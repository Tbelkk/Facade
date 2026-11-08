"""Operator agent (agent 2): explored + extracted data -> an API design.

    python -m operator_agent.run <run folder>              # Nemotron designs (NVIDIA_API_KEY in core/.env)
    python -m operator_agent.run <run folder> --offline    # code-only design, no API key
    python -m operator_agent.run operator_agent/examples/news

Reads  <run folder>/data_model.json, site_map.json, records/<Entity>.jsonl
Writes <run folder>/operations.json and api_docs.md
"""
import argparse
import json
import os
import time
from pathlib import Path

from . import design as design_mod, docs, inputs

CORE = Path(__file__).resolve().parent.parent


def run(run_dir, use_nemotron=None, log=print):
    run_dir = Path(run_dir)
    dm, site_map, records = inputs.load(run_dir)
    if use_nemotron is None:
        key = os.getenv("NVIDIA_API_KEY", "")
        use_nemotron = key.startswith("nvapi-") and "paste" not in key
    ops, meta = design_mod.design(dm, records, use_nemotron=use_nemotron, log=log)
    docs.add_examples(ops, records)
    doc = {"version": 1, "site": dm.get("site") or site_map.get("site"),
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "designed_by": meta,
           "entities": {e["name"]: {"key": "legacy_id", "record_count": len(records.get(e["name"], [])),
                                    "fields": e["fields"]} for e in dm["entities"]},
           "operations": ops}
    (run_dir / "operations.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (run_dir / "api_docs.md").write_text(docs.markdown(doc, dm), encoding="utf-8")
    log(f"Operator: {len(ops)} endpoints designed by {meta['by']} -> {run_dir / 'operations.json'}, api_docs.md")
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description="Facade Operator: design the API for extracted data")
    ap.add_argument("run_dir")
    ap.add_argument("--offline", action="store_true", help="code-only design (no Nemotron)")
    ap.add_argument("--no-publish", action="store_true", help="do not update the handoff folder core/cache/latest/")
    a = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv(CORE / ".env")
    except ImportError:
        pass
    doc = run(a.run_dir, use_nemotron=False if a.offline else None)
    for o in doc["operations"]:
        print(f"  {o['method']:6} {o['path']:32} {o['source']:8} {o['name']}")
    if not a.no_publish:
        from extract.handoff import publish
        publish(a.run_dir)


if __name__ == "__main__":
    main()
