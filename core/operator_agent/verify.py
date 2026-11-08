"""Check the final output before SpacetimeDB gets it: shared/output/<site>/.

    python -m operator_agent.verify                 # every site in shared/output/
    python -m operator_agent.verify hackernews      # one site (name or folder path)
    python -m operator_agent.verify --json          # machine-readable report

Errors = the database or the API would be wrong. Warnings = data quality worth knowing (empty fields, ...).
Exit code 1 when any site has errors.

What is checked
    folder      data_model.json has a site and entities; manifest counts match the files; index.json lists it
    records     canonical shape {legacy_id, hash, data}; ids unique; hash matches data; only known fields;
                every value has its field's type (integer, number, boolean, ISO date, enum value, string);
                references point at records that exist
    endpoints   operations.json passes the design checker; every read endpoint is CALLED against the records
                and its answer is checked: filters really filter (gte/lte/eq/contains/search), sort is ordered,
                limit/offset page correctly, get returns the right record and "not found" for a missing id,
                the stored example still matches what the endpoint returns; writes point at a real form and
                require what the form requires; api_docs.md documents every endpoint
    spacetime   spacetime/record.json (when present) holds the same records as records/*.jsonl
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from . import design, inputs, query

CORE = Path(__file__).resolve().parent.parent
OUTPUT = CORE.parent / "shared" / "output"
TYPES = {"string", "integer", "number", "boolean", "date", "enum", "ref"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Report:
    def __init__(self, site):
        self.site, self.errors, self.warnings, self.checks = site, [], [], 0

    def ok(self, cond, msg, warn=False):
        self.checks += 1
        if not cond:
            (self.warnings if warn else self.errors).append(msg)
        return cond

    def as_dict(self):
        return {"site": self.site, "passed": not self.errors, "checks": self.checks,
                "errors": self.errors, "warnings": self.warnings}


def _hash(data):
    return hashlib.sha1(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _type_ok(v, f):
    t = f["type"]
    if v is None:
        return True
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "date":
        return isinstance(v, str) and bool(ISO_DATE.match(v))
    if t == "enum":
        return v in (f.get("values") or [v])
    return isinstance(v, str)


# ------------------------------------------------------------------ folder + records

def check_folder(folder, r):
    dm_path = folder / "data_model.json"
    if not r.ok(dm_path.exists(), "data_model.json is missing"):
        return None
    raw = _read(dm_path)
    r.ok(bool(raw.get("site")), "data_model.json has no 'site' (the loader needs it)")
    r.ok(bool(raw.get("entities")), "data_model.json has no entities")
    for e in raw.get("entities", []):
        for f in e.get("fields", []):
            r.ok(f.get("type") in TYPES, f"{e['name']}.{f.get('name')}: type '{f.get('type')}' is not one of "
                                         f"{sorted(TYPES)} (the API and schema would not know it)")
        r.ok((folder / "records" / f"{e['name']}.jsonl").exists(), f"records/{e['name']}.jsonl is missing")
    man = folder / "manifest.json"
    if r.ok(man.exists(), "manifest.json is missing", warn=True):
        m = _read(man)
        for ent, n in (m.get("records") or {}).items():
            p = folder / "records" / f"{ent}.jsonl"
            lines = sum(1 for l in p.read_text(encoding="utf-8").splitlines() if l.strip()) if p.exists() else 0
            r.ok(lines == n, f"manifest says {n} {ent} records, records/{ent}.jsonl has {lines}")
        for f in m.get("files", []):
            r.ok((folder / f).exists(), f"manifest lists {f}, which does not exist")
    idx = folder.parent / "index.json"
    if idx.exists():
        r.ok(folder.name in _read(idx).get("sites", {}), f"index.json does not list '{folder.name}'", warn=True)
    return raw


def check_records(folder, raw, r):
    """Returns {entity: [flat rows]} for the endpoint checks."""
    ents = {e["name"]: e for e in raw["entities"]}
    rows_by = {}
    for name, e in ents.items():
        p = folder / "records" / f"{name}.jsonl"
        if not p.exists():
            continue
        fields = {f["name"]: f for f in e["fields"]}
        seen, rows, bad_type, unknown = set(), [], {}, set()
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            rec = json.loads(line)
            if not r.ok(isinstance(rec.get("data"), dict) and "legacy_id" in rec,
                        f"{name} line {n}: not the canonical shape {{legacy_id, hash, data}}"):
                continue
            lid = str(rec["legacy_id"])
            r.ok(lid not in seen and lid not in ("", "None"), f"{name} line {n}: legacy_id '{lid}' is empty or repeated")
            seen.add(lid)
            r.ok(rec.get("hash") == _hash(rec["data"]), f"{name} {lid}: hash does not match its data")
            for k, v in rec["data"].items():
                if k not in fields:
                    unknown.add(k)
                elif not _type_ok(v, fields[k]):
                    bad_type.setdefault(k, (lid, v))
            rows.append({"legacy_id": lid, **rec["data"]})
        r.ok(not unknown, f"{name}: records use fields not in the data model: {sorted(unknown)}")
        for k, (lid, v) in bad_type.items():
            r.ok(False, f"{name}.{k}: value {v!r} (record {lid}) is not a {fields[k]['type']}")
        r.ok(bool(rows), f"{name}: no records", warn=True)
        for f in e["fields"]:
            filled = sum(1 for x in rows if x.get(f["name"]) not in (None, ""))
            if rows and not filled:
                r.ok(False, f"{name}.{f['name']}: never has a value in {len(rows)} records", warn=True)
            elif f.get("required") and rows and filled < len(rows):
                r.ok(False, f"{name}.{f['name']}: marked required but empty in {len(rows) - filled}/{len(rows)} "
                            f"records", warn=True)
        rows_by[name] = rows
    for name, e in ents.items():  # references must point at real records
        for f in e["fields"]:
            if f["type"] == "ref" and f.get("to") in rows_by:
                ids = {x["legacy_id"] for x in rows_by[f["to"]]}
                missing = {x[f["name"]] for x in rows_by.get(name, []) if x.get(f["name"]) and x[f["name"]] not in ids}
                r.ok(not missing, f"{name}.{f['name']} points at {f['to']} ids that do not exist: {sorted(missing)[:5]}")
    return rows_by


# ------------------------------------------------------------------ endpoints

def _val(rows, field, pick="median"):
    vals = sorted((x[field] for x in rows if x.get(field) not in (None, "")), key=lambda v: (str(type(v)), v))
    return vals[len(vals) // 2] if vals else None


def _satisfies(item, inp, val):
    v = item.get(inp.get("field"))
    m = inp["match"]
    if m == "eq":
        return v is not None and str(v).lower() == str(val).lower()
    if m == "contains":
        return v is not None and str(val).lower() in str(v).lower()
    if m == "gte":
        return v is not None and v >= val
    if m == "lte":
        return v is not None and v <= val
    if m == "search":
        return any(str(val).lower() in str(item.get(f) or "").lower() for f in inp.get("fields", []))
    return True


def check_endpoint(op, records, dm_norm, r):
    tag = f"{op['method']} {op['path']}"
    rows = records.get(op["entity"], [])
    if op["source"] == "legacy":
        forms = {f["page_id"]: f for e in dm_norm["entities"] if e["name"] == op["entity"] for f in e.get("forms", [])}
        form = forms.get((op.get("legacy") or {}).get("form_page"))
        if r.ok(form is not None, f"{tag}: legacy.form_page is not a form seen for {op['entity']}"):
            req = {x["name"] for x in form["fields"] if x.get("required")}
            body_req = {i["name"] for i in op["inputs"] if i.get("in") == "body" and i.get("required")}
            if op["kind"] == "create":
                r.ok(req <= body_req, f"{tag}: the form requires {sorted(req - body_req)} but the endpoint does not")
        return
    ex = op.get("example") or {}
    if op["kind"] == "get":
        if not rows:
            return
        target = rows[len(rows) // 2]
        got = query.run(op, {"id": target["legacy_id"]}, records)
        r.ok(got == target, f"{tag}: get({target['legacy_id']}) did not return that record")
        r.ok(query.run(op, {"id": "__no_such_id__"}, records).get("error") == "not found",
             f"{tag}: a missing id should answer 'not found'")
        if ex:
            lid = ex["request"].rstrip("/").rsplit("/", 1)[-1]
            r.ok(query.run(op, {"id": lid}, records) == ex.get("response"),
                 f"{tag}: the stored example no longer matches the data")
        return
    # list / search: call the endpoint for every input with a real value and check the answer
    everything = query.run(op, {"limit": 10 ** 9}, records)
    if op["kind"] == "list":
        r.ok(everything["total"] == len(rows), f"{tag}: with no filters it returns {everything['total']} of "
                                               f"{len(rows)} records")
    for inp in op["inputs"]:
        m, name = inp.get("match"), inp["name"]
        if m in ("eq", "contains", "gte", "lte"):
            val = _val(rows, inp.get("field"))
            if val is None:
                continue
            if m == "contains":
                val = str(val)[: max(3, len(str(val)) // 2)]
            res = query.run(op, {name: val, "limit": 10 ** 9}, records)
            bad = [x["legacy_id"] for x in res["items"] if not _satisfies(x, inp, val)]
            r.ok(not bad, f"{tag}?{name}={val}: returned records that do not match: {bad[:5]}")
            r.ok(res["total"] > 0, f"{tag}?{name}={val}: a value taken from the data returns nothing")
            expect = sum(1 for x in rows if _satisfies(x, inp, val))
            r.ok(res["total"] == expect, f"{tag}?{name}={val}: returned {res['total']}, {expect} records match")
        elif m == "search":
            words = [w for x in rows[:20] for f in inp.get("fields", []) for w in re.findall(r"[A-Za-z]{4,}", str(x.get(f) or ""))]
            if not words:
                continue
            res = query.run(op, {name: words[0], "limit": 10 ** 9}, records)
            r.ok(res["total"] > 0 and all(_satisfies(x, inp, words[0]) for x in res["items"]),
                 f"{tag}?{name}={words[0]}: search results do not all contain the word")
        elif m == "sort":
            for key in (inp.get("values") or [])[:4]:
                res = query.run(op, {name: key, "limit": 10 ** 9}, records)
                field, desc = key.lstrip("-"), key.startswith("-")
                vals = [x.get(field) for x in res["items"] if x.get(field) is not None]
                r.ok(vals == sorted(vals, reverse=desc), f"{tag}?{name}={key}: results are not sorted")
        elif m == "limit" and rows:
            res = query.run(op, {name: 2}, records)
            r.ok(len(res["items"]) == min(2, res["total"]), f"{tag}?{name}=2: returned {len(res['items'])} items")
        elif m == "offset" and len(rows) > 3 and op["kind"] == "list":
            a = query.run(op, {"limit": 2, name: 0}, records)["items"]
            b = query.run(op, {"limit": 2, name: 2}, records)["items"]
            r.ok(not {x["legacy_id"] for x in a} & {x["legacy_id"] for x in b}, f"{tag}: offset pages overlap")
    if ex.get("request"):
        q = ex["request"].split("?", 1)[1] if "?" in ex["request"] else ""
        from urllib.parse import parse_qsl
        params = {}
        for k, v in parse_qsl(q):
            i = next((x for x in op["inputs"] if x["name"] == k), {})
            params[k] = (int(v) if re.fullmatch(r"-?\d+", v) else float(v)) if i.get("type") in ("integer", "number") \
                or k in ("limit", "offset") else v
        r.ok(query.run(op, params, records) == ex.get("response"),
             f"{tag}: the stored example ({ex['request']}) no longer matches what the endpoint returns")


def check_operations(folder, records, r):
    p = folder / "operations.json"
    if not r.ok(p.exists(), "operations.json is missing (run python -m operator_agent.run on the run folder)"):
        return
    doc = _read(p)
    dm_norm, _, _ = inputs.load(folder)
    ops = doc.get("operations", [])
    for problem in design.check(ops, dm_norm):
        r.ok(False, f"design: {problem}")
    for ent in dm_norm["entities"]:
        kinds = {o["kind"] for o in ops if o.get("entity") == ent["name"]}
        r.ok({"list", "get"} <= kinds, f"{ent['name']}: needs both a list and a get endpoint (has {sorted(kinds)})")
        r.ok(bool(ent.get("forms")) or not kinds & {"create", "update"},
             f"{ent['name']}: has write endpoints but no form was seen")
    for op in ops:
        try:
            check_endpoint(op, records, dm_norm, r)
        except Exception as e:  # an endpoint that crashes is an error, not a crash of the checker
            r.ok(False, f"{op.get('method')} {op.get('path')}: calling it failed: {type(e).__name__}: {e}")
    docs = folder / "api_docs.md"
    if r.ok(docs.exists(), "api_docs.md is missing", warn=True):
        text = docs.read_text(encoding="utf-8")
        for op in ops:
            r.ok(f"{op['method']} {op['path']}" in text or f"`{op['path']}`" in text,
                 f"api_docs.md does not document {op['method']} {op['path']}", warn=True)


def check_spacetime_rows(folder, records, r):
    p = folder / "spacetime" / "record.json"
    if not p.exists():
        return
    rows = _read(p)
    got = {(x["entity"], x["legacy_id"]): json.loads(x["data_json"]) for x in rows}
    want = {(e, x["legacy_id"]): {k: v for k, v in x.items() if k != "legacy_id"} for e, xs in records.items() for x in xs}
    r.ok(set(got) == set(want), f"spacetime/record.json has {len(got)} rows, records/ has {len(want)} "
                                f"(different records)")
    diff = [k for k in set(got) & set(want) if got[k] != want[k]]
    r.ok(not diff, f"spacetime/record.json data differs from records/ for {sorted(diff)[:3]}")


def verify(folder):
    folder = Path(folder)
    r = Report(folder.name)
    raw = check_folder(folder, r)
    if raw and raw.get("entities"):
        records = check_records(folder, raw, r)
        check_operations(folder, records, r)
        check_spacetime_rows(folder, records, r)
    return r.as_dict()


def sites(root=OUTPUT):
    return sorted(p for p in Path(root).iterdir() if p.is_dir() and (p / "data_model.json").exists()) \
        if Path(root).exists() else []


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check shared/output/<site>/ before SpacetimeDB loads it")
    ap.add_argument("site", nargs="?", help="site name in shared/output/ or a folder path (default: all)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.site:
        p = Path(a.site)
        targets = [p if p.exists() else OUTPUT / a.site]
    else:
        targets = sites()
    reports = [verify(t) for t in targets]
    if a.json:
        print(json.dumps(reports, indent=2))
    else:
        for rep in reports:
            print(f"[{'PASS' if rep['passed'] else 'FAIL'}] {rep['site']}: {rep['checks']} checks, "
                  f"{len(rep['errors'])} error(s), {len(rep['warnings'])} warning(s)")
            for e in rep["errors"]:
                print(f"    ERROR  {e}")
            for w in rep["warnings"]:
                print(f"    warn   {w}")
    sys.exit(0 if all(x["passed"] for x in reports) else 1)


if __name__ == "__main__":
    main()
