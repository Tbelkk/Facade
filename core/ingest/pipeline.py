"""End-to-end ingest: snapshot -> labels (6.2) + style profile (6.3).

Usage (from core/):
    python -m ingest.pipeline --snapshot ../shared/fixtures/snapshot.json     # any OS
    python -m ingest.pipeline --live                                         # Windows: capture the front window
Writes cache/screens/<snapshot_id>/screen.json   <- the Screen Model the overlay receives (schema_version 1)
       cache/screens/<snapshot_id>/shots/...     <- screenshot + crops of custom-drawn regions
       cache/screens/<snapshot_id>/debug.json    <- raw snapshot + labels + style, for debugging
"""
import argparse
import json
import sys
import time
from pathlib import Path

from . import screen_model
from .label import label_screen
from .paths import CACHE_DIR, resolve
from .style import style_profile

SCREENS_DIR = CACHE_DIR / "screens"


def run(snapshot, snapshot_dir=None, use_cache=True, use_ai_style=True, budget=None, out_dir=None):
    t0 = time.time()
    labels = label_screen(snapshot, snapshot_dir=snapshot_dir, use_cache=use_cache, budget=budget)
    t1 = time.time()
    shot = resolve(snapshot.get("screenshot_path"), snapshot_dir)
    app_key = snapshot.get("app", {}).get("process") or "unknown_app"
    style = style_profile(app_key, shot, snapshot, use_cache=use_cache, use_ai=use_ai_style, budget=budget) \
        if shot else None
    t2 = time.time()
    model = screen_model.build(snapshot, labels, style, out_dir=out_dir, screenshot_path=shot)
    t3 = time.time()
    return {"model": model, "snapshot": snapshot, "labels": labels, "style": style,
            "timing_ms": {"label": int((t1 - t0) * 1000), "style": int((t2 - t1) * 1000),
                          "model": int((t3 - t2) * 1000), "total": int((t3 - t0) * 1000)}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="RESTore ingest pipeline")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--snapshot", help="snapshot JSON file")
    src.add_argument("--live", action="store_true", help="Windows only: capture the window in front")
    ap.add_argument("--delay", type=int, default=3)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--no-ai-style", action="store_true")
    ap.add_argument("--budget", type=int, default=None)
    args = ap.parse_args(argv)

    if args.live:
        from .capture import capture_foreground, summarize
        snapshot = capture_foreground(args.delay)
        summarize(snapshot)
        snap_dir = None
    else:
        p = Path(args.snapshot)
        snapshot = json.loads(p.read_text(encoding="utf-8"))
        snap_dir = p.parent

    out_dir = SCREENS_DIR / snapshot.get("snapshot_id", "screen")
    screen = run(snapshot, snap_dir, use_cache=not args.no_cache, use_ai_style=not args.no_ai_style,
                 budget=args.budget, out_dir=out_dir)
    out = out_dir / "screen.json"
    out.write_text(json.dumps(screen["model"], indent=2, ensure_ascii=False), encoding="utf-8")
    debug = {k: screen[k] for k in ("snapshot", "labels", "style", "timing_ms")}
    (out_dir / "debug.json").write_text(json.dumps(debug, indent=2, ensure_ascii=False), encoding="utf-8")
    problems = screen_model.check(screen["model"])

    lb, st = screen["labels"], screen["style"]
    print(f"\nLABELS  {lb['screen_type']} | mode={lb['mode']} | confidence={lb['confidence']} | "
          f"{len(lb['controls'])} controls, {len(lb['groups'])} groups, {len(lb['vision_regions'])} vision regions"
          f"{' | CACHED' if lb.get('cached') else ''}")
    print(f"        {lb['purpose']}")
    if lb.get("error"):
        print("        ERROR:", lb["error"], file=sys.stderr)
    if st:
        print(f"STYLE   {st['theme']} | {st['density']} | identity {st['identity_color']} | "
              f"primary {st['tokens']['color.primary']} | contrast ok={st['contrast_checked']}"
              f"{' | CACHED' if st.get('cached') else ''}")
    print(f"MODEL   screen.id={screen['model']['screen']['id']} | schema valid={not problems}"
          f"{'' if not problems else ' ' + str(problems[:5])}")
    print(f"TIMING  {screen['timing_ms']}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
