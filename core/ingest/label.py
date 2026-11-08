"""Screen Snapshot (6.1) -> Screen Labels (6.2) using Nemotron 3 Nano Omni.

Usage (from core/):
    python -m ingest.label ../shared/fixtures/snapshot.json
    python -m ingest.label cache/snap_123.json --no-cache --budget 512
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from . import nemotron
from .paths import CACHE_DIR, PROMPTS_DIR, resolve

KINDS = {"text_input", "number_input", "date_input", "dropdown", "checkbox", "radio", "button",
         "table", "list", "tab", "label", "menu", "other"}
IMPORTANCE = {"high", "medium", "low", "hide"}
RISKS = {"write", "destructive"}
REGION_KINDS = {"table", "calendar", "chart", "canvas", "other"}

ASSIST_BELOW = 0.6        # confidence under this -> assist mode
VISION_BELOW = 0.4        # identified-node ratio under this -> vision mode
PROMPT_FILE = PROMPTS_DIR / "label_v1.md"
LABEL_CACHE = CACHE_DIR / "labels"


# ---------- helpers ----------

def identified_ratio(snapshot):
    nodes = snapshot.get("nodes", [])
    if not nodes:
        return 0.0
    named = sum(1 for n in nodes if (n.get("name") or n.get("automation_id")))
    return named / len(nodes)


def compact_tree(snapshot, max_value=40):
    """Accessibility tree as a compact table (far fewer tokens than raw JSON)."""
    wr = snapshot.get("window_rect", {"x": 0, "y": 0})
    lines = ["id|parent|role|name|automation_id|value|actions|x,y,w,h"]
    for n in snapshot.get("nodes", []):
        r = n.get("rect", {})
        val = n.get("value")
        val = "" if val is None else str(val).replace("\n", " ")[:max_value]
        name = (n.get("name") or "").replace("|", "/").replace("\n", " ")[:60]
        lines.append("|".join([
            str(n["id"]),
            "" if n.get("parent") is None else str(n["parent"]),
            n.get("role", ""),
            name,
            n.get("automation_id", "") or "",
            val,
            ",".join(n.get("actions", [])),
            f'{r.get("x", 0) - wr.get("x", 0)},{r.get("y", 0) - wr.get("y", 0)},{r.get("w", 0)},{r.get("h", 0)}',
        ]))
    return "\n".join(lines)


def cache_path(fingerprint):
    h = hashlib.sha1(fingerprint.encode()).hexdigest()[:16]
    return LABEL_CACHE / f"{h}.json"


# ---------- validation ----------

def _box_to_screen(box, snapshot, scale):
    """Model box (sent-image pixels, window-relative) -> physical screen pixels (contract 6.1 space)."""
    if isinstance(box, dict):
        vals = [box.get("x"), box.get("y"), box.get("w"), box.get("h")]
    elif isinstance(box, (list, tuple)) and len(box) == 4:
        vals = list(box)
    else:
        return None
    try:
        x, y, w, h = (float(v) for v in vals)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    wr = snapshot.get("window_rect", {"x": 0, "y": 0, "w": 10**9, "h": 10**9})
    x, y, w, h = x * scale, y * scale, w * scale, h * scale
    # clamp inside the window
    ww, wh = wr.get("w", 10**9), wr.get("h", 10**9)
    x, y = max(0, min(x, ww)), max(0, min(y, wh))
    w, h = min(w, ww - x), min(h, wh - y)
    if w <= 0 or h <= 0:
        return None
    return {"x": int(x + wr.get("x", 0)), "y": int(y + wr.get("y", 0)), "w": int(w), "h": int(h)}


def validate(raw, snapshot, scale=1.0):
    """Clean the model's answer into contract 6.2.

    Returns (labels, hard_errors, soft_notes). Hard errors trigger one repair retry.
    """
    hard, soft = [], []
    if not isinstance(raw, dict):
        return None, ["answer is not a JSON object"], soft

    node_ids = {n["id"] for n in snapshot.get("nodes", [])}
    nodes_by_id = {n["id"]: n for n in snapshot.get("nodes", [])}

    screen_type = raw.get("screen_type")
    if not isinstance(screen_type, str) or not screen_type.strip():
        hard.append("missing screen_type")
        screen_type = "unknown"
    purpose = raw.get("purpose") if isinstance(raw.get("purpose"), str) else ""
    if not purpose:
        hard.append("missing purpose")

    controls = {}
    raw_controls = raw.get("controls", {})
    if not isinstance(raw_controls, dict):
        hard.append("controls must be an object keyed by id")
        raw_controls = {}
    for key, spec in raw_controls.items():
        try:
            cid = int(key)
        except (TypeError, ValueError):
            soft.append(f"dropped non-numeric control id {key!r}")
            continue
        if cid not in node_ids:
            soft.append(f"dropped unknown control id {cid}")
            continue
        spec = spec if isinstance(spec, dict) else {}
        label = spec.get("label") if isinstance(spec.get("label"), str) and spec.get("label").strip() \
            else (nodes_by_id[cid].get("name") or f"Control {cid}")
        kind = spec.get("kind") if spec.get("kind") in KINDS else "other"
        importance = spec.get("importance") if spec.get("importance") in IMPORTANCE else "medium"
        entry = {"label": label.strip()[:80], "kind": kind, "importance": importance}
        if spec.get("risk") in RISKS:
            entry["risk"] = spec["risk"]
        if spec.get("required") is True:
            entry["required"] = True
        if spec.get("is_default") is True:
            entry["is_default"] = True
        if isinstance(spec.get("on_double_click"), str) and spec["on_double_click"].strip():
            entry["on_double_click"] = spec["on_double_click"].strip()[:80]
        controls[str(cid)] = entry

    groups = []
    for g in raw.get("groups", []) if isinstance(raw.get("groups"), list) else []:
        if not isinstance(g, dict):
            continue
        ids = []
        for i in g.get("ids", []) if isinstance(g.get("ids"), list) else []:
            try:
                i = int(i)
            except (TypeError, ValueError):
                continue
            if i in node_ids and i not in ids:
                ids.append(i)
        if ids:
            groups.append({"name": str(g.get("name") or "Section")[:60], "ids": ids})

    regions = []
    for idx, r in enumerate(raw.get("vision_regions", []) if isinstance(raw.get("vision_regions"), list) else []):
        if not isinstance(r, dict):
            continue
        box = _box_to_screen(r.get("box"), snapshot, scale)
        if box is None:
            soft.append(f"dropped vision region {idx} with bad box")
            continue
        regions.append({
            "region_id": f"v{len(regions) + 1}",
            "label": str(r.get("label") or "Region")[:60],
            "kind": r.get("kind") if r.get("kind") in REGION_KINDS else "other",
            "box": box,
        })

    if not controls and not regions:
        hard.append("no valid controls or vision_regions")

    try:
        confidence = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    warnings = [str(w)[:160] for w in raw.get("warnings", []) if isinstance(w, (str, int, float))] \
        if isinstance(raw.get("warnings"), list) else []

    ratio = identified_ratio(snapshot)
    if confidence < ASSIST_BELOW:
        mode = "assist"
    elif ratio < VISION_BELOW:
        mode = "vision"
    else:
        mode = "structure"

    labels = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "fingerprint": snapshot.get("fingerprint"),
        "screen_type": screen_type.strip()[:60],
        "purpose": purpose.strip()[:240],
        "mode": mode,
        "groups": groups,
        "controls": controls,
        "vision_regions": regions,
        "help": str(raw.get("help") or "")[:400],
        "warnings": warnings,
        "confidence": round(confidence, 2),
    }
    return labels, hard, soft


def assist_fallback(snapshot, reason):
    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "fingerprint": snapshot.get("fingerprint"),
        "screen_type": "unknown",
        "purpose": "",
        "mode": "assist",
        "groups": [],
        "controls": {},
        "vision_regions": [],
        "help": "",
        "warnings": [],
        "confidence": 0.0,
        "error": reason[:300],
    }


# ---------- main entry ----------

def label_screen(snapshot, snapshot_dir=None, use_cache=True, budget=None):
    """Label one screen. Returns a contract 6.2 dict (plus model_ms / cached / notes)."""
    fp = snapshot.get("fingerprint") or ""
    if use_cache and fp:
        cp = cache_path(fp)
        if cp.is_file():
            labels = json.loads(cp.read_text(encoding="utf-8"))
            labels.update({"snapshot_id": snapshot.get("snapshot_id"), "cached": True, "model_ms": 0})
            return labels

    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    app = snapshot.get("app", {})
    intro = (f'App: {app.get("process", "?")} | Window title: {app.get("window_title", "?")}\n'
             f'Window size: {snapshot.get("window_rect", {}).get("w")}x{snapshot.get("window_rect", {}).get("h")}\n'
             f"Accessibility table ({snapshot.get('node_count', len(snapshot.get('nodes', [])))} rows"
             f"{', truncated' if snapshot.get('truncated') else ''}):\n")
    text = intro + compact_tree(snapshot)
    web = snapshot.get("web")
    if web:  # web pages: forms, data tables and messages say a lot about what the page is for
        extra = {"url": web.get("url"), "forms": [{k: f[k] for k in ("action", "method", "submit")} |
                                                  {"fields": [{k: x[k] for k in ("label", "name", "type", "required", "options")}
                                                              for x in f["fields"]]} for f in web.get("forms", [])],
                 "tables": [{k: t[k] for k in ("headers", "row_count", "link_column", "sample_rows")}
                            for t in web.get("tables", [])],
                 "pagination": {k: (v or {}).get("text") for k, v in (web.get("pagination") or {}).items()},
                 "alerts": web.get("alerts", [])}
        text += "\n\nWeb page details (JSON):\n" + json.dumps(extra, ensure_ascii=False)[:8000]
    content = [{"type": "text", "text": text}]

    scale = 1.0
    shot = resolve(snapshot.get("screenshot_path"), snapshot_dir)
    if shot:
        part, scale = nemotron.image_part(shot)
        content.append(part)

    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": content}]
    total_ms, notes = 0, []
    try:
        res = nemotron.chat(messages, purpose="label_screen", budget=budget)
        total_ms += res["ms"]
        try:
            raw = nemotron.extract_json(res["text"])
            labels, hard, soft = validate(raw, snapshot, scale)
        except ValueError as e:
            labels, hard, soft = None, [str(e)], []
        notes += soft

        if hard:  # one repair attempt
            messages += [
                {"role": "assistant", "content": res["text"][:6000]},
                {"role": "user", "content": "Your answer had these problems: " + "; ".join(hard)
                 + ". Return the corrected JSON object only, using only ids from the table."},
            ]
            res = nemotron.chat(messages, purpose="label_screen_repair", budget=budget)
            total_ms += res["ms"]
            try:
                raw = nemotron.extract_json(res["text"])
                labels, hard, soft = validate(raw, snapshot, scale)
            except ValueError as e:
                labels, hard, soft = None, [str(e)], []
            notes += soft
        if hard or labels is None:
            labels = assist_fallback(snapshot, "; ".join(hard) or "invalid answer")
    except RuntimeError as e:
        labels = assist_fallback(snapshot, str(e))

    labels["model_ms"] = total_ms
    labels["cached"] = False
    if notes:
        labels["notes"] = notes[:20]

    if fp and labels.get("mode") != "assist" and "error" not in labels:
        LABEL_CACHE.mkdir(parents=True, exist_ok=True)
        cache_path(fp).write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    return labels


def main(argv=None):
    ap = argparse.ArgumentParser(description="Label a Screen Snapshot with Nemotron.")
    ap.add_argument("snapshot", help="path to a snapshot JSON (contract 6.1)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--budget", type=int, default=None, help="reasoning budget override")
    ap.add_argument("--out", help="where to write the labels JSON")
    args = ap.parse_args(argv)

    snap_path = Path(args.snapshot)
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    t0 = time.time()
    labels = label_screen(snapshot, snapshot_dir=snap_path.parent, use_cache=not args.no_cache,
                          budget=args.budget)
    out = Path(args.out) if args.out else snap_path.with_suffix(".labels.json")
    out.write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"screen_type={labels['screen_type']}  mode={labels['mode']}  confidence={labels['confidence']}")
    print(f"purpose: {labels['purpose']}")
    print(f"controls={len(labels['controls'])}  groups={len(labels['groups'])}  "
          f"vision_regions={len(labels['vision_regions'])}  warnings={len(labels['warnings'])}")
    print(f"model_ms={labels.get('model_ms')}  cached={labels.get('cached')}  total={time.time() - t0:.2f}s")
    if labels.get("error"):
        print("ERROR:", labels["error"], file=sys.stderr)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
