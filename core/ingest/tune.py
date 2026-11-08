"""Tune Nemotron labeling: run one snapshot at several reasoning budgets and compare.

Usage (from core/):
    python -m ingest.tune --snapshot ../shared/fixtures/snapshot.json
    python -m ingest.tune --snapshot cache/snapshots/snap_123.json --budgets 512 1024 4096 --runs 2

For every budget it prints speed + quality signals, and saves a Screen Model to
cache/screens/<snapshot_id>__b<budget>/screen.json, so the Inspector's dropdown shows the
versions side by side (python -m ingest.inspect, then click the refresh button).
Results also go to cache/tune/<snapshot_id>.json so you can paste them to teammates.
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from . import label as label_mod
from . import nemotron, screen_model
from .paths import CACHE_DIR, resolve
from .style import style_profile

INTERACTIVE_UIA = {"Button", "Edit", "ComboBox", "CheckBox", "RadioButton", "List", "ListItem", "DataGrid",
                   "Table", "TabItem", "MenuItem", "Hyperlink", "Spinner", "Slider", "TreeItem"}


def quality(labels, snapshot):
    """Signals that don't need a 'correct answer' file."""
    nodes = snapshot.get("nodes", [])
    interactive = [n for n in nodes if n["role"] in INTERACTIVE_UIA]
    labeled = [n for n in interactive if str(n["id"]) in labels.get("controls", {})]
    ctrls = labels.get("controls", {}).values()
    cryptic_fixed = 0
    for n in interactive:
        c = labels.get("controls", {}).get(str(n["id"]))
        raw = (n.get("name") or n.get("automation_id") or "").strip()
        if c and raw and c["label"].strip().lower() != raw.lower():
            cryptic_fixed += 1
    return {
        "coverage": round(len(labeled) / len(interactive), 2) if interactive else None,
        "controls": len(labels.get("controls", {})),
        "groups": len(labels.get("groups", [])),
        "vision_regions": len(labels.get("vision_regions", [])),
        "hidden": sum(1 for c in ctrls if c.get("importance") == "hide"),
        "risky": sum(1 for c in labels.get("controls", {}).values() if c.get("risk")),
        "renamed": cryptic_fixed,
        "dropped_ids": sum(1 for x in labels.get("notes", []) if "unknown control id" in x),
        "mode": labels.get("mode"),
        "confidence": labels.get("confidence"),
        "error": labels.get("error"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compare reasoning budgets for screen labeling.")
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--budgets", type=int, nargs="+", default=[512, 1024, 2048, 4096])
    ap.add_argument("--runs", type=int, default=1, help="runs per budget (speed varies a lot)")
    ap.add_argument("--no-style", action="store_true", help="skip the style step")
    args = ap.parse_args(argv)

    snap_path = Path(args.snapshot)
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    sid = snapshot.get("snapshot_id", snap_path.stem)
    shot = resolve(snapshot.get("screenshot_path"), snap_path.parent)
    print(f"model={nemotron.MODEL_VISION}  endpoint={nemotron.BASE_URL}")
    print(f"snapshot={sid}  nodes={len(snapshot.get('nodes', []))}  screenshot={'yes' if shot else 'NO'}\n")

    style = None
    if not args.no_style and shot:
        t = time.time()
        style = style_profile(snapshot.get("app", {}).get("process") or "app", shot, snapshot,
                              use_cache=False, use_ai=True)
        print(f"style: {style['traits_source']} in {time.time() - t:.1f}s | identity {style['identity_color']} | "
              f"font {style['original_font']} | {style['traits'][:90]}"
              + (f" | ERROR {style['error']}" if style.get("error") else "") + "\n")

    results = []
    header = f"{'budget':>6} {'run':>3} {'secs':>6} {'cover':>5} {'ctrls':>5} {'grps':>4} {'vis':>3} {'hide':>4} " \
             f"{'risky':>5} {'renamed':>7} {'dropped':>7} {'conf':>5} mode"
    print(header)
    print("-" * len(header))
    for budget in args.budgets:
        for run in range(1, args.runs + 1):
            t = time.time()
            labels = label_mod.label_screen(snapshot, snapshot_dir=snap_path.parent, use_cache=False, budget=budget)
            secs = time.time() - t
            q = quality(labels, snapshot)
            results.append({"budget": budget, "run": run, "secs": round(secs, 2), **q})
            print(f"{budget:>6} {run:>3} {secs:>6.1f} {str(q['coverage']):>5} {q['controls']:>5} {q['groups']:>4} "
                  f"{q['vision_regions']:>3} {q['hidden']:>4} {q['risky']:>5} {q['renamed']:>7} {q['dropped_ids']:>7} "
                  f"{str(q['confidence']):>5} {q['mode']}" + (f"  ERROR: {q['error'][:60]}" if q["error"] else ""))
            out_dir = CACHE_DIR / "screens" / (f"{sid}__b{budget}" + ("" if run == 1 else f"_r{run}"))
            model = screen_model.build(snapshot, labels, style, out_dir=out_dir, screenshot_path=shot)
            model["screen"]["window"]["title"] = f"{model['screen']['window'].get('title')} [budget {budget}]"
            (out_dir / "screen.json").write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nsummary (median seconds per budget):")
    for budget in args.budgets:
        rs = [r for r in results if r["budget"] == budget]
        ok = [r for r in rs if not r["error"]]
        med = statistics.median(r["secs"] for r in rs)
        print(f"  {budget:>5}: {med:5.1f}s  ok {len(ok)}/{len(rs)}  "
              f"avg coverage {round(statistics.mean(r['coverage'] or 0 for r in ok), 2) if ok else '-'}")
    tune_dir = CACHE_DIR / "tune"
    tune_dir.mkdir(parents=True, exist_ok=True)
    (tune_dir / f"{sid}.json").write_text(json.dumps({"snapshot": sid, "model": nemotron.MODEL_VISION,
                                                      "results": results}, indent=2), encoding="utf-8")
    print(f"\nsaved cache/tune/{sid}.json  |  open the Inspector to compare: python -m ingest.inspect")
    print("Pick the LOWEST budget whose labels still look right in the Inspector, then set REASONING_BUDGET in core/.env")


if __name__ == "__main__":
    main()
