"""The Explorer agent: start from a URL and map the whole system on its own, read-only.

Loop (one iteration = one step):
    capture the page (Playwright)  ->  PageReader names it (Nemotron Nano Omni)
    ->  collect safe candidate actions from every page seen so far
    ->  Planner picks one (Nemotron Super): follow link | open row | open form | stop
    ->  navigate (GET only)  ->  repeat until the page budget is spent or nothing new is left

Safety (team rule 4: the Explorer never submits forms):
    * A browser-level guard aborts every request that is not GET/HEAD/OPTIONS. The only exception is
      the single login submit when login mode is "env". Blocked requests are reported.
    * Links whose text or URL looks destructive (logout, delete, remove, ...) are never followed.
    * Navigation is always page.goto(<link href>); the explorer never clicks buttons.

Output (format 7.2): site_map.json, plus one page model per page type in pages/ for the Understand step.
"""
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from . import capture_web, policy, sink as sink_mod
from .capture_web import NEXT_TEXT, PREV_TEXT
from .urlpattern import normalize, same_origin, slug, type_key, url_pattern

DENY = re.compile(
    r"log\s*-?\s*(out|off)|sign\s*-?\s*(out|off)|\bexit\b|delete|remove|destroy|\bvoid\b|purge|\bcancel|"
    r"\breset\b|\bdrop\b|archive|unsubscribe|deactivate|disable|terminate|\bapprove|\breject|\bsend\b|"
    r"\bsubmit|\bpay\b|checkout|\bprint\b|download|export", re.I)
FORM_HINT_URL = re.compile(r"/(edit|new|add|create|book|register|update)\b|[?&](action|mode|op)=(edit|new|add|create)",
                           re.I)
FORM_HINT_TEXT = re.compile(r"^\s*(edit|new|add|create|book|register|schedule)\b|\b(edit|new)\s*$", re.I)
SKIP_EXT = re.compile(r"\.(pdf|zip|gz|csv|xlsx?|docx?|pptx?|png|jpe?g|gif|svg|ico|css|js|xml|rss|mp[34])(\?|$)",
                      re.I)
VALID_KINDS = {"list", "detail", "form", "menu", "login", "other"}

CORE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUT = CORE_DIR / "cache" / "explore"


@dataclass
class ExploreConfig:
    start_url: str
    page_budget: int = 25
    max_steps: int = 0                 # 0 = 3 x page_budget (navigations, including failed ones)
    headless: bool = True
    reader: str = "heuristic"          # "nemotron" = Nano Omni reads each page
    planner: str = "heuristic"         # "nemotron" = Super picks each step
    sink: str = "json"                 # "spacetime" also mirrors to SpacetimeDB
    out_dir: str = ""                  # default core/cache/explore/<host>_<time>
    login: str = "none"                # "none" | "env" | "manual"
    username: str = ""
    password: str = ""
    screenshots: bool = True
    nav_timeout_ms: int = 15000
    reasoning_budget: int = 0          # 0 = use REASONING_BUDGET from .env
    extra: dict = field(default_factory=dict)


class LoginRequired(RuntimeError):
    pass


class Explorer:
    def __init__(self, cfg, reader=None, planner=None, sink=None):
        self.cfg = cfg
        cfg.start_url = normalize(cfg.start_url)
        if not cfg.max_steps:
            cfg.max_steps = cfg.page_budget * 3
        budget = cfg.reasoning_budget or None
        r, p = policy.make(cfg.reader, cfg.planner, budget=budget, use_screenshot=cfg.screenshots)
        self.reader = reader or r
        self.planner = planner or p
        host = slug(urlsplit(cfg.start_url).netloc, "site")
        self.run_dir = Path(cfg.out_dir) if cfg.out_dir else DEFAULT_OUT / f"{host}_{time.strftime('%Y%m%d-%H%M%S')}"
        self.sink = sink or sink_mod.make(cfg.sink, self.run_dir)

        self.pages = {}          # page_id -> site-map entry (+ internal keys starting with "_")
        self.key_to_id = {}      # type_key -> page_id
        self.candidates = {}     # cand id -> candidate
        self.queued_keys = set()
        self.used = set()
        self.risky = []          # links skipped because they looked destructive
        self.blocked = []        # non-GET requests the guard stopped
        self.notes = []
        self.nemotron = {"calls": 0, "ms": 0, "fallbacks": 0}
        self._allow_write = False
        self._order = 0

    # ------------------------------------------------------------ helpers

    def log(self, message, level="info", **data):
        ev = self.sink.log_event(message, level, **data)
        if os.getenv("FACADE_QUIET") != "1":
            print(f"[explorer] {message}", flush=True)
        return ev

    def _count_ai(self, by, ms):
        if by == "nemotron":
            self.nemotron["calls"] += 1
            self.nemotron["ms"] += ms or 0
        elif by == "heuristic_fallback":
            self.nemotron["calls"] += 1
            self.nemotron["fallbacks"] += 1
            self.nemotron["ms"] += ms or 0

    def _guard(self, route, request):
        if request.method in ("GET", "HEAD", "OPTIONS") or self._allow_write:
            route.continue_()
            return
        self.blocked.append({"method": request.method, "url": request.url})
        self.log(f"Blocked a {request.method} request (explorer is read-only): {request.url}", level="warn",
                 action="blocked_write", method=request.method, url=request.url)
        route.abort("blockedbyclient")

    # ------------------------------------------------------------ login

    def _login(self, page):
        mode = self.cfg.login
        if mode == "none":
            raise LoginRequired("This site asks for a login. Re-run with --login env (credentials from .env) "
                                "or --login manual (you type them in the browser window).")
        if mode == "manual":
            if self.cfg.headless:
                raise LoginRequired("--login manual needs a visible browser (add --headed).")
            input("\n>>> Log in in the browser window, then press Enter here to start exploring... ")
        else:
            user = self.cfg.username or os.getenv("FACADE_LOGIN_USER") or os.getenv("CLINICPRO_USER", "")
            pw = self.cfg.password or os.getenv("FACADE_LOGIN_PASS") or os.getenv("CLINICPRO_PASS", "")
            if not user or not pw:
                raise LoginRequired("--login env needs FACADE_LOGIN_USER / FACADE_LOGIN_PASS (or CLINICPRO_USER / "
                                    "CLINICPRO_PASS) in core/.env")
            pw_box = page.locator("input[type=password]").first
            form = pw_box.locator("xpath=ancestor::form[1]")
            scope = form if form.count() else page
            user_box = scope.locator("input:not([type]), input[type=text], input[type=email]").first
            user_box.fill(user)
            pw_box.fill(pw)
            self._allow_write = True  # the ONE write the explorer ever makes: the login submit
            try:
                with page.expect_navigation(timeout=self.cfg.nav_timeout_ms):
                    submit = scope.locator("button[type=submit], input[type=submit], button:not([type])").first
                    if submit.count():
                        submit.click()
                    else:
                        pw_box.press("Enter")
            finally:
                self._allow_write = False
        page.wait_for_load_state("domcontentloaded")
        if page.locator("input[type=password]").count():
            raise LoginRequired("Login did not work: the page still asks for a password.")
        self.log("Logged in", action="login", mode=mode)

    # ------------------------------------------------------------ pages

    def _register(self, model, via=None):
        """Name a freshly captured page and add it to the site map. Returns page_id."""
        url = model["screen"]["url"]
        key = type_key(url)
        if key in self.key_to_id:
            return self.key_to_id[key]

        known = [p for p in self.pages]
        read = self.reader.read(model, known)
        self._count_ai(read.get("by"), read.get("ms"))
        pid = read["page_id"] or "page"
        if pid in self.pages:  # the reader reused a name for a different page type
            k = 2
            while f"{pid}_{k}" in self.pages:
                k += 1
            pid = f"{pid}_{k}"
        kind = read["kind"] if read["kind"] in VALID_KINDS else "other"

        model["screen"]["id"] = pid
        model["screen"]["ai"] = {k: read.get(k) for k in ("purpose", "entity", "kind", "confidence", "by")}
        self.sink.save_page(pid, model)

        entry = {
            "id": pid,
            "url_pattern": model["screen"]["url_pattern"],
            "purpose": read["purpose"],
            "entity": read.get("entity"),
            "kind": kind,
            "example_url": url,
            "title": model["screen"]["title"],
            "capture": f"pages/{pid}.json",
            "confidence": read.get("confidence"),
            "read_by": read.get("by"),
            "_model": model,
            "_key": key,
        }
        self.pages[pid] = entry
        self.key_to_id[key] = pid
        self.queued_keys.add(key)
        self.log(f"Mapped {pid} ({kind}{', ' + entry['entity'] if entry['entity'] else ''}): {entry['purpose']}",
                 page=pid, action="map_page", kind=kind, url=url, read_by=read.get("by"),
                 nemotron_ms=read.get("ms", 0), via=via, error=read.get("error"))
        self._add_candidates(pid, model)
        return pid

    def _add_candidates(self, pid, model):
        start = self.cfg.start_url
        seen_row_keys = set()
        for link in model["dom"]["links"]:
            href = link.get("href") or ""
            if not href.startswith(("http://", "https://")):
                continue
            url = normalize(href)
            text = link.get("text") or ""
            if not same_origin(url, start) or SKIP_EXT.search(url):
                continue
            if DENY.search(text) or DENY.search(urlsplit(url).path + "?" + urlsplit(url).query):
                if len(self.risky) < 50 and text not in [r["text"] for r in self.risky]:
                    self.risky.append({"text": text, "url": url, "page": pid})
                continue
            if NEXT_TEXT.search(text) or PREV_TEXT.search(text):
                continue  # paging: recorded on the list page, not a new page type
            key = type_key(url)
            if key in self.queued_keys or key in seen_row_keys:
                continue
            if link.get("in_table") or link.get("in_repeat"):
                ctype = "open_row"
                seen_row_keys.add(key)
            elif FORM_HINT_URL.search(url) or FORM_HINT_TEXT.search(text):
                ctype = "open_form"
            else:
                ctype = "follow_link"
            self._order += 1
            cid = f"c{self._order}"
            self.candidates[cid] = {"id": cid, "type": ctype, "label": text[:60] or url_pattern(url),
                                    "url": url, "url_pattern": url_pattern(url), "key": key, "from_page": pid,
                                    "in_nav": bool(link.get("in_nav")), "order": self._order}
            self.queued_keys.add(key)

    def _open(self):
        return [c for cid, c in self.candidates.items() if cid not in self.used and c["key"] not in self.key_to_id]

    def _goto(self, page, url):
        resp = page.goto(url, wait_until="domcontentloaded", timeout=self.cfg.nav_timeout_ms)
        return resp.status if resp else None

    def _visit(self, page, cand):
        try:
            status = self._goto(page, cand["url"])
        except Exception as e:
            self.log(f"Could not open {cand['url']}: {str(e)[:120]}", level="warn", action="navigate_failed",
                     url=cand["url"])
            return None
        # Session expired and we were bounced to the login page: log in again, retry once.
        if page.locator("input[type=password]").count() and self.cfg.login != "none" \
                and type_key(page.url) != cand["key"]:
            self.log("Session looks expired (login page shown). Logging in again.", level="warn", action="relogin")
            self._login(page)
            status = self._goto(page, cand["url"])
        if status and status >= 400:
            self.log(f"{cand['url']} answered HTTP {status}", level="warn", action="http_error", status=status)
            self.notes.append(f"HTTP {status} at {cand['url_pattern']}")
            return None
        model = capture_web.capture(page, shots_dir=self.run_dir / "shots" if self.cfg.screenshots else None)
        via = {"from": cand["from_page"], "type": cand["type"], "text": cand["label"]}
        return self._register(model, via=via)

    # ------------------------------------------------------------ main loop

    def run(self):
        from playwright.sync_api import sync_playwright

        cfg = self.cfg
        t0 = time.time()
        steps, stop_reason = 0, "budget"
        self.log(f"Exploring {cfg.start_url} (budget {cfg.page_budget} pages, reader={self.reader.name}, "
                 f"planner={self.planner.name})", action="start", url=cfg.start_url)
        self.sink.job("running", 0, cfg.page_budget)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=cfg.headless)
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            ctx.route("**/*", self._guard)
            page = ctx.new_page()
            page.on("dialog", lambda d: d.dismiss())
            try:
                self._goto(page, cfg.start_url)
                first = capture_web.capture(page, shots_dir=self.run_dir / "shots" if cfg.screenshots else None)
                current = self._register(first, via={"type": "start"})
                if first["dom"]["has_password"]:
                    self._login(page)
                    after = capture_web.capture(page, shots_dir=self.run_dir / "shots" if cfg.screenshots else None)
                    current = self._register(after, via={"from": current, "type": "login"})

                while len(self.pages) < cfg.page_budget and steps < cfg.max_steps:
                    open_c = self._open()
                    site = [{"id": p["id"], "kind": p["kind"], "entity": p["entity"],
                             "url_pattern": p["url_pattern"]} for p in self.pages.values()]
                    decision = self.planner.choose(site, current, open_c)
                    self._count_ai(decision.get("by"), decision.get("ms"))
                    if decision["action"] == "stop":
                        stop_reason = "planner_stop" if open_c else "nothing_left"
                        self.log(f"Stopping: {decision.get('reason')}", action="stop", by=decision.get("by"),
                                 nemotron_ms=decision.get("ms", 0))
                        break
                    cand = self.candidates[decision["action"]]
                    self.used.add(cand["id"])
                    steps += 1
                    self.log(f"Step {steps}: {cand['type']} '{cand['label']}' -> {cand['url_pattern']} "
                             f"({decision.get('reason', '')})", action=cand["type"], page=cand["from_page"],
                             url=cand["url"], by=decision.get("by"), nemotron_ms=decision.get("ms", 0),
                             error=decision.get("error"))
                    got = self._visit(page, cand)
                    if got:
                        current = got
                    self.sink.job("running", len(self.pages), cfg.page_budget)
                else:
                    stop_reason = "budget" if len(self.pages) >= cfg.page_budget else "max_steps"
            except LoginRequired as e:
                stop_reason = "login_required"
                self.notes.append(str(e))
                self.log(str(e), level="error", action="login_required")
            finally:
                browser.close()

        site_map = self.site_map(stop_reason, steps, time.time() - t0)
        path = self.sink.save_site(site_map)
        DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
        (DEFAULT_OUT / "latest_site_map.json").write_text(json.dumps(site_map, indent=2), encoding="utf-8")
        self.sink.job("done", len(self.pages), cfg.page_budget)
        self.log(f"Done: {len(self.pages)} page types in {steps} steps, stop={stop_reason}. Site map: {path}",
                 action="done", pages=len(self.pages), steps=steps, stop=stop_reason)
        return {"site_map": site_map, "run_dir": str(self.run_dir), "site_map_path": str(path)}

    # ------------------------------------------------------------ site map (format 7.2)

    def site_map(self, stop_reason, steps, seconds):
        pages, edges = [], []
        for pid, p in self.pages.items():
            entry = {k: v for k, v in p.items() if not k.startswith("_")}
            model = p["_model"]
            pag = model["screen"]["heuristic"].get("pagination")
            if p["kind"] == "list" and pag and pag.get("next"):
                entry["pagination"] = {k: pag[k] for k in ("next", "prev", "page_size") if k in pag}
            # row_link: which column of the list opens which page
            if p["kind"] == "list":
                for link in model["dom"]["links"]:
                    if (link.get("in_table") or link.get("in_repeat")) and link.get("href"):
                        target = self.key_to_id.get(type_key(normalize(link["href"])))
                        if target and target != pid:
                            col = link.get("header") or (f"col{link.get('column')}" if link.get("in_table")
                                                         else "item link")
                            entry["row_link"] = {"column": col, "goes_to": target}
                            break
            pages.append(entry)

            # edges: every link on this page that leads to another mapped page type
            seen = set()
            for link in model["dom"]["links"]:
                if not link.get("href"):
                    continue
                target = self.key_to_id.get(type_key(normalize(link["href"])))
                if not target or target == pid or target in seen:
                    continue
                seen.add(target)
                via = "row link" if (link.get("in_table") or link.get("in_repeat")) else \
                    "next page" if NEXT_TEXT.search(link.get("text") or "") else f"link '{link.get('text', '')[:40]}'"
                edges.append({"from": pid, "to": target, "via": via})

        unexplored = []
        for c in sorted(self._open(), key=lambda c: (not c["in_nav"], c["order"])):
            if c["label"] not in unexplored:
                unexplored.append(c["label"])
        notes = list(self.notes)
        if stop_reason == "budget" and unexplored:
            notes.append(f"Page budget ({self.cfg.page_budget}) reached with {len(unexplored)} links left unvisited")
        if self.risky:
            notes.append("Not followed (looked destructive): " + ", ".join(sorted({r['text'] for r in self.risky}))[:300])
        if self.blocked:
            notes.append(f"Blocked {len(self.blocked)} write request(s); the explorer is read-only")
        return {
            "site": f"{urlsplit(self.cfg.start_url).scheme}://{urlsplit(self.cfg.start_url).netloc}",
            "start_url": self.cfg.start_url,
            "pages": pages,
            "edges": edges,
            "unexplored": unexplored[:25],
            "notes": notes,
            "stats": {"page_types": len(pages), "steps": steps, "stop_reason": stop_reason,
                      "seconds": round(seconds, 1), "nemotron_calls": self.nemotron["calls"],
                      "nemotron_ms": self.nemotron["ms"], "nemotron_fallbacks": self.nemotron["fallbacks"],
                      "blocked_writes": len(self.blocked), "reader": self.reader.name, "planner": self.planner.name},
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


def explore(start_url, **kw):
    """One-call API: explore(url, page_budget=25, reader="nemotron", planner="nemotron") -> result dict."""
    return Explorer(ExploreConfig(start_url=start_url, **kw)).run()


def validate_site_map(sm):
    """Problems with a site map (empty list = matches format 7.2)."""
    problems = []
    if not isinstance(sm.get("site"), str) or not sm["site"].startswith("http"):
        problems.append("site must be the site's origin URL")
    pages = sm.get("pages")
    if not isinstance(pages, list) or not pages:
        return problems + ["pages must be a non-empty list"]
    ids = [p.get("id") for p in pages]
    if len(set(ids)) != len(ids):
        problems.append("duplicate page ids")
    for p in pages:
        for k in ("id", "url_pattern", "purpose", "kind"):
            if not p.get(k):
                problems.append(f"page {p.get('id')} missing {k}")
        if p.get("kind") not in VALID_KINDS:
            problems.append(f"page {p.get('id')} has bad kind {p.get('kind')}")
        if "row_link" in p and p["row_link"].get("goes_to") not in ids:
            problems.append(f"page {p['id']} row_link goes to unknown page")
    for e in sm.get("edges", []):
        if e.get("from") not in ids or e.get("to") not in ids:
            problems.append(f"edge {e} references unknown page")
    for k in ("edges", "unexplored", "notes"):
        if not isinstance(sm.get(k), list):
            problems.append(f"{k} must be a list")
    return problems
