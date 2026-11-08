"""The whole Facade workflow from one URL. This is what the Console's Start button calls.

    python -m facade.run https://news.ycombinator.com
    python -m facade.run http://localhost:5005 --login        # a person logs in once in the browser
    python -m facade.run <url> --offline-design               # API design without Nemotron
    python -m facade.run <url> --pause 2 --minutes 20         # go easy on a fragile old server

  1. Explore + extract   (explore.agent, Nemotron)   writes to SpacetimeDB live as it goes
  2. Design the API      (operator_agent, Nemotron)  operations.json + api_docs.md
  3. Publish             (extract.handoff)           shared/output/<site>/
  4. Load                (store.load_run)            final data model, API design, docs, all records
  5. Serve               (serve.run)                 starts the REST API + MCP server, self-tests every route and tool

Every step also leaves its files on disk, so a database problem never loses a run.
"""
import argparse
import time

from ingest import nemotron  # noqa: F401  (loads core/.env)


def run(url, login=False, headed=False, offline_design=False, full=False, live=True, serve=True, port=8000,
        pause=None, minutes=None, pages=None):
    from explore import agent
    from extract.handoff import publish
    from operator_agent import run as operator
    from store.load_run import load

    from facade.events import emit
    t0 = time.time()
    emit({"stage": "run", "kind": "start", "site": url})
    print("== 1/5  Explore + extract ==")
    r = agent.run(url, max_pages=pages, login=login, headed=headed, full=full, live=live, pause=pause, minutes=minutes)
    if not r.records:
        raise SystemExit("No records were extracted, so there is nothing to design an API for. See the run log above.")

    print("\n== 2/5  Design the API (operator agent) ==")
    emit({"stage": "operator", "kind": "start"})
    doc = operator.run(r.dir, use_nemotron=False if offline_design else None)
    meta = doc.get("designed_by") or {}
    emit({"stage": "operator", "kind": "proposed", "operations": doc["operations"], "problems": meta.get("problems_found") or []})
    if meta.get("problems_found"):
        emit({"stage": "operator", "kind": "fixed", "problems": meta.get("problems_after_fix") or []})
    emit({"stage": "operator", "kind": "done", "operations": doc["operations"], "designed_by": meta})

    print("\n== 3/5  Publish ==")
    dest = publish(r.dir)

    print("\n== 4/5  Load into SpacetimeDB ==")
    load(dest, progress=lambda tables: emit({"stage": "database", "target": "SpacetimeDB", "tables": tables}))

    print(f"\n== 5/5  Start the API + MCP server ==   (steps 1-4 took {(time.time() - t0) / 60:.1f} min, output: {dest})")
    from serve.run import run as serve_run
    serve_run(dest, port=port, check_only=not serve, live=live)
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser(description="Facade: website -> database + API design, in one go")
    ap.add_argument("url")
    ap.add_argument("--login", action="store_true", help="log in by hand first (the session is reused)")
    ap.add_argument("--headed", action="store_true", help="show the browser")
    ap.add_argument("--offline-design", action="store_true", help="design the API without Nemotron")
    ap.add_argument("--full", action="store_true", help="page through every list to the end (slow on big sites)")
    ap.add_argument("--no-live", action="store_true", help="don't write to SpacetimeDB during the run")
    ap.add_argument("--no-serve", action="store_true", help="self-test the API + MCP server, then exit instead of serving")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--pause", type=float, default=None, help="seconds between page loads (speed limit for old servers)")
    ap.add_argument("--minutes", type=float, default=None, help="stop exploring after this many minutes")
    ap.add_argument("--pages", type=int, default=None, help="stop exploring after this many pages")
    a = ap.parse_args(argv)
    run(a.url, login=a.login, headed=a.headed, offline_design=a.offline_design, full=a.full, live=not a.no_live,
        serve=not a.no_serve, port=a.port, pause=a.pause, minutes=a.minutes, pages=a.pages)


if __name__ == "__main__":
    main()
