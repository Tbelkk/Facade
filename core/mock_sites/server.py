"""Serve a mock legacy website from a data file (core/mock_sites/data/<name>.json).

The site is generic: every entity in the file gets a paged list, a detail page, an edit form and a
"new" form, 2005-style (server-rendered tables, no API, no export). Traps the agents must handle:
  * login with a cookie session that can expire after N requests (session_max_requests)
  * GET "Delete" and "Log Out" links, and POST forms (the explorer must never use them)
Every request is recorded in server.hits; every write attempt in server.writes.

Run one by hand:   python -m mock_sites.server clinic        -> http://127.0.0.1:5060
"""
import html
import json
import sys
import threading
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DATA_DIR = Path(__file__).resolve().parent / "data"

STYLE = ("<style>body{background:#D4D0C8;font:11px Verdana;margin:8px}th{background:#000080;color:#fff;"
         "text-align:left}table{border-collapse:collapse}td,th{border:1px solid #888;padding:2px 6px}"
         "#nav td{border:2px outset #fff;background:#C0C0C0}.error{color:red}</style>")


def load(name_or_path):
    p = Path(name_or_path)
    if not p.suffix:
        p = DATA_DIR / f"{name_or_path}.json"
    site = json.loads(p.read_text(encoding="utf-8"))
    site.setdefault("page_size", 10)
    site.setdefault("login", None)
    site.setdefault("session_max_requests", 0)
    for e in site["entities"]:
        e.setdefault("path", e["name"].lower() + "s")
        e.setdefault("title", e["name"] + "s")
        e["_by_id"] = {str(r["id"]): r for r in e["records"]}
    site["_by_name"] = {e["name"]: e for e in site["entities"]}
    site["_file"] = str(p)
    return site


# ------------------------------------------------------------------ how values look on the old site

def show(site, field, value):
    """Stored (clean) value -> how the legacy site prints it."""
    if value is None or value == "":
        return ""
    t = field.get("type", "string")
    if t == "date":
        y, m, d = str(value).split("-")
        return f"{m}/{d}/{y}"
    if t == "money":
        return f"${float(value):,.2f}"
    if t == "number":
        return f"{value:,}" if isinstance(value, int) else str(value)
    if field.get("ref"):
        target = site["_by_name"][field["ref"]]
        rec = target["_by_id"].get(str(value))
        return display(site, target, rec) if rec else str(value)
    return str(value)


def display(site, entity, rec):
    tpl = entity.get("display")
    if tpl:
        return tpl.format(**{k: v for k, v in rec.items()})
    first = entity["fields"][0]
    return show(site, first, rec.get(first["key"]))


def cell(site, entity, col, rec):
    if "template" in col:
        return col["template"].format(**{k: ("" if v is None else v) for k, v in rec.items()})
    f = next(x for x in entity["fields"] if x["key"] == col["field"])
    return show(site, f, rec.get(f["key"]))


def esc(s):
    return html.escape(str(s), quote=True)


# ------------------------------------------------------------------ pages

def page(site, title, body, nav=True):
    links = ""
    if nav:
        tds = "".join(f"<td><a href='/{e['path']}'>{esc(e['title'])}</a></td>" for e in site["entities"])
        out = "<td><a href='/logout'>Log Out</a></td>" if site["login"] else ""
        links = f"<table id='nav'><tr><td><a href='/home'>Home</a></td>{tds}{out}</tr></table><hr>"
    brand = esc(site.get("brand", site.get("name", "Legacy System")))
    return (f"<html><head><title>{brand} - {esc(title)}</title>{STYLE}</head><body>"
            f"<b>{brand}</b>{links}<h2>{esc(title)}</h2>{body}"
            f"<hr><small>&copy; 2005 {brand}. Best viewed in Internet Explorer 6.</small></body></html>")


def login_form(error=""):
    err = f"<p class='error'>{esc(error)}</p>" if error else ""
    return (f"{err}<form method='post' action='/login'><table>"
            "<tr><td>User name</td><td><input name='username'></td></tr>"
            "<tr><td>Password</td><td><input type='password' name='password'></td></tr>"
            "</table><input type='submit' value='Log In'></form>")


def list_page(site, e, q):
    term = (q.get("q") or "").lower()
    recs = [r for r in e["records"] if not term or term in display(site, e, r).lower()]
    size = site["page_size"]
    n = max(1, int(q.get("page", "1") or 1))
    chunk = recs[(n - 1) * size: n * size]
    cols = e.get("list_columns") or [{"header": f["label"], "field": f["key"]} for f in e["fields"][:4]]
    head = "".join(f"<th>{esc(c['header'])}</th>" for c in cols)
    trs = ""
    for r in chunk:
        tds = []
        for i, c in enumerate(cols):
            v = esc(cell(site, e, c, r))
            tds.append(f"<td><a href='/{e['path']}/{r['id']}'>{v}</a></td>" if i == 0 else f"<td>{v}</td>")
        trs += "<tr>" + "".join(tds) + "</tr>"
    pager = []
    if n > 1:
        pager.append(f"<a href='/{e['path']}?page={n - 1}&q={esc(term)}'>&lt;&lt; Prev</a>")
    pager.append(f"Page {n} of {max(1, -(-len(recs) // size))}")
    if n * size < len(recs):
        pager.append(f"<a href='/{e['path']}?page={n + 1}&q={esc(term)}'>Next &gt;&gt;</a>")
    body = (f"<form method='get' action='/{e['path']}'>Search: <input name='q' value='{esc(term)}'>"
            "<input type='submit' value='Find'></form>"
            f"<table class='grid'><tr>{head}</tr>{trs}</table><p>{' | '.join(pager)}</p>"
            + ("" if e.get("read_only") else f"<a href='/{e['path']}/new'>Add {esc(e['name'].lower())}</a>"))
    return page(site, e["title"], body)


def detail_page(site, e, rec):
    rows = ""
    for f in e["fields"]:
        v = esc(show(site, f, rec.get(f["key"])))
        if f.get("ref") and rec.get(f["key"]) not in (None, ""):
            target = site["_by_name"][f["ref"]]
            v = f"<a href='/{target['path']}/{rec[f['key']]}'>{v}</a>"
        rows += f"<tr><td><b>{esc(f['label'])}:</b></td><td>{v}</td></tr>"
    links = [] if e.get("read_only") else [f"<a href='/{e['path']}/{rec['id']}/edit'>Edit</a>"]
    for other in site["entities"]:  # "New <child>" links for entities that point at this one
        ref = next((f for f in other["fields"] if f.get("ref") == e["name"]), None)
        if ref and not other.get("read_only"):
            links.append(f"<a href='/{other['path']}/new?{ref['key']}={rec['id']}'>New {esc(other['name'].lower())}</a>")
    links.append(f"<a href='/{e['path']}'>Back to list</a>")
    if not e.get("read_only"):
        links.append(f"<a href='/{e['path']}/{rec['id']}/delete'>Delete {esc(e['name'].lower())}</a>")
    return page(site, e["name"], f"<table>{rows}</table><br>{' | '.join(links)}")


def form_page(site, e, rec, action, q=None):
    q = q or {}
    rows = ""
    for f in e["fields"]:
        star = " <font color='red'>*</font>" if f.get("required") else ""
        label = esc(f["label"]) + (" (MM/DD/YYYY)" if f.get("type") == "date" else "")
        raw = rec.get(f["key"]) if rec else q.get(f["key"], "")
        name = esc(f["key"])
        if f.get("options"):
            shown = show(site, f, raw)
            opts = "<option value=''>-- choose --</option>" + "".join(
                f"<option{' selected' if o == shown else ''}>{esc(o)}</option>" for o in f["options"])
            ctrl = f"<select name='{name}'>{opts}</select>"
        elif f.get("type") == "text":
            ctrl = f"<textarea name='{name}'>{esc(show(site, f, raw))}</textarea>"
        else:
            val = raw if f.get("ref") else show(site, f, raw)
            ctrl = f"<input name='{name}' value='{esc(val or '')}'{' required' if f.get('required') else ''}>"
        rows += f"<tr><td>{label}{star}</td><td>{ctrl}</td></tr>"
    title = f"Edit {e['name']}" if rec else f"New {e['name']}"
    body = (f"<form method='post' action='{esc(action)}'><table>{rows}</table>"
            "<input type='submit' value='Save'> <input type='reset' value='Clear'></form>")
    return page(site, title, body)


def home_page(site):
    items = "".join(f"<li><a href='/{e['path']}'>{esc(e['title'])}</a> ({len(e['records'])})</li>"
                    for e in site["entities"])
    return page(site, "Main Menu", f"<p>Welcome to {esc(site.get('name', ''))}.</p><ul>{items}</ul>")


# ------------------------------------------------------------------ HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    @property
    def site(self):
        return self.server.site

    def _sid(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return c["sid"].value if "sid" in c else ""

    def _session_ok(self):
        if not self.site["login"]:
            return True
        sid = self._sid()
        if sid not in self.server.sessions:
            return False
        limit = self.site["session_max_requests"]
        self.server.sessions[sid] += 1
        if limit and self.server.sessions[sid] > limit:  # session timeout
            del self.server.sessions[sid]
            self.server.expired += 1
            return False
        return True

    def _send(self, body, status=200, headers=None):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, to, headers=None):
        self._send("", 302, {"Location": to, **(headers or {})})

    def do_POST(self):
        self.server.hits.append(("POST", self.path))
        n = int(self.headers.get("Content-Length", 0) or 0)
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
        login = self.site["login"]
        if urlsplit(self.path).path == "/login" and login:
            if form.get("username") == login["username"] and form.get("password") == login["password"]:
                sid = uuid.uuid4().hex
                self.server.sessions[sid] = 0
                return self._redirect("/home", {"Set-Cookie": f"sid={sid}; Path=/"})
            return self._send(page(self.site, "Login", login_form("Invalid login"), nav=False))
        self.server.writes.append(("POST", self.path))  # the mock never changes its data
        return self._redirect("/home")

    def do_GET(self):
        self.server.hits.append(("GET", self.path))
        site = self.site
        u = urlsplit(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}
        p = u.path.rstrip("/") or "/"
        if p == "/login":
            return self._send(page(site, "Login", login_form(), nav=False))
        if not self._session_ok():
            return self._redirect("/login")
        if p in ("/", "/home"):
            return self._send(home_page(site))
        if p == "/logout":
            self.server.writes.append(("GET", self.path))
            self.server.sessions.pop(self._sid(), None)
            return self._redirect("/login")
        parts = p.strip("/").split("/")
        e = next((x for x in site["entities"] if x["path"] == parts[0]), None)
        if not e:
            return self._send(page(site, "Not found", "Page not found"), 404)
        if len(parts) == 1:
            return self._send(list_page(site, e, q))
        if e.get("read_only") and (parts[-1] in ("new", "edit", "delete")):
            return self._send(page(site, "Not found", "Page not found"), 404)
        if parts[1] == "new" and len(parts) == 2:
            return self._send(form_page(site, e, None, p, q))
        rec = e["_by_id"].get(parts[1])
        if not rec:
            return self._send(page(site, "Not found", f"No such {e['name'].lower()}"), 404)
        if len(parts) == 2:
            return self._send(detail_page(site, e, rec))
        if parts[2] == "edit":
            return self._send(form_page(site, e, rec, p))
        if parts[2] == "delete":
            self.server.writes.append(("GET", self.path))
            return self._redirect(f"/{e['path']}")
        return self._send(page(site, "Not found", "Page not found"), 404)


def start(name_or_path, port=0):
    """Start in a background thread. Returns the server (.url, .site, .hits, .writes, .expired)."""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.site = load(name_or_path)
    srv.hits, srv.writes, srv.sessions, srv.expired = [], [], {}, 0
    srv.url = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    name = argv[0] if argv else "clinic"
    port = int(argv[1]) if len(argv) > 1 else 5060
    s = start(name, port)
    login = s.site["login"]
    print(f"{s.site.get('name')} on {s.url}" + (f"  (login {login['username']} / {login['password']})" if login else ""))
    print("Ctrl+C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        s.shutdown()


if __name__ == "__main__":
    main()
