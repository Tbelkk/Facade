"""One command: mock website -> Explorer -> recipes -> Extractor -> SpacetimeDB-shaped JSON -> check vs. the data.

    python -m mock_sites.run clinic                 # heuristic explorer, no API key needed
    python -m mock_sites.run inventory --nemotron   # Nemotron reads and plans the pages
    python -m mock_sites.run path/to/my_site.json --headed

Output: core/cache/mock/<name>_<time>/  (site_map.json, recipes.json, pages/, extract/...)
"""
import argparse
import json
import os
import time
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent


def run(name, nemotron=False, headed=False, out=None, quiet=False):
    from explore.explorer import ExploreConfig, Explorer
    from extract.extractor import Extractor

    from . import compare, server

    if quiet:
        os.environ["FACADE_QUIET"] = "1"
    srv = server.start(name)
    try:
        site = srv.site
        login = site["login"] or {}
        slug = Path(site["_file"]).stem
        out = Path(out) if out else CORE / "cache" / "mock" / f"{slug}_{time.strftime('%Y%m%d-%H%M%S')}"
        mode = "nemotron" if nemotron else "heuristic"
        cfg = ExploreConfig(start_url=srv.url + "/", out_dir=str(out), reader=mode, planner=mode, headless=not headed,
                            screenshots=nemotron, login="env" if login else "none",
                            username=login.get("username", ""), password=login.get("password", ""))
        explored = Explorer(cfg).run()
        writes_during_explore = list(srv.writes)
        ex = Extractor(out, login="env" if login else "none", username=login.get("username", ""),
                       password=login.get("password", ""), headless=not headed)
        res = ex.run()
        data = json.loads((out / "extract" / "data.json").read_text(encoding="utf-8"))
        report = compare.compare(site, data, explored["recipes"])
        (out / "extract" / "check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        from operator_agent import run as operator_run
        api = operator_run.run(out, use_nemotron=nemotron, log=(lambda *a: None) if quiet else print)
        from extract import view
        view.render(out / "extract")  # again, now with the ground-truth check + API design on the page
        return {"out": str(out), "url": srv.url, "explore": explored["site_map"]["stats"], "extract": res,
                "check": report, "writes": list(srv.writes), "writes_during_explore": writes_during_explore,
                "session_expired": srv.expired, "api": api}
    finally:
        srv.shutdown()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Test the agents on a mock website")
    ap.add_argument("site", nargs="?", default="clinic", help="name in mock_sites/data/ or a path to a .json file")
    ap.add_argument("--offline", action="store_true",
                    help="no Nemotron: heuristic reader + planner (default is Nemotron when NVIDIA_API_KEY is set)")
    ap.add_argument("--nemotron", action="store_true", help="require Nemotron (fail if NVIDIA_API_KEY is missing)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--serve", action="store_true", help="then serve the results page (http://127.0.0.1:5070)")
    ap.add_argument("--port", type=int, default=5070)
    ap.add_argument("--no-publish", action="store_true", help="do not publish to shared/output/<site>/")
    a = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv(CORE / ".env")
    except ImportError:
        pass
    has_key = os.getenv("NVIDIA_API_KEY", "").startswith("nvapi-") and "paste" not in os.getenv("NVIDIA_API_KEY", "")
    if a.nemotron and not has_key:
        raise SystemExit("--nemotron needs NVIDIA_API_KEY in core/.env")
    use_nemotron = has_key and not a.offline
    print(f"Agent: {'NVIDIA Nemotron (reader ' + os.getenv('MODEL_VISION', '?') + ', planner ' + os.getenv('MODEL_AGENT', '?') + ')' if use_nemotron else 'offline heuristics (no Nemotron)'}")
    r = run(a.site, nemotron=use_nemotron, headed=a.headed, out=a.out or None)
    s = r["explore"]
    print("\n================ RESULT ================")
    print(f"Explorer: {s['page_types']} page types, stop={s['stop_reason']}, reader={s['reader']}, planner={s['planner']}")
    if use_nemotron:
        print(f"Nemotron: {s['nemotron_calls']} calls, {s['nemotron_ms'] / 1000:.1f}s total, "
              f"{s['nemotron_fallbacks']} fallback(s) to heuristics")
    print(f"Extract:  {r['extract']['records']} records {json.dumps(r['extract']['entities'])}, "
          f"session expired {r['session_expired']}x, re-logins {r['extract']['relogins']}")
    for d in r["extract"]["duplicates"]:
        print(f"  possible duplicate {d['entity']}: {d['legacy_ids']}")
    ok = True
    for ent, c in r["check"].items():
        flag = "OK " if c["accuracy"] == 100.0 and not c["extra"] else "BAD"
        ok &= flag == "OK "
        print(f"  [{flag}] {ent}: {c['extracted']}/{c['expected']} records, {c['fields_checked'] - c['fields_wrong']}"
              f"/{c['fields_checked']} fields right ({c['accuracy']}%)")
        for m in c["mismatches"][:5]:
            print(f"        {m['legacy_id']}.{m['field']}: expected {m['expected']!r}, got {m['got']!r}")
        if c["missing"]:
            print(f"        missing ids: {c['missing'][:10]}")
    print(f"Writes reaching the site: {len(r['writes'])} (must be 0)")
    m = r["api"]["designed_by"]
    print(f"Operator: {len(r['api']['operations'])} endpoints designed by {m['by']}"
          + (f" ({m['attempts']} Nemotron call(s), {len(m['problems_found'])} problem(s) found, "
             f"{len(m['problems_after_fix'])} left)" if m["by"] == "nemotron" else ""))
    for o in r["api"]["operations"]:
        print(f"  {o['method']:6} {o['path']:28} {o['source']}")
    print(f"\nOutput: {r['out']}/extract/  ->  spacetime/*.json  schema.json  data.json  check.json")
    print(f"        {r['out']}/  ->  data_model.json  records/  operations.json  api_docs.md")
    if not a.no_publish:
        from extract.handoff import publish
        publish(r["out"])
    if a.serve:
        from extract import view
        view.serve(Path(r["out"]) / "extract", a.port)
    else:
        print("See it as a web page:  python -m extract.view   ->  http://127.0.0.1:5070")
    raise SystemExit(0 if ok and not r["writes"] else 1)


if __name__ == "__main__":
    main()
