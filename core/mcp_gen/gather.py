"""Gather what the MCP server needs, and turn it into MCP tool definitions.

Inputs (per site):
  operations   operations.json from the Operator agent  -> one MCP tool per operation
  schema       the entities and their fields            -> checks that every tool input points at a real field
  records      the extracted data                       -> what database tools answer from
  op_requests  write requests and their status          -> what legacy (write) tools create

Where they come from:
  SpacetimeDB  tables site (ops_json), entity_schema, record, op_request   (via store.spacetime)
  files        shared/output/<site>/operations.json, data_model.json, records/*.jsonl   (mock mode)
  The script tries SpacetimeDB first and falls back to the files if it can't be reached. --mock skips SpacetimeDB.

Output: shared/output/<site>/mcp/tools.json   (MCP tool list + what the server needs to answer each tool)

Run from core/:
  python -m mcp_gen.gather hackernews --mock
  python -m mcp_gen.gather clinic --mock
  python -m mcp_gen.gather https://news.ycombinator.com      # SpacetimeDB, falling back to files
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "shared" / "output"

TYPE = {"string": "string", "integer": "integer", "number": "number", "date": "string", "enum": "string", "ref": "string", "boolean": "boolean"}
HOW = {
    "contains": "Text that {f} contains (case-insensitive)",
    "eq": "Exact {f}",
    "gte": "Smallest {f} to include",
    "lte": "Largest {f} to include",
    "search": "Words to look for in {f}",
    "limit": "How many results to return (default 50)",
    "offset": "How many results to skip, for paging",
    "sort": "Field to sort by; put - in front for descending",
    "id": "The record's id",
    "set": "New value for {f}",
}


def say(step, msg):
    print(f"[{step}] {msg}")


# ---------------- where to find the site ----------------

def resolve(name_or_url):
    """'hackernews' or 'https://news.ycombinator.com' -> (folder name, site url)."""
    index = json.loads((OUTPUT / "index.json").read_text()).get("sites", {}) if (OUTPUT / "index.json").exists() else {}
    if name_or_url in index:
        return name_or_url, index[name_or_url]["site"]
    for name, meta in index.items():
        if meta.get("site", "").rstrip("/") == name_or_url.rstrip("/"):
            return name, meta["site"]
    if (OUTPUT / name_or_url).is_dir():
        return name_or_url, name_or_url
    return None, name_or_url


# ---------------- SpacetimeDB ----------------

def from_spacetime(site):
    """Returns the inputs from SpacetimeDB, or None if it can't be reached or has nothing for this site."""
    try:
        from store import spacetime as db
    except ImportError as e:
        say("db", f"store client not importable ({e})")
        return None
    q = db.quote(site)
    rows = db.sql(f"SELECT * FROM site WHERE url = {q}")
    if rows is None:
        say("db", f"SpacetimeDB not reachable at {db.HOST} (database {db.DB})")
        return None
    if not rows or not rows[0].get("ops_json"):
        say("db", f"SpacetimeDB has no operations for {site}")
        return None
    ops = json.loads(rows[0]["ops_json"])
    schema = {r["name"]: {"fields": json.loads(r["fields_json"] or "[]")} for r in (db.sql(f"SELECT * FROM entity_schema WHERE site = {q}") or [])}
    records = {}
    for r in db.sql(f"SELECT entity, legacy_id, data_json FROM record WHERE site = {q}") or []:
        records.setdefault(r["entity"], []).append({"legacy_id": r["legacy_id"], **json.loads(r["data_json"] or "{}")})
    op_status = Counter(r["status"] for r in (db.sql(f"SELECT status FROM op_request WHERE site = {q}") or []))
    return {"source": f"SpacetimeDB ({db.HOST}, {db.DB})", "ops": ops, "schema": schema, "records": records, "op_status": op_status}


# ---------------- files (mock) ----------------

def from_files(folder):
    d = OUTPUT / folder
    ops = json.loads((d / "operations.json").read_text())
    schema = {}
    if (d / "data_model.json").exists():
        for e in json.loads((d / "data_model.json").read_text()).get("entities", []):
            schema[e["name"]] = {"fields": e.get("fields", [])}
    for name, e in (ops.get("entities") or {}).items():   # operations.json has the normalized types
        schema[name] = {"fields": e.get("fields", [])}
    records = {}
    for f in sorted((d / "records").glob("*.jsonl")):
        rows = []
        for line in f.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                rows.append({"legacy_id": str(r.get("legacy_id", r.get("_key", ""))), **(r.get("data") or {k: v for k, v in r.items() if k != "_key"})})
        records[f.stem] = rows
    return {"source": f"files in {d.relative_to(ROOT)}", "ops": ops, "schema": schema, "records": records, "op_status": Counter()}


# ---------------- operations -> MCP tools ----------------

def to_tool(op, schema):
    props, required = {}, []
    for i in op.get("inputs", []):
        field = i.get("field") or ", ".join(i.get("fields") or [])
        p = {"type": TYPE.get(i.get("type"), "string"), "description": HOW.get(i.get("match"), "{f}").format(f=field or i["name"])}
        if i.get("type") == "date":
            p["format"] = "date"
        if i.get("values"):
            p["enum"] = i["values"]
        props[i["name"]] = p
        if i.get("required") or i.get("in") == "path":
            required.append(i["name"])
    writes = op.get("source") == "legacy"
    desc = op.get("summary", op["name"])
    ex = op.get("example") or {}
    if ex.get("request"):
        desc += f" Example: {ex['request']}"
    if writes:
        desc += " Runs on the legacy system and can take a while; returns status, verified and the record."
    return {
        "name": op["name"],
        "description": desc,
        "inputSchema": {"type": "object", "properties": props, "required": required},
        "annotations": {"readOnlyHint": not writes, "destructiveHint": False, "openWorldHint": writes},
        # what the MCP server itself needs to answer the call (not shown to the AI)
        "_facade": {
            "entity": op["entity"], "kind": op["kind"], "source": op["source"],
            "inputs": [{k: i[k] for k in ("name", "field", "fields", "match") if k in i} for i in op.get("inputs", [])],
            "legacy": op.get("legacy"),
        },
    }


def check(op, schema, records):
    """Problems that would stop this tool from working."""
    problems = []
    ent = op.get("entity")
    fields = {f["name"] for f in schema.get(ent, {}).get("fields", [])} | {"legacy_id"}   # legacy_id is the record key
    if ent not in schema:
        problems.append(f"no schema for {ent}")
    for i in op.get("inputs", []):
        for f in ([i["field"]] if i.get("field") else []) + list(i.get("fields") or []):
            if fields and f not in fields:
                problems.append(f"input {i['name']} points at unknown field {f}")
    if op.get("source") == "database" and not records.get(ent):
        problems.append(f"no {ent} records to answer from")
    if op.get("source") == "legacy" and not (op.get("legacy") or {}).get("form_page"):
        problems.append("write tool has no legacy form_page")
    return problems


def try_example(op, records):
    """Run a read tool's example through the reference query rules; returns a one-line result."""
    if op.get("source") != "database":
        return "write tool: creates an op_request for the Operator (not run here)"
    try:
        from operator_agent import query
    except ImportError:
        return "skipped (operator_agent.query not importable)"
    params = {}
    if op["kind"] == "get":
        rows = records.get(op["entity"]) or []
        pid = next((i["name"] for i in op["inputs"] if i.get("in") == "path"), "id")
        params = {pid: rows[0]["legacy_id"]} if rows else {}
    else:
        req = (op.get("example") or {}).get("request", "")
        if "?" in req:
            from urllib.parse import parse_qsl
            params = dict(parse_qsl(req.split("?", 1)[1]))
    res = query.run(op, params, records)
    if "items" in res:
        return f"{params or '{}'} -> {res['total']} matches, {len(res['items'])} returned"
    return f"{params} -> {'found' if 'error' not in res else res['error']}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gather MCP inputs from SpacetimeDB + operations.json and write MCP tool definitions.")
    ap.add_argument("site", help="folder in shared/output (hackernews, clinic, news) or the site URL")
    ap.add_argument("--mock", action="store_true", help="read shared/output files only, skip SpacetimeDB")
    ap.add_argument("--out", help="where to write tools.json (default shared/output/<site>/mcp/tools.json)")
    a = ap.parse_args(argv)

    folder, site = resolve(a.site)
    say("site", f"{site}" + (f"  (shared/output/{folder})" if folder else ""))

    data = None if a.mock else from_spacetime(site)
    if data is None:
        if not folder:
            sys.exit(f"No SpacetimeDB data and no shared/output folder for {a.site}. Try one of: "
                     + ", ".join(p.name for p in OUTPUT.iterdir() if (p / 'operations.json').exists()))
        data = from_files(folder)
    say("1/4 operations", f"{len(data['ops']['operations'])} from {data['source']}"
        + (f", designed by {data['ops']['designed_by'].get('by')}" if data["ops"].get("designed_by") else ""))
    say("2/4 schema", ", ".join(f"{n} ({len(e['fields'])} fields)" for n, e in data["schema"].items()) or "none")
    say("3/4 records", ", ".join(f"{n}: {len(r):,}" for n, r in data["records"].items()) or "none")
    if data["op_status"]:
        say("   op_requests", ", ".join(f"{s}: {c}" for s, c in data["op_status"].items()))

    tools, bad = [], 0
    say("4/4 tools", "")
    for op in data["ops"]["operations"]:
        problems = check(op, data["schema"], data["records"])
        bad += bool(problems)
        tools.append(to_tool(op, data["schema"]))
        mark = "ok " if not problems else "!! "
        print(f"   {mark}{op['name']:<22} {op['source']:<8} {len(op.get('inputs', []))} inputs  "
              + ("; ".join(problems) if problems else try_example(op, data["records"])))

    out = Path(a.out) if a.out else (OUTPUT / (folder or "site") / "mcp" / "tools.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"site": site, "source": data["source"], "tools": tools}, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(tools)} MCP tools to {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}"
          + (f"  ({bad} with problems)" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
