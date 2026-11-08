"""The fixed handoff folder the next agent reads: core/cache/latest/

Every run (extract, operator, mock pipeline) replaces it as a whole with the newest run's outputs, so files
from different runs are never mixed:

    core/cache/latest/
        manifest.json          which run this is, when, record counts, which files are present
        site_map.json          pages            (save_site)
        recipes.json           how to read/fill each page
        data_model.json        entities + forms (upsert_schema)
        records/<Entity>.jsonl the data          (upsert_record)
        operations.json        the API design   (the SpacetimeDB server builds exactly these endpoints + MCP tools)
        api_docs.md
        schema.json            JSON Schema per entity
        spacetime/<table>.json ready-made rows for every table (plan 7.5)

Point the SpacetimeDB server at it with FACADE_HANDOFF_DIR (default: this folder).
"""
import json
import os
import shutil
import time
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
DEFAULT = CORE / "cache" / "latest"


def latest_dir():
    return Path(os.getenv("FACADE_HANDOFF_DIR") or DEFAULT)

FILES = ["site_map.json", "recipes.json", "data_model.json", "operations.json", "api_docs.md"]
DIRS = {"records": "records", "extract/spacetime": "spacetime"}
EXTRA = {"extract/schema.json": "schema.json"}


def publish(run_dir, dest=None, log=print):
    """Copy a run folder's outputs into the handoff folder (atomically: build next to it, then swap)."""
    run_dir, dest = Path(run_dir).resolve(), Path(dest or latest_dir())
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    present = []
    for f in FILES:
        if (run_dir / f).exists():
            shutil.copy2(run_dir / f, tmp / f)
            present.append(f)
    for src, name in EXTRA.items():
        if (run_dir / src).exists():
            shutil.copy2(run_dir / src, tmp / name)
            present.append(name)
    for src, name in DIRS.items():
        if (run_dir / src).is_dir():
            shutil.copytree(run_dir / src, tmp / name)
            present += [f"{name}/{p.name}" for p in sorted((tmp / name).iterdir())]
    counts = {}
    for p in sorted((tmp / "records").glob("*.jsonl")) if (tmp / "records").is_dir() else []:
        counts[p.stem] = sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
    site = None
    for f in ("data_model.json", "site_map.json"):
        if (tmp / f).exists():
            site = json.loads((tmp / f).read_text(encoding="utf-8")).get("site")
            break
    ops = None
    if (tmp / "operations.json").exists():
        doc = json.loads((tmp / "operations.json").read_text(encoding="utf-8"))
        ops = {"count": len(doc["operations"]), "designed_by": doc.get("designed_by", {}).get("by")}
    manifest = {"published_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_dir": str(run_dir), "site": site,
                "records": counts, "operations": ops, "files": present}
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    old = dest.with_name(dest.name + ".old")
    shutil.rmtree(old, ignore_errors=True)
    if dest.exists():
        dest.rename(old)
    tmp.rename(dest)
    shutil.rmtree(old, ignore_errors=True)
    log(f"Handoff: published to {dest}  ({sum(counts.values())} records, "
        f"{ops['count'] if ops else 0} endpoints)")
    return dest
