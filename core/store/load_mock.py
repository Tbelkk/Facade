"""Load mock "Nemotron output" into SpacetimeDB, through the same reducers the real agents use.

Run from the core/ folder:
    python -m store.load_mock                 # loads every site in shared/formats/mock/
    python -m store.load_mock bookstore       # loads just one
    python -m store.load_mock --clear-only    # removes the mock sites again

Each run first clears that site, so running it twice never doubles anything.
When the real Explorer/Operator run, their data goes into the same tables under
the real site's URL, so mock and real data never mix.
"""

import json
import sys
from pathlib import Path

from store import spacetime as db

MOCK_DIR = Path(__file__).resolve().parents[2] / "shared" / "formats" / "mock"


def read(folder: Path, name: str):
    return json.loads((folder / name).read_text(encoding="utf-8"))


def load_site(folder: Path) -> bool:
    site = read(folder, "site.json")
    url = site["url"]
    print(f"\n== {folder.name}  ({url})")

    if not db.clear_site(url):
        print("   Could not reach SpacetimeDB. Check SPACETIME_HOST / SPACETIME_DB and that the module is published.")
        return False

    # 1. What the Explorer would save: site map, data model, operations, docs
    db.save_site(url, site["site_map"], site["model"], site["operations"], site.get("docs_md", ""))
    rules = site["model"].get("rules", [])
    for entity in site["model"]["entities"]:
        db.upsert_schema(url, entity["name"], entity["fields"],
                         [r for r in rules if r.get("entity") == entity["name"]])
    print(f"   site map, data model, {len(site['operations']['operations'])} operations")

    # 2. What the Operator would save: extracted records
    records = read(folder, "records.json")
    for entity, rows in records.items():
        failed = 0
        for row in rows:
            if not db.upsert_record(url, entity, row["legacy_id"], row["data"]):
                failed += 1
        print(f"   {entity}: {len(rows) - failed}/{len(rows)} records")

    # 3. Progress bars
    for job in read(folder, "jobs.json"):
        db.start_job(job["job_key"], url, job["kind"], job.get("entity", ""), job["total"])
        db.update_job(job["job_key"], job["done"], job["total"], job["status"])

    # 4. Write requests in every state (pending / running / done / failed)
    ops = read(folder, "op_requests.json")
    for op in ops:
        db.request_op(op["request_key"], url, op["operation"], op["inputs"])
        if op["status"] == "pending":
            continue
        rows = db.sql("SELECT id FROM op_request WHERE request_key = " + db.quote(op["request_key"]))
        if not rows:
            print(f"   could not find op {op['request_key']} after creating it")
            continue
        op_id = rows[0]["id"]
        db.claim_op(op_id)
        if op["status"] in ("done", "failed"):
            db.finish_op(op_id, op["status"] == "done", op.get("result"), op.get("error", ""))
    print(f"   {len(ops)} op requests")

    # 5. Activity log
    events = read(folder, "events.json")
    for ev in events:
        db.log_event(url, ev["actor"], ev["message"], ev.get("data"), ev.get("level", "info"))
    print(f"   {len(events)} events")
    return True


def main(argv):
    folders = sorted(p for p in MOCK_DIR.iterdir() if (p / "site.json").exists())
    names = [a for a in argv if not a.startswith("--")]
    if names:
        folders = [f for f in folders if f.name in names]
        if not folders:
            print(f"No mock site named {names}. Available: {[p.name for p in MOCK_DIR.iterdir() if p.is_dir()]}")
            return 1

    print(f"SpacetimeDB: {db.HOST}  database: {db.DB}")
    if "--clear-only" in argv:
        for f in folders:
            url = read(f, "site.json")["url"]
            print(("cleared " if db.clear_site(url) else "FAILED to clear ") + url)
        return 0

    ok = all([load_site(f) for f in folders])
    print("\nDone." if ok else "\nFinished with errors (see above).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
