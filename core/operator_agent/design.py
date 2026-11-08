"""Design the API: Nemotron proposes the operations, code checks them, Nemotron fixes problems once.

operations.json shape (one entry per endpoint):
    {"name": "list_posts", "method": "GET", "path": "/posts", "entity": "Post",
     "kind": "list" | "get" | "search" | "create" | "update",
     "source": "database" (read from SpacetimeDB) | "legacy" (performed live on the old site by the agent),
     "summary": "...",
     "inputs": [{"name": "min_points", "in": "query" | "path" | "body", "type": "integer",
                 "field": "points", "match": "eq|contains|gte|lte|id|search|limit|offset|sort",
                 "required": false, "values": [...]?, "fields": [...]? (search only)}],
     "output": {"type": "list" | "record" | "op_result", "entity": "Post"},
     "legacy": {"form_page": "patient_new", "steps": [...]}   (writes only)}
"""
import json
import re

from . import inputs as inputs_mod

KINDS = {"list": "GET", "get": "GET", "search": "GET", "create": "POST", "update": "PATCH"}
MATCHES = {"eq", "contains", "gte", "lte", "id", "search", "limit", "offset", "sort"}
ORDERED = {"integer", "number", "date"}
PATH_OK = re.compile(r"^/[a-z0-9_\-/{}]*$")


def plural_path(entity):
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", entity).lower()
    s = s[:-1] + "ies" if s.endswith("y") and s[-2:-1] not in "aeiou" else s + ("es" if s.endswith("s") else "s")
    return "/" + s


def _snake(entity):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", entity).lower()


# ------------------------------------------------------------------ baseline (no AI)

def heuristic(dm, prof):
    """A sensible design from types and value statistics alone. Used offline and as a safety net."""
    ops = []
    for p in prof:
        ent, path, one = p["entity"], plural_path(p["entity"]), _snake(p["entity"])
        filters, text = [], []
        for f in p["fields"]:
            t, n = f["type"], f["name"]
            if not f["non_null"]:
                continue  # never had a value: nothing to filter on
            if t == "boolean":
                filters.append({"name": n, "in": "query", "type": "boolean", "field": n, "match": "eq",
                                "values": [True, False]})
                continue
            if f.get("display_of"):  # readable twin of a reference (?author=alice); the id filter comes too
                filters.append({"name": n, "in": "query", "type": "string", "field": n, "match": "contains"})
                continue
            if t == "ref":
                filters.append({"name": n, "in": "query", "type": "string", "field": n, "match": "eq"})
            elif t == "enum" or (t == "string" and 0 < f["distinct"] <= 12 and f["distinct"] < p["record_count"] / 2):
                i = {"name": n, "in": "query", "type": "enum" if t == "enum" else "string", "field": n, "match": "eq"}
                if f.get("values") or f.get("value_counts"):
                    i["values"] = f.get("values") or list(f["value_counts"])
                filters.append(i)
            elif t in ORDERED:
                lo, hi = ("min_", "max_") if t != "date" else ("", "")
                filters.append({"name": f"{lo}{n}" if lo else f"{n}_from", "in": "query", "type": t, "field": n,
                                "match": "gte"})
                filters.append({"name": f"{hi}{n}" if hi else f"{n}_to", "in": "query", "type": t, "field": n,
                                "match": "lte"})
            elif t == "string":
                text.append(n)
                if (f.get("avg_len") or 0) <= 30:
                    filters.append({"name": n, "in": "query", "type": "string", "field": n, "match": "contains"})
        sortable = [f["name"] for f in p["fields"] if f["type"] in ORDERED]
        paging = [{"name": "limit", "in": "query", "type": "integer", "match": "limit"},
                  {"name": "offset", "in": "query", "type": "integer", "match": "offset"}]
        if sortable:
            paging.append({"name": "sort", "in": "query", "type": "string", "match": "sort",
                           "values": sortable + [f"-{s}" for s in sortable]})
        ops.append({"name": f"list_{path[1:]}", "method": "GET", "path": path, "entity": ent, "kind": "list",
                    "source": "database", "summary": f"List {ent} records, with filters",
                    "inputs": filters + paging, "output": {"type": "list", "entity": ent}})
        ops.append({"name": f"get_{one}", "method": "GET", "path": f"{path}/{{id}}", "entity": ent, "kind": "get",
                    "source": "database", "summary": f"One {ent} by its legacy id",
                    "inputs": [{"name": "id", "in": "path", "type": "string", "field": "legacy_id", "match": "id",
                                "required": True}], "output": {"type": "record", "entity": ent}})
        if text:
            ops.append({"name": f"search_{path[1:]}", "method": "GET", "path": f"{path}/search", "entity": ent,
                        "kind": "search", "source": "database", "summary": f"Full-text search over {', '.join(text)}",
                        "inputs": [{"name": "q", "in": "query", "type": "string", "match": "search", "fields": text,
                                    "required": True}] + paging[:2], "output": {"type": "list", "entity": ent}})
        for form in p["forms"]:
            kind = "create" if form["purpose"] == "create" else "update"
            if any(o["entity"] == ent and o["kind"] == kind for o in ops):
                continue
            body = []
            for x in form["fields"]:
                ftype = next((f["type"] for f in p["fields"] if f["name"] == x["name"]), "string")
                i = {"name": x["name"], "in": "body", "type": "enum" if x.get("options") else ftype,
                     "field": x["name"], "match": "eq", "required": bool(x.get("required")) and kind == "create"}
                if x.get("options"):
                    i["values"] = x["options"]
                body.append(i)
            op = {"name": f"{kind}_{one}", "method": KINDS[kind], "entity": ent, "kind": kind, "source": "legacy",
                  "summary": f"{'Create a new' if kind == 'create' else 'Update an existing'} {ent} on the legacy "
                             f"system through its form, then verify",
                  "output": {"type": "op_result", "entity": ent},
                  "legacy": {"form_page": form["page_id"],
                             "steps": [f"open {form['page_id']}", "fill fields by label", "submit",
                                       "read the result message", f"verify on the {ent} detail page"]}}
            if kind == "create":
                op.update(path=path, inputs=body)
            else:
                op.update(path=f"{path}/{{id}}", inputs=[{"name": "id", "in": "path", "type": "string",
                                                          "field": "legacy_id", "match": "id", "required": True}] + body)
            ops.append(op)
    return ops


# ------------------------------------------------------------------ checks (code, not AI)

def check(ops, dm):
    """Every problem with a proposed design, as plain sentences Nemotron can act on. [] = valid."""
    problems = []
    ents = {e["name"]: e for e in dm["entities"]}
    if not isinstance(ops, list) or not ops:
        return ["'operations' must be a non-empty list"]
    names, routes = set(), set()
    for k, op in enumerate(ops):
        if not isinstance(op, dict):
            problems.append(f"operation #{k} is not an object")
            continue
        tag = op.get("name") or f"#{k}"
        for req in ("name", "method", "path", "entity", "kind", "source", "inputs"):
            if req not in op:
                problems.append(f"{tag}: missing '{req}'")
        if any(req not in op for req in ("name", "method", "path", "entity", "kind")):
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(op["name"])):
            problems.append(f"{tag}: name must be snake_case like list_posts (lowercase letters, digits, _)")
        if op["name"] in names:
            problems.append(f"{tag}: operation name is used twice")
        names.add(op["name"])
        route = (op["method"], re.sub(r"\{\w+\}", "{}", op["path"]))
        if route in routes:
            problems.append(f"{tag}: {op['method']} {op['path']} duplicates another endpoint's path")
        routes.add(route)
        if not PATH_OK.match(op["path"]):
            problems.append(f"{tag}: path '{op['path']}' must start with / and use lowercase letters, digits, _ - {{}}")
        e = ents.get(op["entity"])
        if not e:
            problems.append(f"{tag}: entity '{op['entity']}' does not exist (have: {', '.join(ents)})")
            continue
        if op["kind"] not in KINDS:
            problems.append(f"{tag}: kind must be one of {sorted(KINDS)}")
            continue
        if op["method"] != KINDS[op["kind"]]:
            problems.append(f"{tag}: kind '{op['kind']}' must use method {KINDS[op['kind']]}")
        want_src = "legacy" if op["kind"] in ("create", "update") else "database"
        if op.get("source") != want_src:
            problems.append(f"{tag}: source must be '{want_src}' for kind '{op['kind']}'")
        fields = {f["name"]: f for f in e["fields"]}
        fields["legacy_id"] = {"name": "legacy_id", "type": "string"}
        ins = op.get("inputs") or []
        seen = set()
        for i in ins:
            n = i.get("name")
            if n in seen:
                problems.append(f"{tag}: input '{n}' appears twice")
            seen.add(n)
            m, where = i.get("match"), i.get("in")
            if where == "body":
                continue  # a value to set on the form; checked against the form in _check_write
            if m not in MATCHES:
                problems.append(f"{tag}: input '{n}' has match '{m}'; use one of {sorted(MATCHES)}")
                continue
            if where not in ("query", "path", "body"):
                problems.append(f"{tag}: input '{n}' has in='{where}'; use query, path or body")
            if m in ("limit", "offset"):
                continue
            if m == "sort":
                bad = [v for v in i.get("values", []) if v.lstrip("-") not in fields]
                if bad:
                    problems.append(f"{tag}: sort values {bad} are not fields of {op['entity']}")
                continue
            if m == "search":
                sf = i.get("fields") or []
                bad = [f for f in sf if f not in fields or fields[f]["type"] not in ("string", "enum")]
                if not sf or bad:
                    problems.append(f"{tag}: search input '{n}' needs 'fields' that are text fields of "
                                    f"{op['entity']}; bad: {bad or 'none given'}")
                continue
            fname = i.get("field")
            if fname not in fields:
                problems.append(f"{tag}: input '{n}' uses field '{fname}', which {op['entity']} does not have "
                                f"(fields: {', '.join(fields)})")
                continue
            ftype = fields[fname]["type"]
            if m in ("gte", "lte") and ftype not in ORDERED:
                problems.append(f"{tag}: input '{n}' uses {m} on '{fname}' ({ftype}); gte/lte only work on numbers/dates")
            if m == "contains" and ftype not in ("string", "enum"):
                problems.append(f"{tag}: input '{n}' uses contains on '{fname}' ({ftype}); contains is for text")
            if m == "id" and (where != "path" or fname != "legacy_id"):
                problems.append(f"{tag}: input '{n}' with match 'id' must be in:path and field 'legacy_id'")
        path_params = set(re.findall(r"\{(\w+)\}", op["path"]))
        in_path = {i.get("name") for i in ins if i.get("in") == "path"}
        if path_params != in_path:
            problems.append(f"{tag}: path parameters {sorted(path_params)} must match the in:path inputs "
                            f"{sorted(in_path)}")
        if op["kind"] in ("get", "update") and not path_params:
            problems.append(f"{tag}: kind '{op['kind']}' needs an id in the path, like /things/{{id}}")
        if op["kind"] in ("list", "get", "search") and any(i.get("in") == "body" for i in ins):
            problems.append(f"{tag}: read operations take no body inputs")
        if op["kind"] in ("create", "update"):
            problems += _check_write(op, e, tag)
    # one base path per entity: /faculty_members and /facultymembers/{id} would confuse anyone using the API
    bases = {}
    for op in ops:
        if isinstance(op, dict) and isinstance(op.get("path"), str) and op.get("entity"):
            bases.setdefault(op["entity"], set()).add(op["path"].strip("/").split("/")[0])
    for ent, b in bases.items():
        if len(b) > 1:
            problems.append(f"{ent}: all its endpoints must share one base path (now: {', '.join('/' + x for x in sorted(b))}); "
                            f"use {plural_path(ent)}")
    return problems


def _check_write(op, e, tag):
    problems = []
    form_id = (op.get("legacy") or {}).get("form_page")
    purpose = "create" if op["kind"] == "create" else "edit"
    forms = {f["page_id"]: f for f in e.get("forms", [])}
    if not forms:
        return [f"{tag}: {e['name']} has no form on the old site, so it cannot have a '{op['kind']}' endpoint; "
                f"remove it"]
    if form_id not in forms:
        return [f"{tag}: legacy.form_page must be one of {sorted(forms)} (the forms seen for {e['name']})"]
    form = forms[form_id]
    if form["purpose"] != purpose:
        problems.append(f"{tag}: form {form_id} is a '{form['purpose']}' form, not '{purpose}'")
    ff = {x["name"]: x for x in form["fields"]}
    body = {i["name"]: i for i in op.get("inputs", []) if i.get("in") == "body"}
    for n, i in body.items():
        if n not in ff:
            problems.append(f"{tag}: body input '{n}' is not a field of form {form_id} "
                            f"(form fields: {', '.join(ff)})")
        elif ff[n].get("options") and i.get("values") and not set(i["values"]) <= set(ff[n]["options"]):
            problems.append(f"{tag}: '{n}' values must come from the form's options {ff[n]['options']}")
    if op["kind"] == "create":
        for n, x in ff.items():
            if x.get("required") and not (n in body and body[n].get("required")):
                problems.append(f"{tag}: form {form_id} marks '{n}' required, so it must be a required body input")
    return problems


# ------------------------------------------------------------------ Nemotron

SYSTEM = """You are the Operator agent of RESTore. Another agent explored a legacy website (no API) and
extracted its data. You design the REST API that other software will use to reach this data.

Decide, from the entity profiles you are given (fields, types, REAL value statistics, forms seen):
1. Endpoints: a list endpoint per entity (GET /<plural>), a get-one endpoint (GET /<plural>/{id}),
   and a search endpoint (GET /<plural>/search?q=) when the entity has free-text fields.
2. Filters on the list endpoint that make sense for the REAL values:
   numbers/dates -> min_/max_ (only for type integer/number/date; text that looks like time, e.g. "2 hours ago",
   is a string); booleans -> eq; fields with non_null 0 never had a value, so give them no filter; (or <field>_from/<field>_to) with match gte/lte; few distinct values -> exact
   match eq (list them in "values"); short text such as names -> contains; references -> eq on the <x>_id field.
   Add limit/offset (match limit/offset) and, when there are numbers/dates, sort (values like "points", "-points").
3. Write endpoints ONLY from forms that were seen: a "create" form -> POST /<plural>; an "edit" form ->
   PATCH /<plural>/{id}. Body inputs are exactly the form's fields (same names); the form's required fields are
   required. Writes have source "legacy" and legacy.form_page = the form's page_id. No form -> no write endpoint.
   Never invent DELETE.
Reads have source "database". Use only field names that exist. Paths are lowercase and unique.

Answer with JSON only: {"operations": [ ... ]} where each operation is
{"name","method","path","entity","kind": list|get|search|create|update,"source": database|legacy,"summary",
 "inputs":[{"name","in": query|path|body,"type","field","match": eq|contains|gte|lte|id|search|limit|offset|sort,
            "required"?, "values"?, "fields"? (search only: the text fields searched)}],
 "output":{"type": list|record|op_result,"entity"},"legacy"?:{"form_page","steps":[...]}}
Names are snake_case (list_posts, get_post, create_patient). Body inputs: {"name","in":"body","type","field",
"required"} (no match). A get endpoint's path input is {"name":"id","in":"path","field":"legacy_id","match":"id","required":true}."""


def _ask(messages, model, budget):
    from ingest import nemotron
    res = nemotron.chat(messages, purpose="operator_design", model=model, budget=budget, answer_tokens=7000,
                        temperature=0.2)
    raw = nemotron.extract_json(res["text"])
    ops = raw.get("operations") if isinstance(raw, dict) else raw
    return ops, res


def design(dm, records, use_nemotron=True, model=None, budget=None, log=print):
    """-> (operations list, meta). Nemotron designs; code checks; one fix round; invalid ops dropped; gaps filled."""
    import os

    prof = inputs_mod.profile(dm, records)
    base = heuristic(dm, prof)
    meta = {"by": "heuristic", "model": None, "attempts": 0, "nemotron_ms": 0, "problems_found": [],
            "problems_after_fix": [], "dropped": [], "added_by_code": []}
    if not use_nemotron:
        return base, meta

    model = model or os.getenv("MODEL_AGENT", "nvidia/nemotron-3.5-super-vl-120b-a12b")
    budget = budget if budget is not None else int(os.getenv("OPERATOR_REASONING_BUDGET", "2048"))
    meta.update(model=model)
    user = "Entity profiles (from the extracted records):\n" + json.dumps(prof, indent=1, default=str)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    try:
        log(f"Nemotron ({model}) is designing the API for {len(prof)} entities...")
        ops, res = _ask(messages, model, budget)
        meta["attempts"], meta["nemotron_ms"] = 1, res["ms"]
        problems = check(ops, dm)
        meta["problems_found"] = problems
        log(f"  proposed {len(ops) if isinstance(ops, list) else 0} endpoints in {res['ms'] / 1000:.1f}s; "
            f"{len(problems)} problem(s) found by the checker")
        if problems:
            messages += [{"role": "assistant", "content": json.dumps({"operations": ops})},
                         {"role": "user", "content": "The checker found these problems. Fix every one and return "
                                                     "the FULL corrected JSON:\n- " + "\n- ".join(problems)}]
            ops, res = _ask(messages, model, budget)
            meta["attempts"], meta["nemotron_ms"] = 2, meta["nemotron_ms"] + res["ms"]
            meta["problems_after_fix"] = check(ops, dm)
            log(f"  after one fix: {len(meta['problems_after_fix'])} problem(s) left")
        meta["by"] = "nemotron"
    except Exception as e:  # network, timeout, unparseable JSON: fall back, and say so
        log(f"  Nemotron design failed ({str(e)[:160]}); using the code-only design")
        meta.update(by="heuristic_fallback", error=str(e)[:300])
        return base, meta

    # keep only operations that pass the checks on their own
    kept = []
    for op in ops if isinstance(ops, list) else []:
        if check([op], dm) == [] and not check(kept + [op], dm):
            kept.append(op)
        else:
            meta["dropped"].append({"name": op.get("name") if isinstance(op, dict) else None,
                                    "problems": check([op], dm) or check(kept + [op], dm)})
    # every entity keeps at least list + get (safety net from the code-only design)
    for b in base:
        if b["kind"] in ("list", "get") and not any(k["entity"] == b["entity"] and k["kind"] == b["kind"]
                                                    for k in kept):
            if not check(kept + [b], dm):
                kept.append(b)
                meta["added_by_code"].append(b["name"])
    for op in kept:  # fill harmless gaps
        op.setdefault("summary", f"{op['kind']} {op['entity']}")
        op.setdefault("output", {"type": {"list": "list", "search": "list", "get": "record"}.get(op["kind"], "op_result"),
                                 "entity": op["entity"]})
        fields = {f["name"]: f for e in dm["entities"] if e["name"] == op["entity"] for f in e["fields"]}
        for i in op["inputs"]:
            i.setdefault("required", i.get("in") == "path")
            if i.get("in") == "body":
                i["match"] = "set"
                i.setdefault("field", i["name"])
            if "type" not in i:
                i["type"] = fields.get(i.get("field"), {}).get("type", "string")
    return kept, meta
