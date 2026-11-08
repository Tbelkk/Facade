"""Shared Nemotron client for Facade (NVIDIA NIM, OpenAI-compatible API).

Settings come from core/.env:
    NVIDIA_API_KEY      your key from build.nvidia.com (never commit it)
    NVIDIA_BASE_URL     https://integrate.api.nvidia.com/v1  (or a self-hosted NIM, e.g. Brev)
    MODEL_VISION        nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
    REASONING_BUDGET    tokens the model may spend thinking (lower = faster)

One model per agent (optional; unset = MODEL_AGENT):
    MODEL_EXPLORER      reads each new kind of page (many calls: pick a fast model)
    MODEL_SPLIT         writes regexes that split packed cells (small focused task)
    MODEL_OPERATOR      tidies names + designs the API (few calls: pick the strongest model)
    NVIDIA_BASE_URL_EXPLORER / _SPLIT / _OPERATOR   send that agent to another endpoint (e.g. a NIM on Brev)
Check what your key can use:  python -m ingest.models
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
MODEL_PARSER = os.getenv("MODEL_PARSER", "nvidia/nemotron-parse")   # document page images -> markdown
REASONING_BUDGET = int(os.getenv("REASONING_BUDGET", "1024"))
MAX_IMAGE_WIDTH = int(os.getenv("MAX_IMAGE_WIDTH", "1600"))
TIMEOUT_S = float(os.getenv("NEMOTRON_TIMEOUT", "90"))

# Every call is recorded here so the overlay's "Nemotron log" panel can show it.
CALL_LOG = []

_clients = {}
ROLES = ("explorer", "split", "operator")
ROLE_MODEL = {r: os.getenv(f"MODEL_{r.upper()}") or None for r in ROLES}
ROLE_URL = {r: os.getenv(f"NVIDIA_BASE_URL_{r.upper()}") or None for r in ROLES}


def role_of(purpose):
    p = purpose or ""
    if p.startswith(("extract_page", "explore")):
        return "explorer"
    if p.startswith("split"):
        return "split"
    if p.startswith("operator"):
        return "operator"
    return None


def route(purpose, model):
    """(model, base_url) for a call: the agent's own model/endpoint if set, else what the caller asked for."""
    r = role_of(purpose)
    if r and ROLE_MODEL[r] and model in (None, MODEL_AGENT):
        model = ROLE_MODEL[r]
    return model or MODEL_VISION, (ROLE_URL[r] if r else None) or BASE_URL
_NO_BUDGET = set()  # models that rejected the reasoning_budget parameter
_UNAVAILABLE = set()  # models that returned 404 for this account (we fall back to MODEL_VISION)


def client(base_url=None):
    base_url = base_url or BASE_URL
    if base_url not in _clients:
        from openai import OpenAI

        key = os.getenv("NVIDIA_API_KEY", "")
        if not key or "paste" in key:
            raise RuntimeError("NVIDIA_API_KEY is missing. Paste your key into core/.env")
        _clients[base_url] = OpenAI(base_url=base_url, api_key=key, timeout=TIMEOUT_S)
    return _clients[base_url]


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
         temperature=0.6, top_p=0.95, retries=2, _routed=False):
    """One Nemotron call with retries. Returns {"text", "ms", "usage", "model"}."""
    if _routed:
        base = BASE_URL
        model = model or MODEL_VISION
    else:
        model, base = route(purpose, model)
    if model in _UNAVAILABLE:
        model, base = MODEL_VISION, BASE_URL
    budget = REASONING_BUDGET if budget is None else budget
    api = client(base)  # fails fast (no retries) if the key is missing
    if role_of(purpose) == "operator":   # few, long answers from a big model: allow more time, retry less
        api = api.with_options(timeout=max(TIMEOUT_S, 240))
        retries = min(retries, 1)
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
                            temperature=temperature, top_p=top_p, retries=retries, _routed=True)
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
