"""Real examples for every endpoint (run against the extracted records) and api_docs.md."""
import json
import statistics
from urllib.parse import urlencode

from . import query


def _example_params(op, rows):
    """Pick parameters that return something real."""
    if op["kind"] == "get":
        return {"id": rows[0]["legacy_id"]} if rows else {}
    params = {}
    for i in op["inputs"]:
        m, f = i.get("match"), i.get("field")
        if m == "search":
            words = [w.strip(".,:!?\"'") for r in rows[:5] for fld in i.get("fields", []) for w in str(r.get(fld) or "").split()]
            words = [w for w in words if len(w) >= 4]
            if words:
                params[i["name"]] = max(words, key=len).lower()
            break
    if op["kind"] == "search":
        params["limit"] = 3
        return params
    for i in op["inputs"]:  # one ranged filter (median) and one exact filter, if the endpoint has them
        f, m = i.get("field"), i.get("match")
        vals = [r.get(f) for r in rows if r.get(f) is not None] if f else []
        if m == "gte" and vals and not any(x.get("match") == "gte" and x["name"] in params for x in op["inputs"]):
            try:
                params[i["name"]] = statistics.median_low(sorted(vals))
            except TypeError:
                pass
    eq = next((i for i in op["inputs"] if i.get("match") == "eq" and i.get("in") == "query"), None)
    if eq:
        vals = [r.get(eq["field"]) for r in rows if r.get(eq["field"]) is not None]
        if vals:
            params[eq["name"]] = max(set(map(str, vals)), key=[str(v) for v in vals].count)
    if any(i.get("match") == "limit" for i in op["inputs"]):
        params["limit"] = 3
    return params


def add_examples(ops, records):
    for op in ops:
        rows = records.get(op["entity"], [])
        if op["source"] == "database":
            params = _example_params(op, rows)
            path = op["path"].replace("{id}", str(params.pop("id", "")))
            resp = query.run(op, {**params, **({"id": path.rsplit("/", 1)[-1]} if op["kind"] == "get" else {})}, records)
            if op["kind"] != "get" and resp.get("total") == 0 and params:  # too narrow: keep only paging
                params = {k: v for k, v in params.items() if k in ("limit", "q")}
                resp = query.run(op, params, records)
            op["example"] = {"request": path + ("?" + urlencode(params) if params else ""), "response": resp}
        else:
            src = rows[0] if rows else {}
            body = {i["name"]: src.get(i["field"]) for i in op["inputs"] if i.get("in") == "body"
                    and src.get(i.get("field")) is not None}
            path = op["path"].replace("{id}", src.get("legacy_id", "1"))
            op["example"] = {"request": path, "body": body,
                             "response": {"status": "done", "verified": True,
                                          "result": {"entity": op["entity"], "legacy_id": src.get("legacy_id"), "data": body},
                                          "error": None},
                             "note": "illustration: the Operator fills the legacy form, submits it and re-reads the "
                                     "record; on a rule violation status is 'failed' and error is the site's own message"}
    return ops


def _inputs_table(op):
    rows = ["| Name | In | Type | Meaning | Required |", "|---|---|---|---|---|"]
    for i in op["inputs"]:
        m = i.get("match")
        meaning = {"eq": f"`{i.get('field')}` equals", "contains": f"`{i.get('field')}` contains (case-insensitive)",
                   "gte": f"`{i.get('field')}` ≥", "lte": f"`{i.get('field')}` ≤", "id": "legacy id",
                   "search": "searches " + ", ".join(f"`{f}`" for f in i.get("fields", [])),
                   "limit": "max rows (default 50)", "offset": "skip rows", "sort": "sort field, `-` = descending"
                   }.get(m, m or "")
        if i.get("in") == "body":
            meaning = f"sets `{i.get('field')}`"
        if i.get("values"):
            vals = i["values"][:8]
            meaning += ": " + ", ".join(f"`{v}`" for v in vals) + (" …" if len(i["values"]) > 8 else "")
        rows.append(f"| `{i['name']}` | {i['in']} | {i.get('type', '')} | {meaning} | {'yes' if i.get('required') else ''} |")
    return "\n".join(rows)


def _short(resp, n=2):
    if isinstance(resp, dict) and isinstance(resp.get("items"), list) and len(resp["items"]) > n:
        resp = {**resp, "items": resp["items"][:n] + [f"... {len(resp['items']) - n} more"]}
    return json.dumps(resp, indent=2, ensure_ascii=False, default=str)


def markdown(doc, dm):
    ops = doc["operations"]
    meta = doc["designed_by"]
    who = f"Nemotron (`{meta['model']}`)" if meta["by"] == "nemotron" else "code-only rules (no Nemotron)"
    out = [f"# API for {doc['site']}", "",
           f"Designed by {who} from {sum(e.get('record_count', 0) for e in dm['entities'])} extracted records. "
           f"Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the "
           f"Operator and verified.", ""]
    if meta.get("problems_found"):
        out.append(f"The checker found {len(meta['problems_found'])} problem(s) in the first design; Nemotron fixed "
                   f"them in one round ({len(meta.get('problems_after_fix', []))} left, {len(meta['dropped'])} "
                   f"endpoint(s) dropped).")
        out.append("")
    out += ["| Method | Path | Source | What it does |", "|---|---|---|---|"]
    out += [f"| {o['method']} | `{o['path']}` | {o['source']} | {o.get('summary', '')} |" for o in ops]
    for ent in dm["entities"]:
        mine = [o for o in ops if o["entity"] == ent["name"]]
        if not mine:
            continue
        out += ["", f"## {ent['name']}", "",
                f"{ent.get('record_count', 0)} records. Fields: " +
                ", ".join(f"`{f['name']}` ({f['type']}{' → ' + f['to'] if f.get('to') else ''})" for f in ent["fields"]),
                ""]
        if not ent.get("forms"):
            out += ["_No form was seen for this entity on the legacy site, so it has no write endpoints._", ""]
        for o in mine:
            out += [f"### `{o['method']} {o['path']}`", "", o.get("summary", ""), ""]
            if o["source"] == "legacy":
                out += [f"Performed on the legacy site through form `{o['legacy']['form_page']}`: "
                        + " → ".join(o["legacy"].get("steps", [])), ""]
            if o["inputs"]:
                out += [_inputs_table(o), ""]
            ex = o.get("example")
            if ex:
                out += ["Example request:", "", "```http", f"{o['method']} {ex['request']}", "```"]
                if ex.get("body"):
                    out += ["```json", json.dumps(ex["body"], indent=2, ensure_ascii=False), "```"]
                out += ["", "Response" + (" (illustration)" if o["source"] == "legacy" else " (real data)") + ":", "",
                        "```json", _short(ex["response"]), "```", ""]
    return "\n".join(out) + "\n"
