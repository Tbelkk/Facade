"""Shared Nemotron client for Facade (NVIDIA NIM, OpenAI-compatible API).

Settings come from core/.env:
    NVIDIA_API_KEY      your key from build.nvidia.com (never commit it)
    NVIDIA_BASE_URL     https://integrate.api.nvidia.com/v1  (or a self-hosted NIM, e.g. Brev)
    MODEL_VISION        nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
    REASONING_BUDGET    tokens the model may spend thinking (lower = faster)
"""
import base64
import io
import json
import os
import re
import time

from dotenv import load_dotenv

from .paths import CORE_DIR

load_dotenv(CORE_DIR / ".env")
load_dotenv()  # also allow a .env in the current folder

BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL_VISION = os.getenv("MODEL_VISION", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")
MODEL_AGENT = os.getenv("MODEL_AGENT", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")
REASONING_BUDGET = int(os.getenv("REASONING_BUDGET", "1024"))
MAX_IMAGE_WIDTH = int(os.getenv("MAX_IMAGE_WIDTH", "1600"))
TIMEOUT_S = float(os.getenv("NEMOTRON_TIMEOUT", "90"))

# Every call is recorded here so the overlay's "Nemotron log" panel can show it.
CALL_LOG = []

_client = None
_NO_BUDGET = set()  # models that rejected the reasoning_budget parameter
_UNAVAILABLE = set()  # models that returned 404 for this account (we fall back to MODEL_VISION)


def client():
    global _client
    if _client is None:
        from openai import OpenAI

        key = os.getenv("NVIDIA_API_KEY", "")
        if not key or "paste" in key:
            raise RuntimeError("NVIDIA_API_KEY is missing. Paste your key into core/.env")
        _client = OpenAI(base_url=BASE_URL, api_key=key, timeout=TIMEOUT_S)
    return _client


def image_part(path, max_width=MAX_IMAGE_WIDTH):
    """Encode a screenshot for the model. Large images are scaled down to save time.

    Returns (content_part, scale) where scale = original_width / sent_width,
    so coordinates the model returns can be mapped back to real pixels.
    """
    from PIL import Image

    img = Image.open(path).convert("RGB")
    scale = 1.0
    if img.width > max_width:
        scale = img.width / max_width
        img = img.resize((max_width, round(img.height / scale)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return {"type": "image_url", "image_url": {"url": url}}, scale


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S)


def strip_reasoning(text):
    """Remove visible chain-of-thought if the model includes it in the answer text."""
    if not text:
        return ""
    text = _THINK_BLOCK.sub("", text)
    if "</think>" in text:  # opening tag cut off
        text = text.split("</think>", 1)[1]
    return text.strip()


def chat(messages, purpose="call", model=None, budget=None, answer_tokens=2000,
         temperature=0.6, top_p=0.95, retries=2):
    """One Nemotron call with retries. Returns {"text", "ms", "usage", "model"}."""
    model = model or MODEL_VISION
    if model in _UNAVAILABLE:
        model = MODEL_VISION
    budget = REASONING_BUDGET if budget is None else budget
    api = client()  # fails fast (no retries) if the key is missing
    last_err = None
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            r = api.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=budget + answer_tokens,
                temperature=temperature,
                top_p=top_p,
                extra_body={} if model in _NO_BUDGET else {"reasoning_budget": budget},
            )
            ms = int((time.time() - t0) * 1000)
            text = strip_reasoning(r.choices[0].message.content or "")
            usage = getattr(r, "usage", None)
            usage = usage.model_dump() if hasattr(usage, "model_dump") else usage
            CALL_LOG.append({"model": model, "purpose": purpose, "ms": ms, "ok": True, "ts": time.time()})
            return {"text": text, "ms": ms, "usage": usage, "model": model}
        except Exception as e:  # rate limits, timeouts, 5xx
            last_err = e
            status = getattr(e, "status_code", None)
            if status in (400, 422) and model not in _NO_BUDGET:
                _NO_BUDGET.add(model)  # the model may not accept reasoning_budget: retry once without it
                if True:
                    try:
                        r = api.chat.completions.create(model=model, messages=messages, max_tokens=answer_tokens + 2000,
                                                        temperature=temperature, top_p=top_p)
                        ms = int((time.time() - t0) * 1000)
                        text = strip_reasoning(r.choices[0].message.content or "")
                        CALL_LOG.append({"model": model, "purpose": purpose, "ms": ms, "ok": True, "ts": time.time()})
                        return {"text": text, "ms": ms, "usage": None, "model": model}
                    except Exception as e2:
                        last_err = e2
            retryable = status in (408, 429, 500, 502, 503, 504) or (status is None and "404" not in str(e))
            CALL_LOG.append({"model": model, "purpose": purpose, "ms": int((time.time() - t0) * 1000),
                             "ok": False, "error": str(e)[:200], "ts": time.time()})
            if status == 404 and model != MODEL_VISION and model not in _UNAVAILABLE:
                # model not available on this account/endpoint: fall back to the vision model (it handles text too)
                _UNAVAILABLE.add(model)
                print(f"  ! {model} is not available for this NVIDIA account; falling back to {MODEL_VISION}")
                return chat(messages, purpose=purpose, model=MODEL_VISION, budget=budget, answer_tokens=answer_tokens,
                            temperature=temperature, top_p=top_p, retries=retries)
            if not retryable or attempt == retries:
                break
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Nemotron call failed ({purpose}): {last_err}")


def extract_json(text):
    """Pull the first JSON object out of a model answer (handles ```json fences and extra prose)."""
    if not text:
        raise ValueError("empty answer")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    start = t.find("{")
    if start < 0:
        raise ValueError("no JSON object in answer")
    # try progressively shorter endings
    ends = [i for i, ch in enumerate(t) if ch == "}" and i > start]
    for end in reversed(ends):
        try:
            return json.loads(t[start:end + 1])
        except Exception:
            continue
    raise ValueError("could not parse JSON from answer")
