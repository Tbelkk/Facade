"""The shared handoff folder, tracked in git: shared/output/<site>/

Every agent's final output for a site lands here, in one layout, so the SpacetimeDB server reads one place:

    shared/output/
        index.json                 every published site + which one is newest ("latest")
        <site>/
            manifest.json          which run, when, record counts, endpoint count, files present
            data_model.json        entities, typed fields, relations, forms   -> upsert_schema
            records/<Entity>.jsonl the extracted data                          -> upsert_record
            site_map.json          page types                                  -> save_site
            operations.json        the API design (Operator)                   -> endpoints + MCP tools
            api_docs.md            readable API docs with real examples
            recipes.json, schema.json, spacetime/<table>.json   (when the run produced them)

A site folder is replaced as a whole on each publish (never a mix of two runs).
FACADE_OUTPUT_DIR moves the root (default: <repo>/shared/output).
"""
import json
import os
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit

CORE = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = CORE.parent / "shared" / "output"

FILES = ["data_model.json", "site_map.json", "operations.json", "api_docs.md", "recipes.json"]
DIRS = {"records": "records", "extract/spacetime": "spacetime"}
EXTRA = {"extract/schema.json": "schema.json"}
_STAMP = re.compile(r"_\d{8}-\d{6}$")


def output_root():
    return Path(os.getenv("FACADE_OUTPUT_DIR") or DEFAULT_ROOT)


def site_name(run_dir, site_url=None):
    """clinic_20261108-001314 -> clinic ; shared/samples/hackernews -> hackernews ; else the host."""
    name = _STAMP.sub("", Path(run_dir).resolve().name)
    if name and not re.fullmatch(r"[\d_]+", name):
        return re.sub(r"[^a-z0-9_-]+", "_", name.lower()).strip("_")
    host = urlsplit(site_url or "").netloc or "site"
    return re.sub(r"[^a-z0-9]+", "_", host.lower()).strip("_")


def _canonicalize(run_dir, tmp):
    """Flat records ({"_key": url, field: "62"}) -> {"legacy_id", "hash", "extracted_at", "data"} with typed values,
    and the data model's types made canonical, so the server only ever sees one shape. Returns True if converted."""
    rec_dir = tmp / "records"
    if not rec_dir.is_dir() or not (tmp / "data_model.json").exists():
        return False
    flat = False
    for p in rec_dir.glob("*.jsonl"):
        first = next((l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()), None)
        if first and "data" not in json.loads(first):
            flat = True
    if not flat:
        return False
    import hashlib

    from operator_agent import inputs
    dm, _, records = inputs.load(run_dir)
    for e in dm["entities"]:
        with (rec_dir / f"{e['name']}.jsonl").open("w", encoding="utf-8") as f:
            for r in records.get(e["name"], []):
                data = {k: v for k, v in r.items() if k != "legacy_id"}
                h = hashlib.sha1(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
                f.write(json.dumps({"legacy_id": r["legacy_id"], "hash": h, "extracted_at": None, "data": data},
                                   ensure_ascii=False) + "\n")
    (tmp / "data_model.json").write_text(json.dumps(dm, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def publish(run_dir, name=None, root=None, log=print):
    """Copy a run folder's outputs to shared/output/<name>/ (atomically) and update shared/output/index.json."""
    run_dir = Path(run_dir).resolve()
    root = Path(root or output_root())
    site = None
    for f in ("data_model.json", "site_map.json"):
        if (run_dir / f).exists():
            site = json.loads((run_dir / f).read_text(encoding="utf-8")).get("site")
            if site:
                break
    name = name or site_name(run_dir, site)
    dest = root / name
    if dest.resolve() == run_dir:
        raise ValueError(f"{run_dir} is already the published folder")
    tmp = root / f".{name}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    present = []
    for f in FILES:
        if (run_dir / f).exists():
            shutil.copy2(run_dir / f, tmp / f)
            present.append(f)
    for src, out in EXTRA.items():
        if (run_dir / src).exists():
            shutil.copy2(run_dir / src, tmp / out)
            present.append(out)
    for src, out in DIRS.items():
        if (run_dir / src).is_dir():
            shutil.copytree(run_dir / src, tmp / out, ignore=shutil.ignore_patterns("*.csv"))
            present += [f"{out}/{p.name}" for p in sorted((tmp / out).iterdir())]
    normalized = _canonicalize(run_dir, tmp)
    counts = {p.stem: sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
              for p in sorted((tmp / "records").glob("*.jsonl"))} if (tmp / "records").is_dir() else {}
    ops = None
    if (tmp / "operations.json").exists():
        doc = json.loads((tmp / "operations.json").read_text(encoding="utf-8"))
        ops = {"count": len(doc["operations"]), "designed_by": doc.get("designed_by", {}).get("by"),
               "model": doc.get("designed_by", {}).get("model")}
    try:
        source = str(run_dir.relative_to(CORE.parent))
    except ValueError:
        source = str(run_dir)
    manifest = {"name": name, "site": site, "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "source_run": source, "records": counts, "operations": ops, "files": present,
                "normalized_from_flat_records": normalized}
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    old = root / f".{name}.old"
    shutil.rmtree(old, ignore_errors=True)
    if dest.exists():
        dest.rename(old)
    tmp.rename(dest)
    shutil.rmtree(old, ignore_errors=True)

    idx_path = root / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"sites": {}}
    idx["sites"][name] = {k: manifest[k] for k in ("site", "published_at", "records", "operations")}
    idx["sites"] = dict(sorted(idx["sites"].items()))
    idx["latest"] = name
    idx_path.write_text(json.dumps(idx, indent=2) + "\n", encoding="utf-8")
    log(f"Handoff: published to {dest}  ({sum(counts.values())} records, {ops['count'] if ops else 0} endpoints)")
    return dest
