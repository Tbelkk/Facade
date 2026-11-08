"""Recipe-driven extractor: run folder (site_map.json + recipes.json) -> every record, typed.

For every list recipe that has a detail link:
    list page -> read the recipe's table -> follow "next" until there is none
    -> open every detail page -> read the recipe's labels -> merge -> normalize types -> hash

No Nemotron per record (plan: "Nemotron learns once, code runs fast"). Read-only: a browser guard
aborts every non-GET request except the login submit. Re-logs in when the session expires.
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from explore.capture_dom import NEXT_TEXT
from explore.recipes import detect_format, field_name

_TXT = "const txt = (el) => (el ? (el.innerText || el.textContent || '') : '').replace(/\\s+/g, ' ').trim();"

READ_TABLES_JS = "() => {" + _TXT + r"""
  return Array.from(document.querySelectorAll('table')).map(t => Array.from(t.rows).map(r =>
    Array.from(r.children).map(c => { const a = c.querySelector('a[href]');
      return { text: txt(c), href: a ? a.href : null, th: c.tagName === 'TH' }; })));
}"""

READ_PAIRS_JS = "() => {" + _TXT + r"""
  const out = [];
  for (const t of document.querySelectorAll('table')) {
    if (t.querySelector('table')) continue;
    for (const r of t.rows) {
      const c = r.children;
      if (c.length < 2 || c.length > 4) continue;
      const label = txt(c[0]).replace(/\s*:\s*$/, '');
      if (!label || label.length >= 40) continue;
      const a = c[1].querySelector('a[href]');
      out.push({ label, text: txt(c[1]), href: a ? a.href : null });
    }
  }
  for (const dt of document.querySelectorAll('dl dt')) {
    const dd = dt.nextElementSibling, a = dd ? dd.querySelector('a[href]') : null;
    out.push({ label: txt(dt).replace(/\s*:\s*$/, ''), text: txt(dd), href: a ? a.href : null });
  }
  return out;
}"""

LINKS_JS = "() => {" + _TXT + "return Array.from(document.querySelectorAll('a[href]')).map(a => ({text: txt(a), href: a.href}));}"


def ids_from_url(pattern, url):
    """'/patients/{id}' + 'http://h/patients/42' -> {'id': '42'}. Query placeholders read from the query."""
    path_pat, _, query_pat = (pattern or "").partition("?")
    parts = urlsplit(url)
    rx = "^" + re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(path_pat)) + "$"
    m = re.match(rx, parts.path)
    if not m:
        return None
    out = dict(m.groupdict())
    q = dict(parse_qsl(parts.query))
    for k, name in re.findall(r"(\w+)=\{(\w+)\}", query_pat):
        if k in q:
            out[name] = q[k]
    return out


def normalize(value, typ):
    """Legacy display string -> clean typed value for the database/API."""
    if value is None:
        return None
    v = str(value).strip()
    if v == "":
        return None
    t, fmt = (typ or {}).get("type"), (typ or {}).get("format")
    try:
        if t == "date" and fmt == "MM/DD/YYYY":
            m, d, y = v.split("/")
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        if t == "money":
            return float(re.sub(r"[^\d.\-]", "", v))
        if t == "number":
            n = v.replace(",", "")
            return int(n) if re.fullmatch(r"-?\d+", n) else float(n)
    except ValueError:
        return v
    return v


def record_hash(data):
    return hashlib.sha1(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


class Extractor:
    def __init__(self, run_dir, login="none", username="", password="", headless=True, limit=0,
                 nav_timeout_ms=15000, out_dir=None, log=None):
        self.run_dir = Path(run_dir)
        self.site_map = json.loads((self.run_dir / "site_map.json").read_text(encoding="utf-8"))
        self.recipes = json.loads((self.run_dir / "recipes.json").read_text(encoding="utf-8"))
        self.by_id = {r["page_id"]: r for r in self.recipes["recipes"]}
        self.login_mode, self.username, self.password = login, username, password
        self.headless, self.limit, self.nav_timeout_ms = headless, limit, nav_timeout_ms
        self.out_dir = Path(out_dir) if out_dir else self.run_dir / "extract"
        self.events, self.jobs, self.records, self.duplicates = [], [], [], []
        self.relogins = 0
        self._allow_write = False
        self._print = log if log is not None else (os.getenv("FACADE_QUIET") != "1")

    # ------------------------------------------------------------ logging / jobs

    def log(self, message, level="info", **data):
        self.events.append({"ts": time.time(), "actor": "operator", "level": level, "message": message, "data": data})
        if self._print:
            print(f"[extract] {message}", flush=True)

    # ------------------------------------------------------------ browser

    def _guard(self, route, request):
        if request.method in ("GET", "HEAD", "OPTIONS") or self._allow_write:
            return route.continue_()
        self.log(f"Blocked a {request.method} request (extraction is read-only): {request.url}", level="warn")
        route.abort("blockedbyclient")

    def _login(self, page):
        if self.login_mode == "none":
            raise RuntimeError("The site asks for a login: re-run with --login env or --login manual")
        if self.login_mode == "manual":
            input("\n>>> Log in in the browser window, then press Enter to continue... ")
        else:
            pw_box = page.locator("input[type=password]").first
            form = pw_box.locator("xpath=ancestor::form[1]")
            scope = form if form.count() else page
            scope.locator("input:not([type]), input[type=text], input[type=email]").first.fill(self.username)
            pw_box.fill(self.password)
            self._allow_write = True
            try:
                with page.expect_navigation(timeout=self.nav_timeout_ms):
                    btn = scope.locator("button[type=submit], input[type=submit], button:not([type])").first
                    btn.click() if btn.count() else pw_box.press("Enter")
            finally:
                self._allow_write = False
        page.wait_for_load_state("domcontentloaded")
        if page.locator("input[type=password]").count():
            raise RuntimeError("Login did not work: the page still asks for a password")

    def _goto(self, page, url):
        page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
        if page.locator("input[type=password]").count():
            if getattr(self, "_logged_in", False):
                self.relogins += 1
                self.log("Session expired (login page shown). Logging in again and resuming.", level="warn",
                         action="relogin", url=url)
            else:
                self.log("Logging in", action="login", mode=self.login_mode)
            self._login(page)
            self._logged_in = True
            page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)

    # ------------------------------------------------------------ reading

    @staticmethod
    def _pick_table(tables, recipe_table):
        """The recipe's table by index; if its headers moved, find the table with the same headers."""
        want = recipe_table.get("headers") or []

        def headers_of(t):
            return [c["text"] for c in t[0]] if t else []
        idx = recipe_table["index"]
        if 0 <= idx < len(tables) and (not want or headers_of(tables[idx]) == want):
            return tables[idx]
        for t in tables:
            if want and headers_of(t) == want:
                return t
        return None

    def _read_list_page(self, page, recipe):
        table = self._pick_table(page.evaluate(READ_TABLES_JS), recipe["table"])
        if table is None:
            self.log(f"{recipe['page_id']}: table not found on {page.url}", level="warn")
            return []
        rows = table[1:] if recipe["table"].get("header_row") else table
        dl = recipe.get("detail_link") or {}
        out = []
        for r in rows:
            if not r or all(c["th"] for c in r):
                continue
            row = {"_cells": {c["index"]: (r[c["index"]]["text"] if c["index"] < len(r) else "")
                              for c in recipe["table"]["columns"]}}
            ci = dl.get("column_index")
            if ci is not None and ci < len(r) and r[ci]["href"]:
                row["_href"] = r[ci]["href"]
            out.append(row)
        return out

    @staticmethod
    def _next_url(page, recipe, seen):
        np = recipe.get("next_page")
        if not np:
            return None
        links = page.evaluate(LINKS_JS)
        name = (np.get("link") or {}).get("name", "")
        cand = [l for l in links if l["text"] == name] or [l for l in links if NEXT_TEXT.search(l["text"] or "")]
        for l in cand:
            if l["href"] and l["href"] not in seen:
                return l["href"]
        return None

    # ------------------------------------------------------------ one entity

    def extract_entity(self, page, lst):
        entity = lst.get("entity") or lst["page_id"]
        dl = lst.get("detail_link") or {}
        detail = self.by_id.get(dl.get("goes_to")) if dl else None
        detail_fields = {l["field"] for l in detail["labels"]} if detail else set()
        job = {"kind": "extract", "entity": entity, "status": "running", "done": 0, "total": 0,
               "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.jobs.append(job)
        self.log(f"Extracting {entity}: list {lst['url_pattern']}" + (f" -> detail {dl['url_pattern']}" if dl else ""),
                 action="extract_start", entity=entity)

        # 1. every list page
        rows, seen, url, pages = [], set(), lst["example_url"], 0
        while url and url not in seen and pages < 1000:
            seen.add(url)
            self._goto(page, url)
            got = self._read_list_page(page, lst)
            rows += got
            pages += 1
            job["total"] = len(rows)
            self.log(f"{entity}: list page {pages}: {len(got)} rows", action="list_page", entity=entity,
                     page=pages, rows=len(got))
            if self.limit and len(rows) >= self.limit:
                rows = rows[:self.limit]
                break
            url = self._next_url(page, lst, seen)
        job["total"] = len(rows)

        # 2. every detail page
        raw = []
        for row in rows:
            data, refs = {}, {}
            for col in lst["table"]["columns"]:
                if col["field"] in detail_fields:
                    continue  # the detail page has this field; it wins
                text = row["_cells"].get(col["index"], "")
                if col.get("split"):
                    m = re.match(col["split"]["regex"], text or "")
                    if m:
                        for k, v in zip(col["split"]["into"], m.groups()):
                            data[k] = v
                        continue
                data[col["field"]] = text
            legacy_id, src = None, row.get("_href")
            if src and dl:
                ids = ids_from_url(dl["url_pattern"], src) or {}
                legacy_id = ids.get(dl.get("id_param"))
            if src and detail:
                self._goto(page, src)
                pairs = {p["label"].lower(): p for p in page.evaluate(READ_PAIRS_JS)}
                for lab in detail["labels"]:
                    p = pairs.get(lab["label"].lower())
                    if p is None:
                        continue
                    data[lab["field"]] = p["text"]
                    if p.get("href"):
                        ref = self._ref_of(p["href"])
                        if ref:
                            refs[lab["field"]] = ref
            if legacy_id is None:
                legacy_id = record_hash(data)
            raw.append({"legacy_id": str(legacy_id), "data": data, "refs": refs, "source_url": src})
            job["done"] += 1
        job["status"] = "done"
        self.log(f"{entity}: {len(raw)} records read from {pages} list page(s)", action="extract_done",
                 entity=entity, records=len(raw), pages=pages)
        return entity, raw

    def _ref_of(self, href):
        """A link on a detail page that points at another entity's detail page -> (entity, legacy_id)."""
        for r in self.recipes["recipes"]:
            if r["kind"] != "detail":
                continue
            ids = ids_from_url(r["url_pattern"], href)
            if ids and r.get("id_param") in ids:
                return {"entity": r.get("entity"), "legacy_id": ids[r["id_param"]]}
        return None

    # ------------------------------------------------------------ typing, hashing, duplicates

    @staticmethod
    def infer_types(raw):
        """Field type from ALL extracted values (sturdier than the explorer's single sample)."""
        fields = []
        for r in raw:
            for k in r["data"]:
                if k not in fields:
                    fields.append(k)
        types = {}
        for f in fields:
            vals = [r["data"].get(f) for r in raw if r["data"].get(f)]
            types[f] = detect_format(vals) or {"type": "string"}
            refs = [r["refs"][f] for r in raw if f in r["refs"]]
            if refs and len(refs) == len(vals):
                types[f] = {"type": "ref", "to": refs[0]["entity"]}
        return types

    def finish_entity(self, entity, raw, previous):
        types = self.infer_types(raw)
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        out = []
        for r in raw:
            data = {}
            for k, v in r["data"].items():
                t = types.get(k, {})
                if t.get("type") == "ref":
                    data[k] = v.strip() if v and v.strip() else None
                    data[f"{k}_id"] = r["refs"].get(k, {}).get("legacy_id")
                else:
                    data[k] = normalize(v, t)
            h = record_hash(data)
            old = previous.get((entity, r["legacy_id"]))
            change = "new" if old is None else ("unchanged" if old == h else "changed")
            out.append({"entity": entity, "legacy_id": r["legacy_id"], "data": data, "hash": h, "change": change,
                        "source_url": r["source_url"], "extracted_at": now})
        self._flag_duplicates(entity, out, types)
        return out, types

    def _flag_duplicates(self, entity, recs, types):
        """Same name(s) + same date(s) = possible duplicate. Flagged, never merged."""
        key_fields = [f for f in types if "name" in f and types[f]["type"] == "string"]
        key_fields += [f for f in types if types[f]["type"] == "date"]
        if not any("name" in f for f in key_fields) or len(key_fields) < 2:
            return
        groups = {}
        for r in recs:
            key = tuple(str(r["data"].get(f) or "").strip().lower() for f in key_fields)
            if all(key):
                groups.setdefault(key, []).append(r["legacy_id"])
        for key, ids in groups.items():
            if len(ids) > 1:
                d = {"entity": entity, "match": dict(zip(key_fields, key)), "legacy_ids": ids}
                self.duplicates.append(d)
                self.log(f"Possible duplicate {entity}: {ids} share {d['match']}", level="warn",
                         action="duplicate", **d)

    # ------------------------------------------------------------ run

    def _previous_hashes(self):
        p = self.out_dir / "records.jsonl"
        out = {}
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    out[(r["entity"], r["legacy_id"])] = r["hash"]
        return out

    def run(self):
        from playwright.sync_api import sync_playwright

        from . import spacetime_export

        t0 = time.time()
        previous = self._previous_hashes()
        lists = [r for r in self.recipes["recipes"] if r["kind"] == "list" and r.get("table")]
        all_types = {}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            ctx = browser.new_context()
            ctx.route("**/*", self._guard)
            page = ctx.new_page()
            page.on("dialog", lambda d: d.dismiss())
            try:
                self._goto(page, self.site_map.get("start_url") or self.site_map["site"])
                done_entities = set()
                for lst in lists:
                    ent = lst.get("entity") or lst["page_id"]
                    if ent in done_entities:
                        continue  # two list pages for one entity: the first one is enough
                    entity, raw = self.extract_entity(page, lst)
                    recs, types = self.finish_entity(entity, raw, previous)
                    self.records += recs
                    all_types[entity] = types
                    done_entities.add(ent)
            finally:
                browser.close()
        changes = {c: sum(1 for r in self.records if r["change"] == c) for c in ("new", "changed", "unchanged")}
        self.log(f"Done: {len(self.records)} records ({changes}), {self.relogins} re-login(s), "
                 f"{len(self.duplicates)} possible duplicate group(s) in {time.time() - t0:.1f}s",
                 action="done", records=len(self.records), relogins=self.relogins, **changes)
        return spacetime_export.write(self, all_types)
