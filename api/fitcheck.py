"""URL fit check: is this site a good candidate for Facade?

Facade is for older business web systems (records behind logins, tables, forms)
that have no API and no export. This check opens just the first page and looks
for signs either way, so people don't spend a full Nemotron exploration on a
site that isn't a fit.

Version 1 (this file): plain HTTP fetch + HTML rules. No browser, no AI.
Version 2 (later):     use the Explorer's browser capture (capture_web) so
                        JavaScript-heavy sites are seen properly, and add one
                        Nemotron call to make the final verdict.
The response shape stays the same, so the Console doesn't change.

Returns:
    {"verdict": "good_fit" | "probably_not" | "blocked",
     "reasons": [...human-readable...],
     "checked_url": "<url after redirects>",
     "signals": {...raw counts, for debugging...}}
"""

import re
import socket
import sys
import warnings
from html.parser import HTMLParser
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "Mozilla/5.0 (compatible; FacadeFitCheck/0.1; authorized-systems-only)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8",
}
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 12
MAX_BYTES = 3_000_000  # read at most ~3 MB of a page

# Words that suggest bot protection we must never try to get past.
CAPTCHA_MARKERS = [
    "g-recaptcha", "recaptcha/api", "hcaptcha", "h-captcha", "cf-turnstile",
    "challenges.cloudflare.com", "cf-chl-", "/cdn-cgi/challenge-platform",
    "px-captcha", "captcha-delivery", "datadome",
]
CHALLENGE_TITLES = ["just a moment", "attention required", "are you a robot", "verify you are human",
                    "access denied", "security check"]

NEXT_WORDS = {"next", "next >", "next >>", "next page", "more", ">", ">>", "»", "›", "older", "load more"}
LOGIN_WORDS = ("log in", "login", "sign in", "signin", "log on", "logon")
API_HREF = re.compile(r"(/api(/|$|\?)|/apis?/docs|swagger|openapi|graphql|/developers?(/|$)|developer\.)", re.I)
API_TEXT = re.compile(r"^\s*(api|apis|api docs?|api documentation|developers?|developer docs|graphql)\s*$", re.I)
EXPORT_TEXT = re.compile(r"\b(export|download)\b.*\b(csv|excel|xlsx|data|all)\b|\bexport\b", re.I)
EXPORT_HREF = re.compile(r"\.(csv|xlsx?)(\?|$)|[?&](format|export)=(csv|xlsx?|json)", re.I)
PAGE_PARAM = re.compile(r"[?&](p|page|pg|pagenum|offset|start|next)=\w+", re.I)


class _PageScan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.in_title = False
        self.tables = 0
        self.table_rows = 0
        self._table_depth = 0
        self.forms = 0
        self.inputs = 0
        self.password_inputs = 0
        self.search_inputs = 0
        self.selects = 0
        self.textareas = 0
        self.required_fields = 0
        self.labels = 0
        self.paragraphs = 0
        self.articles = 0
        self.scripts = 0
        self.links: List[Dict[str, str]] = []
        self._link = None
        self.text_chars = 0
        self._skip = 0  # inside <script>/<style>
        self.raw_markers: List[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in ("script", "style", "noscript"):
            self._skip += 1
            if tag == "script":
                self.scripts += 1
        if tag == "title":
            self.in_title = True
        elif tag == "table":
            self.tables += 1
            self._table_depth += 1
        elif tag == "tr" and self._table_depth:
            self.table_rows += 1
        elif tag == "form":
            self.forms += 1
        elif tag == "input":
            t = a.get("type", "text").lower()
            if t not in ("hidden", "submit", "button", "image", "reset"):
                self.inputs += 1
            if t == "password":
                self.password_inputs += 1
            if t == "search" or "search" in (a.get("name", "") + a.get("id", "") + a.get("placeholder", "")).lower() \
                    or a.get("name", "").lower() == "q":
                self.search_inputs += 1
            if "required" in a:
                self.required_fields += 1
        elif tag == "select":
            self.selects += 1
            if "required" in a:
                self.required_fields += 1
        elif tag == "textarea":
            self.textareas += 1
        elif tag == "label":
            self.labels += 1
        elif tag == "p":
            self.paragraphs += 1
        elif tag == "article":
            self.articles += 1
        elif tag == "a" and a.get("href"):
            self._link = {"href": a["href"], "text": ""}
        # bot-protection markers can sit in any attribute (class, src, id)
        joined = " ".join(a.values()).lower()
        for m in CAPTCHA_MARKERS:
            if m in joined:
                self.raw_markers.append(m)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        if tag == "title":
            self.in_title = False
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
        elif tag == "a" and self._link is not None:
            self._link["text"] = " ".join(self._link["text"].split())
            self.links.append(self._link)
            self._link = None

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self._skip:
            return
        if self._link is not None:
            self._link["text"] += data
        self.text_chars += len(data.strip())


def _fetch(url: str, verify: bool):
    """GET the page, reading at most MAX_BYTES. Returns (response, body bytes)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # silence the "unverified HTTPS request" warning on the fallback
        resp = requests.get(url, headers=HEADERS, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                            allow_redirects=True, stream=True, verify=verify)
        try:
            body = resp.raw.read(MAX_BYTES, decode_content=True) or b""
        finally:
            resp.close()
    return resp, body


def _decode(body: bytes, ctype: str) -> str:
    """Bytes -> text. Use the charset the server declared, else the page's <meta charset>, else UTF-8."""
    m = re.search(r"charset=([\w.:-]+)", ctype)
    enc = m.group(1) if m else None
    if not enc:
        m = re.search(rb"""<meta[^>]+charset=["']?([\w.:-]+)""", body[:4096], re.I)
        enc = m.group(1).decode("ascii", "ignore") if m else None
    if not enc:
        # Nothing declared: modern pages are UTF-8, older ones usually Windows-1252.
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            return body.decode("cp1252", errors="replace")
    try:
        return body.decode(enc, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _result(verdict: str, reasons: List[str], checked_url: str, signals: Dict[str, Any]) -> Dict[str, Any]:
    return {"verdict": verdict, "reasons": reasons, "checked_url": checked_url, "signals": signals}


def _check(url: str) -> Dict[str, Any]:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return _result("blocked", ["That isn't a valid web address. It should start with http:// or https://"],
                       url, {})

    # ---- 1. Can we reach it? ----
    cert_problem = False
    try:
        resp, body = _fetch(url, verify=True)
    except requests.exceptions.SSLError:
        # Old internal systems often have expired or self-made certificates, which is exactly
        # the kind of site Facade is for. We only READ this one page (nothing is sent),
        # so read it without verification and warn the user instead of blocking.
        cert_problem = True
        try:
            resp, body = _fetch(url, verify=False)
        except requests.exceptions.RequestException:
            return _result("blocked", ["The site's security certificate couldn't be verified, and the page "
                                       "couldn't be read."], url, {})
    except requests.exceptions.TooManyRedirects:
        return _result("blocked", ["The site keeps redirecting in a loop."], url, {})
    except (requests.exceptions.Timeout, socket.timeout):
        return _result("blocked", [f"The site didn't respond within {READ_TIMEOUT} seconds."], url, {})
    except (requests.exceptions.RequestException, OSError, ValueError):
        return _result("blocked", ["Couldn't reach the site. Check the address and that the site is running."],
                       url, {})

    final_url = resp.url
    signals: Dict[str, Any] = {"status": resp.status_code, "certificate_ok": not cert_problem}
    ctype = resp.headers.get("Content-Type", "").lower()
    signals["content_type"] = ctype
    text = _decode(body, ctype)
    lower = text.lower()
    signals["bytes"] = len(body)

    # Read the page now (also used for the bot-protection check below).
    scan = _PageScan()
    try:
        scan.feed(text)
        scan.close()
    except Exception:
        pass  # broken HTML: keep whatever was read before the error

    # ---- 2. Bot protection: never try to get past it ----
    title_l = " ".join(scan.title.split()).lower()
    attr_hits = set(scan.raw_markers)            # markers in tags (script src, div class, iframe src, ...)
    text_hits = {m for m in CAPTCHA_MARKERS if m in lower}
    challenge_status = resp.status_code in (403, 429, 503)
    challenge_title = any(t in title_l for t in CHALLENGE_TITLES)
    # A page that only *mentions* a CAPTCHA in its text (e.g. an article) is not blocked.
    if attr_hits or (challenge_status and (challenge_title or text_hits)):
        signals["captcha_markers"] = sorted(attr_hits | text_hits)
        return _result("blocked", ["The site is protected by a CAPTCHA or bot check. Facade never tries to get "
                                   "around those."], final_url, signals)

    if resp.status_code == 404:
        return _result("blocked", ["The page wasn't found (404). Check the address."], final_url, signals)
    if resp.status_code >= 500:
        return _result("blocked", [f"The site returned a server error ({resp.status_code}). Try again later."],
                       final_url, signals)

    if "html" not in ctype and not lower.lstrip().startswith(("<!doctype html", "<html")):
        if "json" in ctype or "xml" in ctype:
            return _result("probably_not", ["This address returns raw data (" + ctype.split(";")[0] +
                                            "), not a web page. It may already be an API."], final_url, signals)
        return _result("blocked", ["This address isn't a web page (" + (ctype.split(";")[0] or "unknown type") +
                                   ")."], final_url, signals)

    # ---- 3. What's on the page ----
    if not text.strip():
        return _result("probably_not", ["The page came back empty."], final_url, signals)
    host = urlparse(final_url).netloc

    def same_site(href: str) -> bool:
        h = urlparse(urljoin(final_url, href)).netloc
        return h == "" or h == host or h.endswith("." + host.split(":")[0])

    next_links = [l for l in scan.links
                  if l["text"].lower() in NEXT_WORDS or (PAGE_PARAM.search(l["href"]) and same_site(l["href"]))]
    numbered = [l for l in scan.links if re.fullmatch(r"\d{1,3}", l["text"]) and same_site(l["href"])]
    login_links = [l for l in scan.links if l["text"].lower() in LOGIN_WORDS or
                   re.search(r"(^|/)(login|log-in|signin|sign-in|logon)(\.\w+)?($|[/?])", l["href"], re.I)]
    api_links = [l for l in scan.links if API_TEXT.match(l["text"]) or API_HREF.search(l["href"])]
    export_links = [l for l in scan.links if EXPORT_TEXT.search(l["text"]) or EXPORT_HREF.search(l["href"])]

    signals.update({
        "title": " ".join(scan.title.split())[:120],
        "tables": scan.tables, "table_rows": scan.table_rows,
        "forms": scan.forms, "inputs": scan.inputs, "password_inputs": scan.password_inputs,
        "search_inputs": scan.search_inputs, "selects": scan.selects, "required_fields": scan.required_fields,
        "links": len(scan.links), "next_links": len(next_links), "numbered_page_links": len(numbered),
        "login_links": len(login_links), "api_links": [l["href"] for l in api_links][:5],
        "export_links": [l["href"] for l in export_links][:5],
        "paragraphs": scan.paragraphs, "articles": scan.articles,
        "scripts": scan.scripts, "text_chars": scan.text_chars,
    })

    # ---- 4. Score it ----
    score = 0
    good: List[str] = []
    bad: List[str] = []

    if scan.password_inputs:
        score += 3
        good.append("Found a login form. Facade is built for systems behind a login (you'll type the password "
                    "yourself).")
    elif login_links:
        score += 1
        good.append("Found a login link, so there's likely an account area with records.")

    if scan.tables and scan.table_rows >= 3:
        score += 2
        good.append(f"Found {scan.tables} table(s) with {scan.table_rows} rows of what looks like records.")
    # (tiny tables are ignored: older sites use them for page layout, not records)

    if next_links or len(numbered) >= 2:
        score += 1
        good.append("Found page-by-page navigation (Next / page numbers), typical of record lists.")

    if scan.search_inputs:
        score += 1
        good.append("Found a search box.")

    if scan.forms and (scan.selects or scan.required_fields or scan.inputs >= 3) and not scan.password_inputs:
        score += 1
        good.append("Found data-entry forms (fields, dropdowns, required markers).")

    has_api = bool(api_links)
    if has_api:
        score -= 2
        bad.append(f"This site links to an API or developer docs ({api_links[0]['href'][:80]}). If it already "
                   "has an API, use that instead of Facade.")

    if export_links:
        score -= 1
        bad.append("This site seems to offer a data export, so the data may not be trapped.")

    content_heavy = (scan.paragraphs >= 15 or scan.articles >= 3) and not scan.tables and not scan.forms
    if content_heavy:
        score -= 1
        bad.append("The page is mostly articles or text, not records.")

    looks_js_app = scan.text_chars < 200 and scan.scripts >= 3 and not scan.tables and not scan.forms
    if looks_js_app:
        bad.append("The page builds itself with JavaScript, so this quick check can't see its content. The full "
                   "browser check (coming next) will.")

    if resp.status_code in (401, 403) and not scan.password_inputs:
        bad.insert(0, f"The site refused access ({resp.status_code}). You may need to log in first.")

    if score <= 0 and not good and not bad:
        bad.append("Didn't find records, tables, forms or a login on this page.")

    signals["score"] = score

    if score >= 3 and not has_api:
        return _result("good_fit", good + bad, final_url, signals)
    if not good and not bad:
        bad.append("Not enough signs of a records-based system on this page.")
    refused = resp.status_code in (401, 403) and not scan.password_inputs
    if score < 3 and not has_api and not looks_js_app and not content_heavy and not export_links and not refused:
        bad.insert(0, "Only weak signs of a records-based system on this first page.")
    return _result("probably_not", bad + good, final_url, signals)


CERT_WARNING = ("The site's security certificate couldn't be verified. That's common on older internal "
                "systems, but make sure this is the system you expect before logging in.")


def check_url(url: str) -> Dict[str, Any]:
    result = _check(url)
    if result.get("signals", {}).get("certificate_ok") is False:
        result["reasons"] = result["reasons"] + [CERT_WARNING]
    return result


# Real public sites, with the verdict we expect. Run:  python -m api.fitcheck --samples
SAMPLE_URLS = [
    ("https://the-internet.herokuapp.com/login", "good_fit", "plain server-rendered login page"),
    ("https://demo.testfire.net/login.jsp", "probably_not", "old-style portal, but it links to its own REST API docs (/swagger); bad certificate should warn, not block"),
    ("https://www.gutenberg.org/ebooks/search/?query=dickens", "good_fit", "server-rendered record list with search + paging"),
    ("https://news.ycombinator.com", "probably_not", "has a public API (linked in the footer)"),
    ("https://en.wikipedia.org/wiki/Main_Page", "probably_not", "mostly articles"),
    ("https://example.com", "probably_not", "no records at all"),
    ("https://httpbin.org/json", "probably_not", "raw JSON, already an API"),
    ("https://www.google.com/recaptcha/api2/demo", "blocked", "reCAPTCHA demo page"),
    ("https://httpbin.org/status/404", "blocked", "page not found"),
    ("https://this-domain-does-not-exist-facade.com", "blocked", "unreachable"),
]


if __name__ == "__main__":
    # Quick test from the terminal:
    #   python -m api.fitcheck https://example.com        check any URLs
    #   python -m api.fitcheck --samples                  check the real sample sites above
    import json
    args = sys.argv[1:]
    if args == ["--samples"]:
        matched = 0
        for u, expected, why in SAMPLE_URLS:
            r = check_url(u)
            ok = r["verdict"] == expected
            matched += ok
            print(f"\n{'OK  ' if ok else 'DIFF'} {u}\n     got {r['verdict']}, expected {expected} ({why})")
            for reason in r["reasons"]:
                print("      -", reason)
        print(f"\n{matched}/{len(SAMPLE_URLS)} matched the expected verdict.")
        sys.exit(0)
    for u in args or ["https://news.ycombinator.com"]:
        r = check_url(u)
        print(f"\n{u}\n  verdict: {r['verdict']}")
        for reason in r["reasons"]:
            print("   -", reason)
        print("  signals:", json.dumps({k: v for k, v in r["signals"].items() if v not in (0, [], "")}))
