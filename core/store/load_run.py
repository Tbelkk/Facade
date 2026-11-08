"""Load one site's agent output into SpacetimeDB.

    python -m store.load_run ../shared/output/hackernews            # the shared handoff folder (preferred)
    python -m store.load_run cache/extract/20261108-010902          # or a raw explore.agent run folder
    python -m store.load_run ../shared/output/hackernews --clear    # wipe this site's rows first

Folder -> reducers (same tables as spacetime/src/index.ts):
    site_map.json + data_model.json + operations.json + api_docs.md  -> save_site
    data_model.json entities                                          -> upsert_schema (one per entity)
    records/<Entity>.jsonl                                            -> upsert_record (one per record, parallel)
    run_log.jsonl (if present)                                        -> log_event (one per line, capped)
    progress                                                          -> start_job / update_job

Records can be either shape:
    {"legacy_id": "42", "hash": "...", "data": {...}}     (shared/output, canonical)
    {"_key": "https://site/item?id=42", "title": ...}       (explore.agent raw run)
Knows nothing about any specific website.
"""
import argparse
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from store import spacetime as db


def _read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _records(path):
    """Yield (legacy_id, data) from a records/<Entity>.jsonl file in either shape."""
    from operator_agent.inputs import legacy_id_of  # same _key -> id rule the API designer uses
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if isinstance(r.get("data"), dict):
            yield str(r.get("legacy_id")), r["data"]
        else:
            data = {k: v for k, v in r.items() if not k.startswith("_")}
            yield legacy_id_of(r), data


def _tables(model, entity, done, total, ev_done, ev_total):
    ents = model.get("entities", [])
    return [{"name": "site", "done": 1, "total": 1, "note": "site map + model + API design"},
            {"name": "entity_schema", "done": len(ents), "total": len(ents), "note": ", ".join(e["name"] for e in ents)},
            {"name": "record", "done": done, "total": total, "note": f"{entity} rows" if entity else "extracted rows"},
            {"name": "event", "done": ev_done, "total": ev_total, "note": "agent log"}]


def load(folder, clear=False, workers=8, max_events=500, progress=None):
    """progress(tables) is called as rows go in: [{name, done, total, note}] (the dashboard's Database tile)."""
    folder = Path(folder)
    model = _read_json(folder / "data_model.json")
    if not model:
        raise SystemExit(f"no data_model.json in {folder}")
    manifest = _read_json(folder / "manifest.json", {}) or {}
    site = model.get("site") or manifest.get("site")
    if not site:
        raise SystemExit("data_model.json has no 'site'")
    site_map = _read_json(folder / "site_map.json", {})
    ops = _read_json(folder / "operations.json", {})
    docs = (folder / "api_docs.md").read_text(encoding="utf-8") if (folder / "api_docs.md").exists() else ""

    print(f"Loading {folder} -> SpacetimeDB {db.HOST} / {db.DB}   site={site}")
    if db.sql("SELECT * FROM site WHERE url = 'x'") is None:
        raise SystemExit("Can't reach SpacetimeDB (check SPACETIME_HOST / SPACETIME_DB in core/.env).")
    if clear:
        print("  clear_site:", db.clear_site(site))

    print("  save_site:", db.save_site(site, site_map, model, ops, docs))
    for e in model.get("entities", []):
        ok = db.upsert_schema(site, e["name"], e.get("fields", []), e.get("rules", []))
        print(f"  upsert_schema {e['name']}:", ok)

    totals = {}
    for path in sorted((folder / "records").glob("*.jsonl")):
        entity = path.stem
        rows = list(_records(path))
        job = f"load-{entity}-{uuid.uuid4().hex[:8]}"
        db.start_job(job, site, "load", entity, len(rows))
        t0, done, failed = time.time(), 0, 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for ok in pool.map(lambda r: db.upsert_record(site, entity, r[0], r[1]), rows):
                done += 1
                failed += 0 if ok else 1
                if done % 200 == 0 or done == len(rows):
                    db.update_job(job, done, len(rows), "running" if done < len(rows) else "done")
                    if progress:
                        progress(_tables(model, entity, done, len(rows), 0, 0))
                    print(f"\r  {entity}: {done}/{len(rows)}  ({failed} failed)", end="", flush=True)
        print(f"   {time.time() - t0:.1f}s")
        totals[entity] = (len(rows) - failed, len(rows))

    log = folder / "run_log.jsonl"
    n_events = 0
    if log.exists():
        lines = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()][:max_events]
        for ev in lines:
            kind = ev.get("kind", "event")
            msg = (f"{ev.get('page_type') or '?'} {ev.get('entity') or ''} +{ev.get('records_new', 0)}  {ev.get('url', '')}"
                   if kind == "page" else f"{kind}: {ev.get('error') or ev.get('reason') or ev.get('url') or ''}")
            db.log_event(site, "explorer", msg.strip(), ev, "error" if "fail" in kind or kind == "error" else "info")
        print(f"  log_event: {len(lines)} events")
        n_events = len(lines)
    if progress:
        rec_total = sum(t for _, t in totals.values())
        progress(_tables(model, None, rec_total, rec_total, n_events, n_events))

    print("\nCheck (rows now in the database):")
    for entity, (ok, total) in totals.items():
        rows = db.sql(f"SELECT * FROM record WHERE site = {db.quote(site)} AND entity = {db.quote(entity)}") or []
        print(f"  {entity}: sent {ok}/{total}, database has {len(rows)}")
    return totals


def main(argv=None):
    ap = argparse.ArgumentParser(description="Load a Facade output folder into SpacetimeDB")
    ap.add_argument("folder")
    ap.add_argument("--clear", action="store_true", help="delete this site's rows first")
    ap.add_argument("--workers", type=int, default=8, help="parallel reducer calls")
    args = ap.parse_args(argv)
    load(args.folder, clear=args.clear, workers=args.workers)


if __name__ == "__main__":
    main()
