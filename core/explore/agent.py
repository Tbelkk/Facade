"""Facade extraction agent: give it a URL, a Nemotron agent explores the site and pulls the data out.

Usage (from core/, venv active, NVIDIA key in core/.env):
    python -m explore.agent https://news.ycombinator.com
    python -m explore.agent http://localhost:5005 --pages 30
    python -m explore.agent https://example.com --vision        # also send screenshots (Nano Omni)
    python -m explore.agent <url> --login                       # log in by hand first, session reused

How it works (one loop per page):
    1. capture the page (read-only): tables, forms, links, pagination, messages, accessibility tree
    2. Nemotron decides: what kind of page is this, what entity, how do table columns map to fields,
       what's the record on a detail page, what rules are visible, which pages to visit next
    3. code does the bulk work fast: turns EVERY table row into a record, follows pagination
    4. repeat until the page budget is used or Nemotron says the site is covered

Never submits forms, never follows logout/delete/remove links.

Output: cache/extract/<run>/
    records/<Entity>.jsonl + .csv     the extracted data
    data_model.json                   entities, fields (type, required, allowed values), rules
    site_map.json                     pages visited: type, purpose, entity, url pattern, links followed
    run_log.jsonl                     every step + every Nemotron call (for the Console / judges)
"""
import argparse
import csv
import hashlib
import json
import os
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from ingest import nemotron
from ingest.paths import CACHE_DIR, PROMPTS_DIR

from .capture_web import AUTH_FILE, WEB_DIR, capture_page, open_browser, url_pattern

PROMPT = PROMPTS_DIR / "extract_v1.md"
# Never follow these: links that DO something (many sites perform actions through plain links),
# and account pages that hold no business data.
UNSAFE = re.compile(
    r"log\s*out|sign\s*out|logoff|delete|remove|destroy|purge|void|cancel|unsubscribe|reset"
    r"|vote|upvote|downvote|flag|hide|unhide|favorite|fave|like|follow|subscribe|approve|reject|archive"
    r"|[?&](how|action|act|op|do|cmd|method)=", re.I)
# Note: viewing /edit or /new pages is fine (they only SHOW a form, and we never submit).
NO_DATA = re.compile(r"log\s*in|sign\s*in|signin|login|register|sign\s*up|signup|forgot|password|captcha|/auth", re.I)
SKIP_EXT = re.compile(r"\.(pdf|zip|jpg|jpeg|png|gif|docx?|xlsx?|csv|mp4|mp3)(\?|$)", re.I)


def page_context(snap, learned, visited_patterns):
    w = snap["web"]
    links = [{"text": l["text"], "url": l["href"]} for l in w["links"]
             if l["same_site"] and not UNSAFE.search(l["text"] + " " + l["href"])
             and not NO_DATA.search(l["text"] + " " + l["href"])]
    seen_links, uniq = set(), []
    for l in links:  # one entry per distinct page type keeps the prompt short
        k = url_pattern(l["url"])
        if k not in seen_links:
            seen_links.add(k)
            uniq.append(l)
    links = uniq[:40]
    ctx = {
        "url": w["url"], "title": w["title"], "messages": w["alerts"],
        "tables": [{"table_index": i, "headers": t["headers"], "has_header_row": t.get("has_header"),
                    "rows_per_record": t.get("rows_per_record", 1), "record_count": t["row_count"],
                    # each record as {header: value} so column names can't be miscounted
                    "sample_records": [dict(zip(t["headers"], row)) for row in t["sample_rows"][:3]],
                    "sample_record_links": t.get("sample_links", [])[:2]}
                   for i, t in enumerate(w["tables"])],
        "forms": [{"action": f["action"], "method": f["method"], "submit": f["submit"],
                   "fields": [{k: x[k] for k in ("label", "name", "type", "required", "options", "pattern", "maxlength")}
                              for x in f["fields"]]} for f in w["forms"]],
        "label_values": w.get("label_values", [])[:60],
        "pagination": {k: (v or {}).get("text") for k, v in (w["pagination"] or {}).items()},
        "same_site_links": links,
        "learned_so_far": {"entities": {e: sorted(v["fields"]) for e, v in learned.items()},
                           "page_types_visited": sorted(visited_patterns)},
    }
    return (json.dumps(ctx, ensure_ascii=False, separators=(",", ":"))[:9000]
            + "\n\nAccessibility tree (truncated):\n" + w["aria_yaml"][:2500])


def problems(a, snap):
    """Check Nemotron's answer against the real page. Returns a list of problems (empty = OK)."""
    out, tables = [], snap["web"]["tables"]
    if not isinstance(a, dict) or not a.get("page_type"):
        return ["the answer is not the JSON object described in the instructions (page_type is missing); "
                "return that full object"]
    tm = a.get("table_mapping")
    if a.get("page_type") == "list" and tables and not isinstance(tm, dict):
        out.append("this is a list page with a data table but table_mapping is missing")
    if isinstance(tm, dict):
        if not a.get("entity"):
            out.append('"entity" is missing: give the singular PascalCase name of what each table record is (e.g. Patient, Story)')
        ti = tm.get("table_index", 0) if isinstance(tm.get("table_index"), int) else 0
        t = tables[ti] if 0 <= ti < len(tables) else (tables[0] if tables else None)
        cols = tm.get("columns") if isinstance(tm.get("columns"), dict) else {}
        if t:
            bad = [h for h in cols if h not in t["headers"]]
            if bad:
                out.append(f"columns {bad} do not exist; the table's headers are exactly {t['headers']}")
            mapped = [h for h, f in cols.items() if f and h in t["headers"]]
            if not mapped and not tm.get("split"):
                out.append("no column is mapped to a field")
            # a mapped column that is empty in every sample is probably miscounted
            empty = [h for h in mapped if all(not dict(zip(t["headers"], r)).get(h) for r in t["sample_rows"][:5])]
            if empty:
                out.append(f"columns {empty} are empty in every sample record; check which column holds which value")
    return out


def analyze(snap, learned, visited_patterns, vision=False, budget=None):
    content = [{"type": "text", "text": page_context(snap, learned, visited_patterns)}]
    model = nemotron.MODEL_AGENT
    if vision:
        part, _ = nemotron.image_part(snap["screenshot_path"], max_width=1280)
        content.append(part)
        model = nemotron.MODEL_VISION
    messages = [{"role": "system", "content": PROMPT.read_text(encoding="utf-8")},
                {"role": "user", "content": content}]
    res = nemotron.chat(messages, purpose="extract_page", model=model, budget=budget, answer_tokens=2500)
    try:
        a = nemotron.extract_json(res["text"])
        issues = problems(a, snap)
        if not issues:
            return a, res["ms"], None
        # one repair round: tell Nemotron exactly what is wrong with its answer
        messages += [{"role": "assistant", "content": res["text"][:4000]},
                     {"role": "user", "content": "Your answer has problems:\n- " + "\n- ".join(issues)
                      + "\nReturn the corrected full JSON object only."}]
        res2 = nemotron.chat(messages, purpose="extract_page_fix", model=model, budget=budget, answer_tokens=2500)
        try:
            a2 = nemotron.extract_json(res2["text"])
        except ValueError:
            a2 = None
        a = a2 if isinstance(a2, dict) and len(problems(a2, snap)) < len(issues) else a
        if not isinstance(a, dict) or not a.get("page_type"):
            return None, res["ms"] + res2["ms"], "no usable answer: " + (res2["text"] or res["text"])[:200]
        a["_problems"] = problems(a, snap)
        return a, res["ms"] + res2["ms"], None
    except ValueError as e:  # one repair attempt
        messages += [{"role": "assistant", "content": res["text"][:4000]},
                     {"role": "user", "content": f"That was not valid JSON ({e}). Return only the JSON object."}]
        res2 = nemotron.chat(messages, purpose="extract_page_repair", model=model, budget=budget, answer_tokens=4000)
        try:
            return nemotron.extract_json(res2["text"]), res["ms"] + res2["ms"], None
        except ValueError as e2:
            return None, res["ms"] + res2["ms"], str(e2)



# ---------- packed cells: Nemotron writes a regex, code tests it on every row, Nemotron repairs it once ----------
RANK = re.compile(r"^\s*\d+\.\s*$")


def _match_rate(rx, values):
    """Score 0..1: in how many cells it matches, weighted by how much of the cell the match covers
    (a regex that only grabs '120 points' out of a long cell is incomplete and gets repaired)."""
    vals = [v for v in values if v]
    if not vals:
        return 0.0
    score = 0.0
    for v in vals:
        m = rx.search(v)
        if m and any(m.groupdict().values()):
            score += min(1.0, (m.end() - m.start()) / max(1, len(v)) * 1.5)
    return score / len(vals)


def _compile(rx):
    try:
        return re.compile(rx) if isinstance(rx, str) and "(?P<" in rx else None
    except re.error:
        return None


def _looks_packed(values):
    """Several values in one cell: long-ish text with numbers in most rows, e.g. '40 points by bob 2 hours ago'."""
    vals = [v for v in values if v][:30]
    if len(vals) < 3:
        return False
    digits = sum(1 for v in vals if re.search(r"\d", v)) / len(vals)
    words = sum(len(v.split()) for v in vals) / len(vals)
    return digits >= 0.8 and words >= 4


def ask_split(header, values, current=None, failures=None, budget=None):
    """Focused Nemotron call: one regex with named groups for one column."""
    sample = [v for v in values if v][:10]
    msg = ("These are values of one table column from a legacy website. Each cell packs several data values.\n"
           "Write ONE Python regular expression with named groups (?P<snake_case_name>...) that extracts every "
           "data value from EVERY sample. Make optional parts optional with (?:...)?. Ignore UI words like "
           "'hide', 'flag', 'reply'. If the column is a single value, return null.\n"
           'Return only JSON: {"regex": "<regex or null>"}\n\nSamples:\n' + "\n".join(f"- {v}" for v in sample))
    if current:
        msg += f"\n\nThe previous regex {current!r} failed on:\n" + "\n".join(f"- {v}" for v in (failures or [])[:6])
    res = nemotron.chat([{"role": "user", "content": msg}], purpose="split_column",
                        model=nemotron.MODEL_AGENT, budget=budget or 512, answer_tokens=600)
    try:
        return nemotron.extract_json(res["text"]).get("regex"), res["ms"]
    except (ValueError, AttributeError):
        return None, res["ms"]


def resolve_splits(tm, t, run, budget=None):
    """Turn whatever Nemotron gave for 'split' into {column_index: regex}, verified against all rows.
    Cached on the mapping (tm['_splits']) so pages that reuse it don't call Nemotron again."""
    cols = list(zip(*[r + [""] * (len(t["headers"]) - len(r)) for r in t["rows"]])) if t["rows"] else []
    col = lambda i: list(cols[i]) if i < len(cols) else []
    if "_splits" in tm:
        # reused mapping: re-check the regex on THIS page (new pages show new formats, e.g. "1 point",
        # "5 minutes ago", "discuss"); if it misses, repair it with these rows plus earlier samples
        out, seen = {}, tm.setdefault("_split_samples", {})
        for h, rx in tm["_splits"].items():
            if h not in t["headers"]:
                continue
            i = t["headers"].index(h)
            c = re.compile(rx)
            values = col(i)
            rate = _match_rate(c, values)
            if rate < 0.75:
                fails = [v for v in values if v and _match_rate(c, [v]) < 0.75]
                pool = (seen.get(h, []) + fails)[-20:]
                new_rx, ms = ask_split(h, pool, rx, fails, budget)
                c2 = _compile(new_rx)
                old_all, new_all = _match_rate(c, pool + values), (_match_rate(c2, pool + values) if c2 else 0)
                run.log("split_column", column=h, first=rx, first_rate=round(old_all, 2), repaired=new_rx,
                        repaired_rate=round(new_all, 2), nemotron_ms=ms, reason="reused mapping missed rows")
                if c2 and new_all > old_all:
                    c = c2
                    tm["_splits"][h] = c2.pattern
                seen[h] = pool
            out[i] = c
        return out
    given = tm.get("split")
    cand = {}  # index -> regex string
    if isinstance(given, dict):
        by_field = {f: h for h, f in (tm.get("columns") or {}).items() if f}
        for h, rx in given.items():
            h = h if h in t["headers"] else by_field.get(h)  # Nemotron sometimes keys by field name
            if h in t["headers"]:
                cand[t["headers"].index(h)] = rx
    elif isinstance(given, list):
        for g in given:
            if isinstance(g, dict) and g.get("column") in t["headers"]:
                cand[t["headers"].index(g["column"])] = g.get("regex")
    elif isinstance(given, str) and _compile(given):  # no column named: use the column it matches best
        best = max(range(len(cols)), key=lambda i: _match_rate(_compile(given), col(i)), default=None)
        if best is not None:
            cand[best] = given
    mapped = {i for i, h in enumerate(t["headers"]) if (tm.get("columns") or {}).get(h)}
    for i in range(len(cols)):  # packed columns Nemotron didn't split
        if i not in cand and _looks_packed(col(i)) and not RANK.match(col(i)[0] or ""):
            if i not in mapped or len((col(i)[0] or "").split()) >= 4:
                cand[i] = None
    out, total_ms = {}, 0
    for i, rx in cand.items():
        values = col(i)
        c = _compile(rx)
        rate = _match_rate(c, values) if c else 0.0
        if rate < 0.75:  # write or repair it once with a focused call
            fails = [v for v in values if v and not (c and c.search(v))]
            new_rx, ms = ask_split(t["headers"][i], values, rx, fails, budget)
            total_ms += ms
            c2 = _compile(new_rx)
            r2 = _match_rate(c2, values) if c2 else 0.0
            run.log("split_column", column=t["headers"][i], first=rx, first_rate=round(rate, 2),
                    repaired=new_rx, repaired_rate=round(r2, 2), nemotron_ms=ms)
            if r2 > rate:
                c, rate = c2, r2
        if c and rate >= 0.5:
            out[i] = c
    tm["_splits"] = {t["headers"][i]: c.pattern for i, c in out.items()}
    tm["_split_samples"] = {t["headers"][i]: [v for v in col(i) if v][:10] for i in out}
    return out

def structure_sig(snap):
    """Pages with the same data-table headers or the same detail labels are the same kind of page."""
    w = snap["web"]
    if w.get("tables"):
        t = w["tables"][0]
        return f"T{t.get('rows_per_record', 1)}:" + "|".join(t["headers"])
    labels = [k for k, _ in w.get("label_values", [])]
    if len(labels) >= 3:
        return "D:" + "|".join(labels[:12])
    return None


def snake(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:40] or "field"


class Run:
    def __init__(self, start_url):
        self.dir = CACHE_DIR / "extract" / time.strftime("%Y%m%d-%H%M%S")
        (self.dir / "records").mkdir(parents=True, exist_ok=True)
        self.start = start_url
        self.host = urlparse(start_url).netloc
        self.learned = {}      # entity -> {"fields": {name: spec}, "rules": set(), "count": int}
        self.records = {}      # entity -> {record_key: dict}
        self.pages = []        # site map entries
        self.log_f = (self.dir / "run_log.jsonl").open("a", encoding="utf-8")

    def log(self, kind, **data):
        row = {"ts": time.time(), "kind": kind, **data}
        self.log_f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.log_f.flush()

    def learn(self, entity, fields, rules):
        e = self.learned.setdefault(entity, {"fields": {}, "rules": set()})
        for f in fields or []:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            name = snake(f["name"])
            spec = e["fields"].setdefault(name, {"label": f.get("label") or f["name"], "type": "string", "required": False})
            if f.get("type") and f["type"] != "string":
                spec["type"] = f["type"]  # keep the most specific type seen
            if f.get("label") and spec["label"] == name:
                spec["label"] = f["label"]
            spec["required"] = spec["required"] or bool(f.get("required"))
            if f.get("values"):
                spec["values"] = sorted(set(spec.get("values", [])) | set(map(str, f["values"])))
        for r in rules or []:
            e["rules"].add(str(r)[:200])

    def add_record(self, entity, rec, key_hint):
        rec = {snake(k): v for k, v in rec.items() if v not in (None, "")}
        if not rec:
            return False
        key = key_hint or hashlib.sha1(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:12]
        bucket = self.records.setdefault(entity, {})
        merged = {**bucket.get(key, {}), **rec}   # detail pages enrich rows from list pages
        new = key not in bucket
        bucket[key] = merged
        e = self.learned.setdefault(entity, {"fields": {}, "rules": set()})
        for k in rec:
            e["fields"].setdefault(k, {"label": k, "type": "string", "required": False})
        return new

    def typed(self, entity, rec):
        """Store numbers as numbers (per the learned field types) so the database/API get real types."""
        fields = self.learned.get(entity, {}).get("fields", {})
        out = {}
        for k, v in rec.items():
            t = (fields.get(k) or {}).get("type")
            if isinstance(v, str) and t in ("int", "integer", "number", "float"):
                num = re.sub(r"[^\d.\-]", "", v)
                try:
                    v = int(num) if t in ("int", "integer") or (num and "." not in num) else float(num)
                except ValueError:
                    pass
            out[k] = v
        return out

    def save(self):
        for entity, bucket in self.records.items():
            rows = [{"_key": k, **self.typed(entity, v)} for k, v in bucket.items()]
            with (self.dir / "records" / f"{entity}.jsonl").open("w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            cols = ["_key"] + sorted({c for r in rows for c in r if c != "_key"})
            with (self.dir / "records" / f"{entity}.csv").open("w", newline="", encoding="utf-8") as f:
                wr = csv.DictWriter(f, fieldnames=cols)
                wr.writeheader()
                wr.writerows(rows)
        model = {"site": self.start, "entities": [
            {"name": n, "record_count": len(self.records.get(n, {})),
             "fields": [{"name": k, **v} for k, v in e["fields"].items()], "rules": sorted(e["rules"])}
            for n, e in self.learned.items()]}
        (self.dir / "data_model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.dir / "site_map.json").write_text(json.dumps({"site": self.start, "pages": self.pages}, indent=2,
                                                           ensure_ascii=False), encoding="utf-8")


def same_site(url, host):
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc == host


# Safety ceilings only (protect against infinite sites); the agent normally stops on its own first.
SAFETY_PAGES = int(os.getenv("AGENT_SAFETY_PAGES", "1000"))
SAFETY_MINUTES = float(os.getenv("AGENT_SAFETY_MINUTES", "30"))


def run(start_url, max_pages=None, vision=False, login=False, headed=False, budget=None, full=False):
    """Explore + extract until there is nothing new left:
    - Nemotron's suggested links are followed until no unknown page types remain (it can also say done)
    - every list is paged until there is no next link, or a page adds no new records
    full=False (learn mode, the default): learn every page type and check paging works on each list
    (page 2), then stop. Fast enough for a live demo. The Operator does the full extraction from what
    was learned. full=True: also page through every list to the end (until the Operator exists).
    max_pages is only for quick tests; the workflow calls run(url) with no limits."""
    from playwright.sync_api import sync_playwright
    limit = max_pages or SAFETY_PAGES
    t_start = time.time()
    stop_reason = "nothing new left to explore"

    r = Run(start_url)
    queue = deque([(start_url, "start")])
    seen_urls, patterns, signatures = set(), {}, {}
    queued_detail, paged_lists = set(), {}   # detail page types already queued; pages followed per list
    print(f"Facade agent → {start_url}")
    print(f"model={nemotron.MODEL_VISION if vision else nemotron.MODEL_AGENT}  page limit={limit if max_pages else 'auto'}  output={r.dir}\n")

    with sync_playwright() as p:
        browser, ctx = open_browser(p, headed=headed or login)
        page = ctx.new_page()
        if login:
            page.goto(start_url)
            input("Log in in the browser window, then press Enter here... ")
            WEB_DIR.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(AUTH_FILE))

        visited = 0
        while queue:
            if visited >= limit:
                stop_reason = f"page limit ({limit})"
                break
            if (time.time() - t_start) / 60 > SAFETY_MINUTES:
                stop_reason = f"safety time limit ({SAFETY_MINUTES:g} min)"
                break
            url, why = queue.popleft()
            norm = url.split("#")[0]
            if norm in seen_urls or not same_site(norm, r.host) or UNSAFE.search(norm) or SKIP_EXT.search(norm) \
                    or (not why.startswith("start") and NO_DATA.search(norm)):
                continue
            seen_urls.add(norm)
            try:
                page.goto(norm, wait_until="domcontentloaded", timeout=20000)
                try:
                    page.wait_for_load_state("networkidle", timeout=4000)
                except Exception:
                    pass
                snap = capture_page(page)
            except Exception as e:
                r.log("error", url=norm, error=str(e)[:200])
                print(f"  ✗ {norm}: {str(e)[:80]}")
                continue
            visited += 1
            pat = snap["web"]["url_pattern"]
            is_pagination = why == "pagination"

            # Already understood this page type? Reuse the mapping, skip the AI call (learn once, run fast).
            # Match by URL pattern OR by structure (same table headers / same detail labels).
            sig = structure_sig(snap)
            known = patterns.get(pat) or (signatures.get(sig) if sig else None)
            if known and (is_pagination or known.get("page_type") in ("list", "detail")):
                a, ms, err = known, 0, None
            else:
                try:
                    a, ms, err = analyze(snap, r.learned, set(patterns), vision=vision, budget=budget)
                except RuntimeError as e:
                    a, ms, err = None, 0, str(e)
            if not a:
                r.log("analyze_failed", url=norm, error=err)
                print(f"  ✗ [{visited}] {norm}  Nemotron: {(err or '')[:100]}")
                if why == "start":  # the start page is the only way in: try it once more
                    seen_urls.discard(norm)
                    queue.appendleft((norm, "start_retry"))
                continue
            if a.get("_problems"):
                r.log("mapping_problems", url=norm, problems=a["_problems"])
                print(f"     ! mapping problems (not reused): {'; '.join(a['_problems'])[:120]}")
            if not known and not a.get("_problems"):
                patterns[pat] = a
                if sig:
                    signatures[sig] = a
            entity = a.get("entity") or None
            new_records = 0

            # table rows -> records, done by code for every row
            tm = a.get("table_mapping") or None
            tables = snap["web"]["tables"]
            if entity and isinstance(tm, dict) and isinstance(tm.get("columns"), dict) and tables:
                ti = tm.get("table_index", 0) if isinstance(tm.get("table_index"), int) else 0
                t = tables[ti] if 0 <= ti < len(tables) else tables[0]
                col_idx = {i: snake(tm["columns"][h]) for i, h in enumerate(t["headers"])
                           if h in tm["columns"] and tm["columns"][h]}
                pat_link = tm.get("detail_link_pattern") if isinstance(tm.get("detail_link_pattern"), str) else None
                splits = resolve_splits(tm, t, r, budget)  # packed cells -> several fields
                for i in splits:
                    col_idx.pop(i, None)  # store the split fields, not the packed text
                for i in list(col_idx):   # rank numbers like "1." are not data
                    vals = [row[i] for row in t["rows"][:20] if i < len(row) and row[i]]
                    if vals and all(RANK.match(v) for v in vals):
                        col_idx.pop(i)
                for ri, row in enumerate(t["rows"]):
                    rec = {f: row[i] for i, f in col_idx.items() if i < len(row)}
                    for i, rx in splits.items():
                        m = rx.search(row[i]) if i < len(row) else None
                        if m:
                            rec.update({snake(k): v.strip() for k, v in m.groupdict().items() if v})
                    links = t["row_links"][ri] if ri < len(t.get("row_links", [])) else []
                    detail = None
                    if pat_link:  # the record's own detail page = the link whose URL contains the pattern
                        detail = next((h for _, h in links if pat_link in h and not UNSAFE.search(h)), None)
                    new_records += r.add_record(entity, rec, detail)
                    dp = url_pattern(detail) if detail else None
                    if dp and same_site(detail, r.host) and dp not in patterns and dp not in queued_detail:
                        queued_detail.add(dp)
                        queue.appendleft((detail, "detail"))  # learn the detail layout from ONE example

            # detail page record: read values from THIS page using the learned label->field mapping
            dm = a.get("detail_mapping")
            lv = {}
            for k, v in snap["web"].get("label_values", []):
                lv.setdefault(k, v)
            rec = {f: lv[lbl] for lbl, f in dm.items() if lbl in lv} if isinstance(dm, dict) else {}
            if not rec and not known and isinstance(a.get("detail_record"), dict):
                rec = a["detail_record"]  # backup only for the page Nemotron actually read
            if entity and rec:
                new_records += r.add_record(entity, rec, norm)

            if entity:
                r.learn(entity, a.get("fields"), a.get("rules"))

            # pagination: code follows it, the agent decided it's a list worth paging
            nxt = (snap["web"]["pagination"] or {}).get("next")
            # keep paging while pages still give new records (stops on the last page or on repeats)
            list_key = urlparse(norm).path or "/"
            followed = paged_lists.get(list_key, 0)
            if nxt and a.get("page_type") == "list" and (new_records > 0 or not is_pagination) \
                    and (full or followed < 1):   # learn mode: page 2 proves paging works, that's enough
                paged_lists[list_key] = followed + 1
                queue.appendleft((nxt["href"], "pagination"))

            # agent's choice of where to go next
            for n in (a.get("next") or [])[:5] if not known else []:
                u = n.get("url") if isinstance(n, dict) else None
                if u and same_site(u, r.host) and not UNSAFE.search(u) and not NO_DATA.search(u):
                    queue.append((u, (n.get("why") or "agent")[:80]))

            r.pages.append({"url": norm, "url_pattern": pat, "page_type": a.get("page_type"), "entity": entity,
                            "next_page_link": (nxt or {}).get("text"),
                            "purpose": a.get("purpose"), "reached_by": why, "nemotron_ms": ms,
                            "records_new": new_records})
            r.log("page", url=norm, page_type=a.get("page_type"), entity=entity, purpose=a.get("purpose"),
                  reached_by=why, nemotron_ms=ms, records_new=new_records, reused_mapping=bool(known),
                  table_mapping=a.get("table_mapping"), detail_mapping=a.get("detail_mapping"))
            tag = "reused" if known else f"{ms / 1000:.1f}s"
            print(f"  [{visited:>2}] {a.get('page_type', '?'):<6} {entity or '-':<14} +{new_records:<4} "
                  f"({tag}) {norm[:70]}")
            r.save()
            if a.get("done") and not queue:
                stop_reason = "Nemotron: done"
                break
        browser.close()

    r.save()
    r.log("done", pages=visited, reason=stop_reason, minutes=round((time.time() - t_start) / 60, 1))
    print(f"\nDone: {stop_reason}. {visited} pages in {(time.time() - t_start) / 60:.1f} min.")
    for e, bucket in r.records.items():
        fields = r.learned.get(e, {}).get("fields", {})
        print(f"  {e}: {len(bucket)} records, fields: {', '.join(list(fields)[:12])}")
        rules = sorted(r.learned.get(e, {}).get("rules", []))
        for rule in rules[:5]:
            print(f"     rule: {rule}")
    print(f"\nOutput: {r.dir}\n  records/*.csv  data_model.json  site_map.json  run_log.jsonl")
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description="Facade extraction agent (read-only).")
    ap.add_argument("url")
    ap.add_argument("--full", action="store_true", help="page through every list to the end (slow on big sites)")
    ap.add_argument("--pages", type=int, default=None, help="testing only: stop after N pages (default: run until done)")
    ap.add_argument("--vision", action="store_true", help="send screenshots too (uses MODEL_VISION)")
    ap.add_argument("--login", action="store_true", help="log in by hand first; the session is reused")
    ap.add_argument("--headed", action="store_true", help="show the browser")
    ap.add_argument("--budget", type=int, default=512, help="Nemotron reasoning budget per page (lower = faster)")
    args = ap.parse_args(argv)
    run(args.url, args.pages, args.vision, args.login, args.headed, args.budget, full=args.full)


if __name__ == "__main__":
    main()
