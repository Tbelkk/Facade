"""Reference implementation of a read operation over the records (what the database-backed API must do).

Used to make real examples for api_docs.md, and handy for the SpacetimeDB person to compare against.
"""


def _match(value, want, how):
    if how == "eq":
        return value is not None and str(value).lower() == str(want).lower()
    if how == "contains":
        return value is not None and str(want).lower() in str(value).lower()
    if value is None:
        return False
    try:
        if isinstance(value, (int, float)):
            want = float(want)
        return value >= want if how == "gte" else value <= want
    except (TypeError, ValueError):
        return False


def run(op, params, records):
    """op: one operations.json entry (GET). params: {input name: value}. -> response JSON."""
    rows = records.get(op["entity"], [])
    inputs = {i["name"]: i for i in op.get("inputs", [])}
    if op["kind"] == "get":
        pid = next((i["name"] for i in op["inputs"] if i["in"] == "path"), None)
        hit = next((r for r in rows if r["legacy_id"] == str(params.get(pid))), None)
        return hit if hit else {"error": "not found"}
    limit, offset, sort = 50, 0, None
    out = rows
    for name, val in params.items():
        i = inputs.get(name)
        if not i or val in (None, ""):
            continue
        m = i.get("match")
        if m == "limit":
            limit = int(val)
        elif m == "offset":
            offset = int(val)
        elif m == "sort":
            sort = str(val)
        elif m == "search":
            out = [r for r in out if any(_match(r.get(f), val, "contains") for f in i.get("fields", []))]
        else:
            out = [r for r in out if _match(r.get(i["field"]), val, m)]
    if sort:
        key, rev = sort.lstrip("-"), sort.startswith("-")
        out = sorted(out, key=lambda r: (r.get(key) is None, r.get(key)), reverse=rev)
    return {"total": len(out), "limit": limit, "offset": offset, "items": out[offset: offset + limit]}
