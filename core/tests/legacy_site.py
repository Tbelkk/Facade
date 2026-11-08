"""A tiny 2005-style web app to test the Explorer against (standard library only, no Flask).

It is deliberately generic and has traps the explorer must avoid:
  * a GET "Delete patient" link and a "Log out" link (must never be followed)
  * edit / booking forms that POST (must never be submitted)
  * a login page with a cookie session

Every request is recorded in `server.hits` so tests can assert what the explorer did.

Run it by hand to look at it:   python tests/legacy_site.py      -> http://127.0.0.1:5055
"""
import html
import threading
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

USER, PASSWORD = "admin", "test-only-password"
PAGE_SIZE = 10
LAST = ["Smith", "Johnson", "Lee", "Garcia", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor", "Clark",
        "Lewis", "Walker", "Hall", "Young", "King", "Wright", "Lopez", "Hill", "Scott", "Green", "Adams", "Baker"]
FIRST = ["John", "Mary", "Ana", "Luis", "Kim", "Raj", "Eve", "Tom", "Sue", "Ian", "Amy", "Bob", "Joy"]
PATIENTS = [{"id": i + 1, "last": LAST[i % len(LAST)], "first": FIRST[i % len(FIRST)],
             "dob": f"{(i % 12) + 1:02d}/{(i % 27) + 1:02d}/19{50 + i % 49}", "phone": f"555-01{i:02d}"}
            for i in range(23)]
PROVIDERS = ["Dr. Lee", "Dr. Patel", "Hyg. Kim"]
APPTS = [{"id": 100 + i, "patient": PATIENTS[i % 23], "date": f"03/{(i % 27) + 1:02d}/2026",
          "time": f"{9 + i % 8}:00", "provider": PROVIDERS[i % 3], "status": "Booked"} for i in range(12)]

STYLE = ("<style>body{background:#D4D0C8;font:11px Verdana}th{background:#000080;color:#fff}"
         "table{border-collapse:collapse}td,th{border:1px solid #888;padding:2px 6px}</style>")


def nav():
    return ('<table id="nav" class="menu"><tr>'
            '<td><a href="/home">Home</a></td><td><a href="/patients">Patients</a></td>'
            '<td><a href="/schedule">Schedule</a></td><td><a href="/reports">Reports</a></td>'
            '<td><a href="/help.html">Help</a></td><td><a href="/logout">Log Out</a></td></tr></table><hr>')


def page(title, body, with_nav=True):
    return (f"<html><head><title>ClinicSoft 2005 - {html.escape(title)}</title>{STYLE}</head><body>"
            f"{nav() if with_nav else ''}<h2>{html.escape(title)}</h2>{body}</body></html>")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    # -------------------------------------------------------- plumbing
    def _session_ok(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return "sid" in c and c["sid"].value in self.server.sessions

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
        h = {"Location": to}
        h.update(headers or {})
        self._send("", 302, h)

    def _record(self):
        self.server.hits.append((self.command, self.path))

    # -------------------------------------------------------- routes
    def do_POST(self):
        self._record()
        u = urlsplit(self.path)
        n = int(self.headers.get("Content-Length", 0) or 0)
        form = parse_qs(self.rfile.read(n).decode())
        if u.path == "/login":
            if form.get("username", [""])[0] == USER and form.get("password", [""])[0] == PASSWORD:
                sid = uuid.uuid4().hex
                self.server.sessions.add(sid)
                return self._redirect("/home", {"Set-Cookie": f"sid={sid}; Path=/"})
            return self._send(page("Login", '<p class="error">Invalid login</p>' + LOGIN_FORM, False))
        self.server.writes.append(self.path)  # any other POST = a write the explorer must never make
        return self._redirect("/home")

    def do_GET(self):
        self._record()
        u = urlsplit(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}
        p = u.path.rstrip("/") or "/"
        if p == "/login":
            return self._send(page("Login", LOGIN_FORM, False))
        if p == "/help.html":
            return self._send(page("Help", "<p>Call the front desk.</p>"))
        if not self._session_ok():
            return self._redirect("/login")
        parts = p.strip("/").split("/")

        if p in ("/", "/home"):
            return self._send(page("Main Menu", "<ul><li><a href='/patients'>Find a patient</a></li>"
                                                "<li><a href='/schedule'>Today's schedule</a></li></ul>"))
        if p == "/logout":
            self.server.writes.append(self.path)
            c = SimpleCookie(self.headers.get("Cookie", ""))
            self.server.sessions.discard(c["sid"].value if "sid" in c else "")
            return self._redirect("/login")
        if p == "/reports":
            return self._send(page("Reports", "<p>Reports are generated nightly.</p>"
                                              "<a href='/reports/export.csv'>Export CSV</a>"))
        if p == "/patients":
            term = q.get("q", "").lower()
            rows = [x for x in PATIENTS if term in x["last"].lower()]
            n = int(q.get("page", "1") or 1)
            chunk = rows[(n - 1) * PAGE_SIZE: n * PAGE_SIZE]
            trs = "".join(f"<tr><td><a href='/patients/{x['id']}'>{x['last']}, {x['first']}</a></td>"
                          f"<td>{x['dob']}</td><td>{x['phone']}</td></tr>" for x in chunk)
            pager = ""
            if n > 1:
                pager += f"<a href='/patients?page={n - 1}&q={term}'>&lt;&lt; Prev</a> | "
            if n * PAGE_SIZE < len(rows):
                pager += f"<a href='/patients?page={n + 1}&q={term}'>Next &gt;&gt;</a>"
            body = ("<form method='get' action='/patients'>Search: <input name='q' value=''>"
                    "<input type='submit' value='Find'></form>"
                    f"<table id='patients'><tr><th>Name</th><th>DOB</th><th>Phone</th></tr>{trs}</table>"
                    f"<p>{pager}</p><a href='/patients/new'>Add patient</a>")
            return self._send(page("Patients", body))
        if p == "/patients/new" or (len(parts) == 3 and parts[0] == "patients" and parts[2] == "edit"):
            pid = parts[1] if len(parts) == 3 else None
            x = next((r for r in PATIENTS if str(r["id"]) == pid), {"last": "", "first": "", "dob": "", "phone": ""})
            body = (f"<form method='post' action='{html.escape(p)}'><table>"
                    f"<tr><td>Last Name <font color='red'>*</font></td><td><input name='lname' value='{x['last']}' required></td></tr>"
                    f"<tr><td>First Name</td><td><input name='fname' value='{x['first']}'></td></tr>"
                    f"<tr><td>DOB (MM/DD/YYYY)</td><td><input name='dob' value='{x['dob']}'></td></tr>"
                    f"<tr><td>Phone</td><td><input name='phone' value='{x['phone']}'></td></tr>"
                    "</table><input type='submit' value='Save'></form>")
            return self._send(page("Edit Patient" if pid else "New Patient", body))
        if len(parts) == 3 and parts[0] == "patients" and parts[2] == "delete":
            self.server.writes.append(self.path)
            return self._redirect("/patients")
        if len(parts) == 2 and parts[0] == "patients":
            x = next((r for r in PATIENTS if str(r["id"]) == parts[1]), None)
            if not x:
                return self._send(page("Not found", "No such patient"), 404)
            body = (f"<table><tr><td><b>Last Name</b></td><td>{x['last']}</td></tr>"
                    f"<tr><td><b>First Name</b></td><td>{x['first']}</td></tr>"
                    f"<tr><td><b>DOB</b></td><td>{x['dob']}</td></tr>"
                    f"<tr><td><b>Phone</b></td><td>{x['phone']}</td></tr></table><br>"
                    f"<a href='/patients/{x['id']}/edit'>Edit</a> | "
                    f"<a href='/appointments/new?patient_id={x['id']}'>New appointment</a> | "
                    f"<a href='/patients/{x['id']}/delete'>Delete patient</a>")
            return self._send(page("Patient", body))
        if p == "/schedule":
            trs = "".join(f"<tr><td><a href='/appointments/{a['id']}'>{a['time']}</a></td><td>{a['date']}</td>"
                          f"<td>{a['patient']['last']}</td><td>{a['provider']}</td></tr>" for a in APPTS)
            return self._send(page("Schedule", "<table><thead><tr><th>Time</th><th>Date</th><th>Patient</th>"
                                               f"<th>Provider</th></tr></thead>{trs}</table>"))
        if p == "/appointments/new":
            opts = "".join(f"<option>{v}</option>" for v in PROVIDERS)
            body = ("<form method='post' action='/appointments/new'><table>"
                    "<tr><td>Date *</td><td><input name='date'></td></tr>"
                    "<tr><td>Time</td><td><input name='time'></td></tr>"
                    f"<tr><td>Provider</td><td><select name='provider'>{opts}</select></td></tr>"
                    "<tr><td>Reason</td><td><textarea name='reason'></textarea></td></tr>"
                    "</table><input type='submit' value='Book'></form>"
                    # a form that would auto-submit: the guard must stop it
                    "<script>setTimeout(()=>fetch('/appointments/autosave',{method:'POST'}),50)</script>")
            return self._send(page("New Appointment", body))
        if len(parts) == 2 and parts[0] == "appointments":
            a = next((r for r in APPTS if str(r["id"]) == parts[1]), None)
            if not a:
                return self._send(page("Not found", "No such appointment"), 404)
            body = (f"<table><tr><td>Date:</td><td>{a['date']}</td></tr><tr><td>Time:</td><td>{a['time']}</td></tr>"
                    f"<tr><td>Patient:</td><td><a href='/patients/{a['patient']['id']}'>{a['patient']['last']}</a></td></tr>"
                    f"<tr><td>Provider:</td><td>{a['provider']}</td></tr><tr><td>Status:</td><td>{a['status']}</td></tr>"
                    f"</table><a href='/appointments/{a['id']}/cancel'>Cancel appointment</a>")
            return self._send(page("Appointment", body))
        return self._send(page("Not found", "Page not found"), 404)


LOGIN_FORM = ("<form method='post' action='/login'><table>"
              "<tr><td>User name</td><td><input name='username'></td></tr>"
              "<tr><td>Password</td><td><input type='password' name='password'></td></tr>"
              "</table><input type='submit' value='Log In'></form>")


def start(port=0):
    """Start in a background thread. Returns the server (server.url, server.hits, server.writes)."""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.hits, srv.writes, srv.sessions = [], [], set()
    srv.url = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    s = start(5055)
    print(f"Legacy test site on {s.url}  (login {USER} / {PASSWORD})  Ctrl+C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        s.shutdown()
