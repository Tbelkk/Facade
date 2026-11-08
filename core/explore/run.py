"""Run the Explorer from the command line (from core/).

    # offline, no API key: structure-only reader + breadth-first planner
    python -m explore.run http://localhost:5005 --offline

    # the real agent: Nemotron Nano Omni reads pages, Nemotron Super plans
    python -m explore.run http://localhost:5005 --budget 25

    # sites behind a login
    python -m explore.run http://localhost:5005 --login env              # FACADE_LOGIN_USER/PASS from core/.env
    python -m explore.run http://localhost:5005 --login manual --headed  # you type the password

    # also stream events + the site map to SpacetimeDB
    python -m explore.run http://localhost:5005 --sink spacetime

Output: core/cache/explore/<host>_<time>/site_map.json (+ pages/, shots/, events.jsonl)
        core/cache/explore/latest_site_map.json
"""
import argparse
import json
import sys

from .explorer import ExploreConfig, Explorer, validate_site_map


def main(argv=None):
    ap = argparse.ArgumentParser(description="Facade Explorer: map a website, read-only.")
    ap.add_argument("url")
    ap.add_argument("--budget", type=int, default=None, help="max page types to map (default EXPLORE_PAGE_BUDGET or 25)")
    ap.add_argument("--offline", action="store_true", help="no Nemotron: heuristic reader and planner")
    ap.add_argument("--reader", choices=["nemotron", "heuristic"], default=None)
    ap.add_argument("--planner", choices=["nemotron", "heuristic"], default=None)
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--login", choices=["none", "env", "manual"], default="none")
    ap.add_argument("--sink", choices=["json", "spacetime"], default="json")
    ap.add_argument("--out", default="", help="run folder (default core/cache/explore/<host>_<time>)")
    ap.add_argument("--no-screenshots", action="store_true", help="faster; the reader sees only the DOM")
    ap.add_argument("--reasoning-budget", type=int, default=0)
    args = ap.parse_args(argv)

    import os
    from ingest import nemotron  # noqa: F401  (loads core/.env)

    budget = args.budget or int(os.getenv("EXPLORE_PAGE_BUDGET", "25"))
    default_ai = "heuristic" if args.offline else "nemotron"
    cfg = ExploreConfig(
        start_url=args.url, page_budget=budget, headless=not args.headed,
        reader=args.reader or default_ai, planner=args.planner or default_ai,
        sink=args.sink, out_dir=args.out, login=args.login,
        screenshots=not args.no_screenshots, reasoning_budget=args.reasoning_budget,
    )
    if "nemotron" in (cfg.reader, cfg.planner):
        key = os.getenv("NVIDIA_API_KEY", "")
        if not key or "paste" in key:
            raise SystemExit("NVIDIA_API_KEY is missing. Put it in core/.env, or add --offline to run without Nemotron.")

    result = Explorer(cfg).run()
    sm = result["site_map"]
    problems = validate_site_map(sm)

    print("\n=== Site map ===")
    for p in sm["pages"]:
        extra = ""
        if p.get("pagination"):
            extra += f"  [paged, {p['pagination'].get('page_size', '?')}/page]"
        if p.get("row_link"):
            extra += f"  [rows -> {p['row_link']['goes_to']}]"
        print(f"  {p['id']:<24} {p['kind']:<7} {str(p.get('entity') or ''):<14} {p['url_pattern']}{extra}")
    print(f"  edges: {len(sm['edges'])}   unexplored: {sm['unexplored'][:8]}")
    for n in sm["notes"]:
        print(f"  note: {n}")
    print(f"  stats: {json.dumps(sm['stats'])}")
    print(f"\nSaved {result['site_map_path']}")
    if problems:
        print("FORMAT PROBLEMS:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
