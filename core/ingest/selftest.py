"""Offline self-test: runs the whole ingest pipeline with a SIMULATED Nemotron.

No API key or Windows needed. Use it after any change to label.py / style.py:
    python -m ingest.selftest
It also (re)writes shared/fixtures/labels.json, style.json and screen/screen.json (the Screen
Model the frontend consumes), so teammates always have fixtures that match the current formats.
"""
import json
import shutil
import tempfile
from pathlib import Path

from . import label as label_mod
from . import nemotron, screen_model, style as style_mod
from .paths import FIXTURES_DIR
from .pipeline import run

FAKE_LABELS = {
    "screen_type": "patient_family",
    "purpose": "View and edit a patient's details and see everyone in their family.",
    "groups": [
        {"name": "Patient", "ids": [16, 18, 20, 34]},
        {"name": "Contact", "ids": [22, 24, 26]},
        {"name": "Actions", "ids": [28, 29]},
        {"name": "Family tools", "ids": [10, 11, 12, 13]},
        {"name": "Modules", "ids": [3, 4, 5, 6, 7, 8]},
    ],
    "controls": {
        "16": {"label": "Last name", "kind": "text_input", "importance": "high"},
        "18": {"label": "First name", "kind": "text_input", "importance": "high"},
        "20": {"label": "Date of birth", "kind": "date_input", "importance": "high"},
        "22": {"label": "Home phone", "kind": "text_input", "importance": "medium"},
        "24": {"label": "Mobile phone", "kind": "text_input", "importance": "high"},
        "26": {"label": "Street address", "kind": "text_input", "importance": "medium"},
        "27": {"label": "Debug mode", "kind": "checkbox", "importance": "hide"},
        "28": {"label": "Save", "kind": "button", "importance": "high", "risk": "write", "is_default": True},
        "34": {"label": "Primary provider", "kind": "dropdown", "importance": "medium"},
        "29": {"label": "Cancel", "kind": "button", "importance": "medium"},
        "10": {"label": "Find patient", "kind": "button", "importance": "high"},
        "11": {"label": "Add family member", "kind": "button", "importance": "medium", "risk": "write"},
        "12": {"label": "Delete family", "kind": "button", "importance": "low", "risk": "destructive"},
        "13": {"label": "Print", "kind": "button", "importance": "low"},
        "3": {"label": "Appointments", "kind": "tab", "importance": "medium"},
        "4": {"label": "Family", "kind": "tab", "importance": "medium"},
        "5": {"label": "Account", "kind": "tab", "importance": "medium"},
        "6": {"label": "Treatment plan", "kind": "tab", "importance": "medium"},
        "7": {"label": "Chart", "kind": "tab", "importance": "medium"},
        "8": {"label": "Manage", "kind": "tab", "importance": "low"},
        "999": {"label": "Invented control", "kind": "button", "importance": "high"},
    },
    "vision_regions": [{"label": "Family members", "kind": "table", "box": [550, 80, 430, 300]}],
    "help": "Search for a patient, then edit their details and save. The table lists their family.",
    "warnings": ["Home phone is empty"],
    "confidence": 0.84,
}
FAKE_TRAITS = {
    "traits": "Teal module bar on the left, navy title bar, classic gray 3D chrome, dense forms and a white data grid",
    "theme": "light", "density": "compact", "primary_hint": None, "accent_hint": None,
    "corner_style": "sharp", "chrome_style": "classic_3d", "font_hint": "sans",
    "font_family": "MS Sans Serif", "font_size_pt": 8,
}


def fake_chat_factory(palette_hex):
    state = {"label_calls": 0}

    def fake_chat(messages, purpose="call", **kw):
        if purpose.startswith("label_screen"):
            state["label_calls"] += 1
            if state["label_calls"] == 1:  # first answer is broken on purpose -> exercises the repair path
                return {"text": "<think>hmm</think>Sure! Here you go: {not json", "ms": 1200, "usage": None,
                        "model": "fake"}
            return {"text": "```json\n" + json.dumps(FAKE_LABELS) + "\n```", "ms": 1500, "usage": None,
                    "model": "fake"}
        if purpose == "style_traits":
            traits = dict(FAKE_TRAITS)
            traits["primary_hint"] = palette_hex["teal"]
            return {"text": json.dumps(traits), "ms": 900, "usage": None, "model": "fake"}
        raise AssertionError(f"unexpected purpose {purpose}")

    return fake_chat, state


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok -", msg)


def main():
    snap_path = FIXTURES_DIR / "snapshot.json"
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    node_ids = {n["id"] for n in snapshot["nodes"]}

    print("1) JSON extraction")
    check(nemotron.extract_json('<think>x</think>```json\n{"a": 1}\n```'.replace("<think>x</think>", "")) == {"a": 1},
          "handles ```json fences")
    check(nemotron.extract_json('Here: {"a": {"b": 2}} thanks') == {"a": {"b": 2}}, "handles prose around JSON")
    check(nemotron.strip_reasoning("<think>long thoughts</think> answer") == "answer", "strips <think> blocks")

    print("2) palette measured from pixels")
    palette = style_mod.extract_palette(FIXTURES_DIR / "screenshot.png")
    hexes = [p["hex"] for p in palette]
    teal = min(hexes, key=lambda h: sum(abs(a - b) for a, b in zip(style_mod.hex_to_rgb(h), (46/255, 125/255, 122/255))))
    check(len(palette) >= 3, f"found {len(palette)} colors: {hexes}")
    check(sum(abs(a - b) for a, b in zip(style_mod.hex_to_rgb(teal), (46/255, 125/255, 122/255))) < 0.15,
          f"teal identity color detected ({teal})")

    tmp = Path(tempfile.mkdtemp())
    real_chat = nemotron.chat
    old_label_cache, old_style_cache = label_mod.LABEL_CACHE, style_mod.STYLE_CACHE
    label_mod.LABEL_CACHE, style_mod.STYLE_CACHE = tmp / "labels", tmp / "style"
    fake_chat, state = fake_chat_factory({"teal": teal})
    nemotron.chat = fake_chat
    try:
        print("3) full pipeline with simulated Nemotron")
        screen = run(snapshot, snapshot_dir=snap_path.parent, use_cache=True)
        lb, st = screen["labels"], screen["style"]
        check(state["label_calls"] == 2, "bad first answer triggered exactly one repair")
        check(lb["screen_type"] == "patient_family", "screen_type parsed")
        check("999" not in lb["controls"], "invented id 999 was dropped")
        check(all(int(k) in node_ids for k in lb["controls"]), "all control ids exist in the snapshot")
        check(lb["mode"] in ("structure", "vision", "assist"), f"mode = {lb['mode']}")
        check(lb["vision_regions"] and lb["vision_regions"][0]["box"]["w"] == 430, "vision region box mapped")
        check(st["identity_color"] == teal, f"style kept the app's identity color {teal}")
        check(st["contrast_checked"], f"all token pairs pass WCAG AA {st['contrast_report']}")
        check(style_mod.hue_distance(st["tokens"]["color.primary"], teal) < 0.03,
              f"modern primary {st['tokens']['color.primary']} keeps the teal hue")

        print("4) Screen Model (frontend format, schema_version 1)")
        out_dir = tmp / "screen"
        model = screen_model.build(snapshot, lb, st, out_dir=out_dir,
                                   screenshot_path=FIXTURES_DIR / "screenshot.png")
        problems = screen_model.check(model)
        check(not problems, f"model passes schema check {problems[:5]}")
        flat = {}

        def _walk(lst):
            for n in lst:
                flat[n["id"]] = n
                _walk(n.get("children", []))
        _walk(model["tree"])
        check(model["screen"]["id"] == "patient_family" and model["screen"]["source"] == "uia", "screen id + source")
        check(model["screen"]["window"]["kind"] == "main" and model["screen"]["window"]["w"] == 1000, "window block")
        check(set(model["theme"]["palette"]) == {"background", "text", "accent", "error", "disabled"}, "palette keys")
        check(model["theme"]["palette"]["accent"] == teal and model["theme"]["palette"]["background"] == "#D4D0C8",
              "palette = the app's ORIGINAL measured colors")
        check(model["theme"]["font"] == {"family": "MS Sans Serif", "size": 8}, "original font from Nemotron")
        check(model["theme"]["density"] == "cramped", "density uses frontend vocabulary")
        check(model["theme"]["modern"]["color.primary"] == st["tokens"]["color.primary"], "modern tokens attached")
        ln = flat["textLName"]
        check(ln["role"] == "textbox" and ln["locator"] == {"automation_id": "textLName"}, "textbox + locator")
        check(ln["state"]["required"] and ln["tooltip"] == "Patient last name", "required + tooltip")
        check(ln["ai"]["label"] == "Last name", "Nemotron label kept separate under ai")
        lbl = next(n for n in flat.values() if n["role"] == "label" and n.get("text") == "LName")
        check(lbl.get("label_for") == "textLName", "label_for matched by position")
        check(flat["butSelectPat"]["hotkey"] == "F2", "hotkey parsed from '(F2)'")
        check(flat["butOK"].get("is_default") is True, "default button")
        cb = flat["comboPriProv"]
        check(cb["role"] == "combobox" and len(cb["options"]) == 3, "combobox options")
        check(flat["checkDebug"]["value"] is False, "checkbox value from toggle state")
        grid = flat["gridFamily"]
        check(grid["role"] == "custom" and (out_dir / grid["crop"]).is_file(), "custom-drawn grid cropped")
        check(grid["ai"]["label"] == "Family members" and "v1" not in flat, "vision region merged, not duplicated")
        status = next(n for n in flat.values() if n["role"] == "status" and n.get("text"))
        check(style_mod.luminance(status["style"]["color"]) < 0.02, f"status text color measured from pixels ({status['style']['color']})")
        check(all("name" in m for m in model["menus"]), "menus")
        tab_idx = [n["tab_index"] for n in flat.values() if "tab_index" in n]
        check(sorted(tab_idx) == list(range(1, len(tab_idx) + 1)), f"tab order 1..{len(tab_idx)}")

        print("5) cache")
        again = run(snapshot, snapshot_dir=snap_path.parent, use_cache=True)
        check(again["labels"]["cached"] and again["style"]["cached"], "second run served from cache (no model call)")
        check(state["label_calls"] == 2, "no extra Nemotron calls on cache hit")

        print("6) fallback")
        nemotron.chat = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network down"))
        fb = label_mod.label_screen(snapshot, snapshot_dir=snap_path.parent, use_cache=False)
        check(fb["mode"] == "assist" and "error" in fb, "API failure -> assist mode, never a crash")

        # refresh fixtures for teammates
        clean_labels = {k: v for k, v in lb.items() if k not in ("cached", "notes")}
        (FIXTURES_DIR / "labels.json").write_text(json.dumps(clean_labels, indent=2), encoding="utf-8")
        clean_style = {k: v for k, v in st.items() if k != "cached"}
        (FIXTURES_DIR / "style.json").write_text(json.dumps(clean_style, indent=2), encoding="utf-8")
        fx = FIXTURES_DIR / "screen"
        model = screen_model.build(snapshot, clean_labels, clean_style, out_dir=fx,
                                   screenshot_path=FIXTURES_DIR / "screenshot.png")
        (fx / "screen.json").write_text(json.dumps(model, indent=2), encoding="utf-8")
        print("\nfixtures refreshed: shared/fixtures/labels.json, style.json, screen/screen.json")
    finally:
        nemotron.chat = real_chat
        label_mod.LABEL_CACHE, style_mod.STYLE_CACHE = old_label_cache, old_style_cache
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
