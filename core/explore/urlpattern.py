"""Turn concrete URLs into url_patterns (format 7.2), so pages of the same TYPE share one id.

    /patients/42                 -> /patients/{id}
    /patients?page=2&q=smith     -> /patients?page={page}&q={q}
    /appointments/new?patient_id=7 -> /appointments/new?patient_id={patient_id}
"""
import re
from urllib.parse import parse_qsl, urldefrag, urljoin, urlsplit

# id-like path segments: 42, P0042, ORD1234, hex/uuid, and slug+id ("a-light-in-the-attic_1000", "travel_2")
_ID_SEGMENT = re.compile(r"^(?:\d+|[A-Za-z]{0,3}\d{2,}|[0-9a-fA-F]{8,}|[0-9a-fA-F-]{32,36}"
                         r"|[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*[-_]\d+(?:\.html?)?)$")


def normalize(url, base=None):
    """Absolute URL without the #fragment."""
    if base:
        url = urljoin(base, url)
    return urldefrag(url)[0]


def same_origin(a, b):
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)


def path_pattern(path):
    segs = [s for s in path.split("/")]
    out = []
    for s in segs:
        out.append("{id}" if s and _ID_SEGMENT.match(s) else s)
    p = "/".join(out)
    return p or "/"


# Query keys that only page, sort or search a page. They never change WHICH page type you are on.
NOISE_KEYS = {"page", "p", "pg", "pagenum", "page_num", "offset", "start", "skip", "limit", "per_page", "perpage",
              "pagesize", "page_size", "sort", "sortby", "sort_by", "order", "orderby", "order_by", "dir",
              "direction", "q", "query", "search", "s", "term", "keyword", "keywords", "filter", "date", "from",
              "to", "ts", "_", "nocache", "sid", "session", "sessionid", "phpsessid", "jsessionid", "return",
              "returnurl", "return_url", "next", "ref", "utm_source", "utm_medium", "utm_campaign"}
_ROUTING_WORD = re.compile(r"^[A-Za-z][A-Za-z_-]{0,23}$")


def _query_items(url):
    return sorted(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def url_pattern(url):
    """Pattern for a URL (format 7.2).

    id-like path segments -> {id}. Query values become {key}, EXCEPT short routing words on
    non-noise keys, which are kept because they select the page: index.php?action=edit&id=5
    -> /index.php?action=edit&id={id}. Keys are sorted.
    """
    parts = urlsplit(url)
    pat = path_pattern(parts.path or "/")
    seen, q = set(), []
    for k, v in _query_items(url):
        if k in seen:
            continue
        seen.add(k)
        keep = k.lower() not in NOISE_KEYS and _ROUTING_WORD.match(v or "")
        q.append(f"{k}={v}" if keep else f"{k}={{{k}}}")
    if q:
        pat += "?" + "&".join(q)
    return pat


def type_key(url):
    """What makes two URLs the SAME page type: the pattern without paging/sorting/search keys.

    /patients, /patients?page=2 and /patients?q=smith all share the key "/patients".
    """
    path, _, query = url_pattern(url).partition("?")
    q = [x for x in query.split("&") if x and x.split("=", 1)[0].lower() not in NOISE_KEYS]
    return path + ("?" + "&".join(q) if q else "")


def entity_guess(url):
    """Best guess at the entity from the path: /patients/42/edit -> Patient. Generic, no site knowledge."""
    segs = [s for s in urlsplit(url).path.split("/") if s and not _ID_SEGMENT.match(s)]
    skip = {"new", "edit", "view", "show", "detail", "details", "list", "index", "search", "create", "update",
            "admin", "app", "home", "main", "default", "cgi-bin"}
    segs = [re.sub(r"\.(php|asp|aspx|jsp|html?|cgi|do)$", "", s, flags=re.I) for s in segs]
    segs = [s for s in segs if s.lower() not in skip]
    if not segs:
        return None
    word = segs[0]
    if word.lower().endswith("ies"):
        word = word[:-3] + "y"
    elif word.lower().endswith("ses"):
        word = word[:-2]
    elif word.lower().endswith("s") and not word.lower().endswith("ss"):
        word = word[:-1]
    word = re.sub(r"[^A-Za-z0-9]+", " ", word).strip()
    return "".join(w.capitalize() for w in word.split()) or None


def slug(text, fallback="page"):
    s = re.sub(r"[^A-Za-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:48] or fallback


def page_id_from_pattern(pattern):
    """/patients/{id}/edit -> patients_id_edit ; / -> home"""
    path = re.sub(r"/index\.\w+$|\.\w+$", "", pattern.split("?")[0])
    return slug(path.replace("{id}", "id"), "") or "home"
