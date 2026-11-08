"""What the server serves: the API design and the records, from SpacetimeDB (preferred) or the output folder.

Records come back as {Entity: [{"legacy_id": ..., field: value, ...}]}, the shape operator_agent/query.py uses.
Knows nothing about any specific website.
"""
import json
from pathlib import Path


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def from_folder(folder):
    """shared/output/<site>/ (or a run folder): operations.json + data_model.json + records/*.jsonl."""
    from operator_agent import inputs
    folder = Path(folder)
    ops = _read_json(folder / "operations.json")
    if not ops:
        raise SystemExit(f"No operations.json in {folder}. Run the Operator first: python -m operator_agent.run {folder}")
    dm, _site_map, records = inputs.load(folder)   # handles both record shapes and types the values
    site = ops.get("site") or dm.get("site")
    return {"site": site, "ops": ops, "model": dm, "records": records, "source": f"files: {folder}"}


def from_spacetime(site):
    """The same, read back from SpacetimeDB (what store.load_run wrote). None if unreachable or empty."""
    from store import spacetime as db
    rows = db.sql(f"SELECT * FROM site WHERE url = {db.quote(site)}")
    if not rows:
        return None
    srow = rows[0]
    ops = json.loads(srow.get("ops_json") or "{}")
    model = json.loads(srow.get("model_json") or "{}")
    if not ops.get("operations"):
        return None
    recs = db.sql(f"SELECT * FROM record WHERE site = {db.quote(site)}") or []
    records = {}
    for r in recs:
        try:
            data = json.loads(r.get("data_json") or "{}")
        except ValueError:
            continue
        records.setdefault(r["entity"], []).append({"legacy_id": str(r["legacy_id"]), **data})
    # rows streamed in live during exploring keep the Explorer's first names; the Operator's tidy step may have
    # renamed or dropped those entities, so serve only the entities in the final design
    wanted = set(ops.get("entities") or {}) | {o.get("entity") for o in ops["operations"]}
    records = {k: v for k, v in records.items() if k in wanted}
    return {"site": site, "ops": ops, "model": model, "records": records, "source": f"SpacetimeDB {db.HOST}/{db.DB}"}


def load(folder, prefer="spacetime"):
    """Folder gives the site; SpacetimeDB is used when it has this site, otherwise the folder's files."""
    local = from_folder(folder)
    if prefer == "spacetime" and local["site"]:
        try:
            remote = from_spacetime(local["site"])
        except Exception:
            remote = None
        if remote and sum(len(v) for v in remote["records"].values()):
            return remote
    return local
