"""Extract every record from a site the explorer already mapped.

    python -m extract.run <run folder>                    # site without login
    python -m extract.run <run folder> --login env        # FACADE_LOGIN_USER / FACADE_LOGIN_PASS from core/.env
    python -m extract.run <run folder> --login manual --headed

Writes <run folder>/extract/ (see extract/spacetime_export.py for every file).
"""
import argparse
import json
import os


def main(argv=None):
    ap = argparse.ArgumentParser(description="Facade: extract records using the explorer's recipes.json")
    ap.add_argument("run_dir")
    ap.add_argument("--login", choices=["none", "env", "manual"], default="none")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="max records per entity (0 = all)")
    ap.add_argument("--out", default="", help="output folder (default <run folder>/extract)")
    ap.add_argument("--no-publish", action="store_true", help="do not update the handoff folder core/cache/latest/")
    a = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    from .extractor import Extractor

    ex = Extractor(a.run_dir, login=a.login, headless=not a.headed, limit=a.limit, out_dir=a.out or None,
                   username=os.getenv("FACADE_LOGIN_USER", ""), password=os.getenv("FACADE_LOGIN_PASS", ""))
    res = ex.run()
    print(f"\n{res['records']} records: {json.dumps(res['entities'])}  re-logins: {res['relogins']}  "
          f"duplicate groups: {len(res['duplicates'])}")
    print(f"Output: {res['out_dir']}  (spacetime/*.json, schema.json, data.json)")
    if not a.no_publish and not a.out:
        from .handoff import publish
        publish(a.run_dir)


if __name__ == "__main__":
    main()
