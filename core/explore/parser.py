"""Document Parser agent: reads the PDFs and big images the Explorer finds, with NVIDIA Nemotron Parse.

Runs in a background thread next to the Explorer:
    Explorer page -> offer(url, title, found_on)   (PDF links, linked images, large <img>s)
    thread        -> download -> render pages (PDF: first pages, 150 dpi) -> Nemotron Parse -> markdown
    Explorer      -> drain() each page and add the results as "Document" records (one per document page)

Read-only: plain GET downloads, size-capped. Nemotron Parse is a small document-transcription VLM
(model MODEL_PARSER, default nvidia/nemotron-parse) that returns the page's text in reading order as markdown.
"""
import base64
import io
import json
import os
import queue
import re
import threading
import time
from urllib.parse import urlparse, unquote

from facade.events import emit
from ingest import nemotron as N

MAX_DOCS = int(os.getenv("PARSER_MAX_DOCS", "8"))          # documents per run (demo-friendly)
MAX_PAGES = int(os.getenv("PARSER_MAX_PAGES", "3"))        # pages per PDF
MAX_BYTES = 15 * 1024 * 1024
MAX_B64 = 170_000                                         # hosted API limit for inline images is ~180 KB
PDF = re.compile(r"\.pdf(\?|#|$)", re.I)
IMG = re.compile(r"\.(png|jpe?g|webp|gif)(\?|#|$)", re.I)


def kind_of(url):
    return "pdf" if PDF.search(url) else "image" if IMG.search(url) else None


def _title(url, text):
    t = (text or "").strip()
    if t and len(t) > 2:
        return t[:120]
    name = unquote(urlparse(url).path.rsplit("/", 1)[-1]) or url
    return re.sub(r"[_\-]+", " ", name.rsplit(".", 1)[0])[:120] or name


def _jpeg_b64(img):
    """Fit a page image under the inline size limit (scale down, then lower quality)."""
    from PIL import Image
    img = img.convert("RGB")
    width, q = min(img.width, 1280), 85
    while True:
        im = img if img.width <= width else img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        b64 = base64.b64encode(buf.getvalue()).decode()
        if len(b64) <= MAX_B64 or width < 500:
            return b64
        if q > 60:
            q -= 10
        else:
            width = int(width * 0.8)


def doc_id(url, page):
    """Readable unique id for one document page: 'syllabus-cs3162-3f9a1c-p1'."""
    import hashlib
    name = re.sub(r"[^a-z0-9]+", "-", unquote(urlparse(url).path.rsplit("/", 1)[-1]).rsplit(".", 1)[0].lower()).strip("-")
    return f"{name[:40] or 'doc'}-{hashlib.sha1(url.encode()).hexdigest()[:6]}-p{page}"


def render(data, kind):
    """bytes -> [PIL images], one per page."""
    from PIL import Image
    if kind == "image":
        return [Image.open(io.BytesIO(data))]
    import pypdfium2 as pdfium   # pip install pypdfium2
    pdf = pdfium.PdfDocument(data)
    try:
        return [pdf[i].render(scale=150 / 72).to_pil() for i in range(min(len(pdf), MAX_PAGES))]
    finally:
        pdf.close()


def parse_image(img):
    """One page image -> markdown, with Nemotron Parse. Returns (markdown, ms, model)."""
    b64 = _jpeg_b64(img)
    t0 = time.time()
    api = N.client().with_options(timeout=120)
    tools = [{"type": "function", "function": {"name": "markdown_no_bbox"}}]
    try:   # documented NIM format: an image_url content part
        r = api.chat.completions.create(model=N.MODEL_PARSER, tools=tools, temperature=0.0, max_tokens=4000, messages=[
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}])
    except Exception as e:   # some hosted endpoints want the image inline in the text
        if getattr(e, "status_code", None) not in (400, 422):
            raise
        r = api.chat.completions.create(model=N.MODEL_PARSER, tools=tools, temperature=0.0, max_tokens=4000, messages=[
            {"role": "user", "content": f'<img src="data:image/jpeg;base64,{b64}" />'}])
    ms = int((time.time() - t0) * 1000)
    msg = r.choices[0].message
    text = ""
    for tc in (msg.tool_calls or []):
        try:
            args = json.loads(tc.function.arguments)
        except (ValueError, TypeError):
            continue
        items = args if isinstance(args, list) else [args]
        for it in items:   # markdown_no_bbox: {"text": ...}; markdown_bbox: [{"text", "type", "bbox"}, ...]
            if isinstance(it, list):
                text += "\n\n".join(x.get("text", "") for x in it if isinstance(x, dict))
            elif isinstance(it, dict):
                text += it.get("text", "")
    if not text:
        text = msg.content or ""
    N.CALL_LOG.append({"model": N.MODEL_PARSER, "purpose": "parse_document", "ms": ms, "ok": True, "ts": time.time()})
    return text.strip(), ms, N.MODEL_PARSER


class Parser:
    def __init__(self, host, log=None):
        self.host = host
        self.log = log or (lambda *a, **k: None)
        self.q = queue.Queue()
        self.seen = set()
        self.results = []           # finished records, taken by drain() on the Explorer's thread
        self.lock = threading.Lock()
        self.docs = self.pages = self.failed = 0
        self.busy = False
        self.stopped = False
        self.thread = threading.Thread(target=self._loop, daemon=True, name="facade-parser")
        self.thread.start()
        emit({"stage": "parser", "kind": "start", "model": N.MODEL_PARSER})

    def offer(self, url, text="", found_on=""):
        url = (url or "").split("#")[0]
        k = kind_of(url)
        if not k or url in self.seen or len(self.seen) >= MAX_DOCS or not url.startswith("http"):
            return
        self.seen.add(url)
        title = _title(url, text)
        emit({"stage": "parser", "kind": "found", "url": url, "title": title, "doc_kind": k, "found_on": found_on})
        self.q.put((url, title, k, found_on))

    def drain(self):
        with self.lock:
            out, self.results = self.results, []
        return out

    def finish(self, wait_s=120):
        """Wait (bounded) for the queue to empty, then stop the thread."""
        t_end = time.time() + wait_s
        while (not self.q.empty() or self.busy) and time.time() < t_end:
            time.sleep(0.5)
        self.stopped = True
        self.q.put(None)
        emit({"stage": "parser", "kind": "done", "docs": self.docs, "pages": self.pages, "failed": self.failed})

    def _loop(self):
        import requests
        while True:
            item = self.q.get()
            if item is None or self.stopped:
                return
            url, title, kind, found_on = item
            self.busy = True
            try:
                r = requests.get(url, timeout=30, stream=True, headers={"User-Agent": "Facade-explorer/1.0 (read-only)"})
                r.raise_for_status()
                data = r.raw.read(MAX_BYTES + 1, decode_content=True)
                if len(data) > MAX_BYTES:
                    raise ValueError("file is larger than 15 MB")
                pages = render(data, kind)
                if kind == "image" and pages and min(pages[0].size) < 200:
                    raise ValueError("image too small to hold a document")
                emit({"stage": "parser", "kind": "parsing", "url": url, "title": title, "pages": len(pages)})
                for i, img in enumerate(pages, 1):
                    md, ms, model = parse_image(img)
                    rec = {"title": title, "page": i, "text": md[:8000], "source_url": url, "found_on": found_on,
                           "file_type": kind}
                    if len(md.strip()) >= 40:   # a photo with no text is not a document: no record
                        with self.lock:
                            self.results.append((doc_id(url, i), rec))
                    self.pages += 1
                    first = next((ln.strip("# ").strip() for ln in md.splitlines() if ln.strip()), "")
                    emit({"stage": "parser", "kind": "parsed", "url": url, "title": title, "page": i,
                          "of": len(pages), "chars": len(md), "preview": first[:120], "ms": ms, "model": model})
                    self.log("parsed_document", url=url, page=i, chars=len(md), nemotron_ms=ms, model=model)
                self.docs += 1
            except ImportError as e:
                self.failed += 1
                emit({"stage": "parser", "kind": "failed", "url": url, "title": title,
                      "error": f"missing package ({e.name}); run: pip install pypdfium2"})
            except Exception as e:
                self.failed += 1
                emit({"stage": "parser", "kind": "failed", "url": url, "title": title, "error": str(e)[:160]})
                self.log("parse_failed", url=url, error=str(e)[:200])
            finally:
                self.busy = False
