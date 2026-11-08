"""Build the Screen Model: the format the overlay (frontend) consumes.

Shape agreed with the frontend (schema_version 1):
    screen  {id, source, window{title, kind, parent, w, h}, screenshot}
    theme   {palette{background, text, accent, error, disabled}, font{family, size}, density, assets[]}
    tree    nested nodes with ARIA roles, window-relative rects [x, y, w, h], locators
    menus   [{name, hotkey, items[]}]

Facade additions (extra keys only, nothing in the agreed shape is changed):
    screen.window.{x, y, dpi_scale}   where the window is on screen, so the overlay can sit on top
    screen.ai                         Nemotron's screen understanding (purpose, help, warnings, sections...)
    node.ai                           Nemotron's per-control labels (plain-English label, importance, risk)
    theme.modern                      modernized design tokens built from the app's own colors
    node.raw                          original accessibility info (class, uia role) for debugging

Everything outside an `ai` key is MEASURED from the app. Everything inside `ai` is Nemotron's judgment.
"""
import json
import re
import shutil
from pathlib import Path

SCHEMA_VERSION = 1

UIA_TO_ARIA = {
    "Button": "button", "SplitButton": "button", "CheckBox": "checkbox", "RadioButton": "radio",
    "Edit": "textbox", "Document": "textbox", "ComboBox": "combobox", "List": "listbox",
    "ListItem": "option", "DataGrid": "table", "Table": "table", "DataItem": "row",
    "Header": "rowgroup", "HeaderItem": "columnheader", "Tree": "tree", "TreeItem": "treeitem",
    "Tab": "tablist", "TabItem": "tab", "Menu": "menu", "MenuBar": "menubar", "MenuItem": "menuitem",
    "ToolBar": "toolbar", "StatusBar": "status", "Text": "label", "Group": "group", "Pane": "group",
    "Window": "group", "Image": "img", "Hyperlink": "link", "ProgressBar": "progressbar",
    "Slider": "slider", "Spinner": "spinbutton", "ScrollBar": "scrollbar", "Separator": "separator",
    "Calendar": "grid", "Custom": "custom", "ToolTip": "tooltip", "AppBar": "toolbar",
}
SKIP_UIA = {"TitleBar", "Thumb"}                 # window chrome the overlay never redraws
TEXT_ROLES = {"label", "button", "status", "link", "tab", "menuitem", "option", "listitem", "columnheader"}
INTERACTIVE = {"button", "checkbox", "radio", "textbox", "combobox", "listbox", "option", "listitem", "table",
               "tab", "menuitem", "link", "slider", "spinbutton", "treeitem"}
GENERIC = {"custom", "group", "option", "listitem"}  # roles Nemotron may refine
AI_KIND_TO_ARIA = {"text_input": "textbox", "number_input": "spinbutton", "date_input": "textbox",
                   "dropdown": "combobox", "checkbox": "checkbox", "radio": "radio", "button": "button",
                   "table": "table", "list": "listbox", "tab": "tab", "label": "label", "menu": "menuitem"}
DENSITY = {"compact": "cramped", "comfortable": "normal", "spacious": "spacious"}
HOTKEY_IN_TEXT = re.compile(r"\((F\d{1,2}|(?:Ctrl|Alt|Shift)\+[\w\d]+)\)", re.I)


# ---------- small helpers ----------

def _slug(text, fallback):
    s = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")
    return (s[:40] or fallback)


def _rel_rect(node, win):
    r = node.get("rect", {})
    return [r.get("x", 0) - win.get("x", 0), r.get("y", 0) - win.get("y", 0), r.get("w", 0), r.get("h", 0)]


def _iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix, iy = max(0, min(ax + aw, bx + bw) - max(ax, bx)), max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def infer_type(values):
    vals = [str(v).strip() for v in values if v not in (None, "")]
    if not vals:
        return "string"
    if all(v.lower() in ("true", "false", "yes", "no", "y", "n", "0", "1", "checked", "unchecked") for v in vals):
        return "bool"
    if all(re.fullmatch(r"-?\d+", v) for v in vals):
        return "int"
    if all(re.fullmatch(r"-?\$?[\d,]*\.\d+", v) for v in vals):
        return "decimal"
    if all(re.fullmatch(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", v) for v in vals):
        return "date"
    return "string"


def _coerce(v, typ):
    try:
        if typ == "int":
            return int(str(v).strip())
        if typ == "decimal":
            return float(str(v).replace("$", "").replace(",", "").strip())
        if typ == "bool":
            return str(v).strip().lower() in ("true", "yes", "y", "1", "checked")
    except ValueError:
        pass
    return v


# ---------- theme (original, measured) ----------

def original_theme(style, label_colors):
    from .style import hls, is_chromatic, luminance

    if not style:
        return {"palette": {}, "font": {"family": None, "size": None}, "density": "normal", "assets": []}
    pal = style.get("palette_share") or [{"hex": h, "share": 0} for h in style.get("source_palette", [])]
    hexes = [p["hex"] for p in pal]
    neutrals = [h for h in hexes if not is_chromatic(h)]
    background = (neutrals or hexes or [None])[0]

    dark = sorted(label_colors or [], key=luminance)
    text = dark[0] if dark else (min(hexes, key=luminance) if hexes else None)

    error = next((h for h in hexes if is_chromatic(h) and (hls(h)[0] < 0.04 or hls(h)[0] > 0.96)
                  and hls(h)[2] > 0.45), None)
    disabled = next((h for h in hexes if not is_chromatic(h) and 0.12 < luminance(h) < 0.35 and h != text), None)
    font = style.get("original_font") or {}
    return {
        "palette": {"background": background, "text": text, "accent": style.get("identity_color"),
                    "error": error, "disabled": disabled},
        "font": {"family": font.get("family"), "size": font.get("size")},
        "density": DENSITY.get(style.get("density"), "normal"),
        "assets": [],
        "modern": style.get("tokens", {}),
    }


def _text_color(img, rect_abs, background_hex):
    """Most common non-background color inside a text element (measured from pixels)."""
    if img is None:
        return None
    x, y, w, h = rect_abs
    if w <= 1 or h <= 1:
        return None
    crop = img.crop((max(0, x), max(0, y), min(img.width, x + w), min(img.height, y + h)))
    colors = crop.getcolors(maxcolors=crop.width * crop.height) or []
    bg = tuple(int(background_hex[i:i + 2], 16) for i in (1, 3, 5)) if background_hex else None
    ink = [(count, rgb) for count, rgb in colors
           if not (bg and sum(abs(a - b) for a, b in zip(rgb, bg)) < 60) and sum(rgb) <= 690]
    if not ink:
        return None
    # Text edges are anti-aliased into many in-between shades. Among the common "ink" colors,
    # take the one furthest from the background: that's the color the app actually draws text in.
    top = max(c for c, _ in ink)
    common = [rgb for c, rgb in ink if c >= 0.2 * top]
    ref = bg or (255, 255, 255)
    rgb = max(common, key=lambda c: sum(abs(a - b) for a, b in zip(c, ref)))
    return "#%02X%02X%02X" % rgb


# ---------- main builder ----------

def build(snapshot, labels=None, style=None, out_dir=None, screenshot_path=None):
    """snapshot (6.1) + labels (6.2) + style (6.3) -> Screen Model dict.

    If out_dir is given, the screenshot, crops of custom regions and image assets are written to
    out_dir/shots and out_dir/assets, and paths in the model are relative to out_dir.
    """
    labels = labels or {}
    controls = labels.get("controls", {})
    win = snapshot.get("window_rect", {"x": 0, "y": 0, "w": 0, "h": 0})
    nodes = [n for n in snapshot.get("nodes", [])]
    by_id = {n["id"]: n for n in nodes}
    root_id = nodes[0]["id"] if nodes else None
    screen_id = labels.get("screen_type") if labels.get("screen_type") not in (None, "unknown") \
        else _slug(snapshot.get("fingerprint", ""), "screen")

    img = None
    if screenshot_path and Path(screenshot_path).is_file():
        from PIL import Image
        img = Image.open(screenshot_path).convert("RGB")

    out = Path(out_dir) if out_dir else None
    shots_rel = None
    if out is not None:
        (out / "shots").mkdir(parents=True, exist_ok=True)
        (out / "assets").mkdir(parents=True, exist_ok=True)
        if screenshot_path and Path(screenshot_path).is_file():
            shots_rel = f"shots/{screen_id}.png"
            shutil.copyfile(screenshot_path, out / shots_rel)

    # stable string ids: automation_id when unique, else role_name slug
    aid_counts = {}
    for n in nodes:
        if n.get("automation_id"):
            aid_counts[n["automation_id"]] = aid_counts.get(n["automation_id"], 0) + 1
    sid, used = {}, set()
    for n in nodes:
        base = n["automation_id"] if n.get("automation_id") and aid_counts[n["automation_id"]] == 1 \
            else f'{UIA_TO_ARIA.get(n["role"], "node")}_{_slug(n.get("name"), str(n["id"]))}'
        cand, k = base, 2
        while cand in used:
            cand, k = f"{base}_{k}", k + 1
        used.add(cand)
        sid[n["id"]] = cand

    # ARIA role per node (UIA first, Nemotron refines generic ones)
    def aria_role(n):
        if n["role"] in SKIP_UIA:
            return None
        role = UIA_TO_ARIA.get(n["role"], "custom")
        parent = by_id.get(n.get("parent"))
        if role == "option" and (not parent or parent["role"] not in ("List", "ComboBox")):
            role = "listitem"
        if role == "label" and parent and parent["role"] == "StatusBar":
            role = "status"
        has_kids = any(m.get("parent") == n["id"] for m in nodes)
        r = n.get("rect", {})
        if role == "group" and not has_kids and r.get("w", 0) * r.get("h", 0) > 5000 and not n.get("name"):
            role = "custom"  # empty drawn area: custom-painted grid/chart/calendar
        ai = controls.get(str(n["id"]), {})
        if role in GENERIC and ai.get("kind") in AI_KIND_TO_ARIA and ai["kind"] != "label":
            role = AI_KIND_TO_ARIA[ai["kind"]]
        return role

    roles = {n["id"]: aria_role(n) for n in nodes}

    # label_for: the library can't read UIA LabeledBy, so match by position (label left of / above field)
    fields = [n for n in nodes if roles[n["id"]] in ("textbox", "combobox", "spinbutton", "listbox")]
    label_for = {}
    for n in nodes:
        if roles[n["id"]] != "label" or not n.get("name"):
            continue
        lr = n["rect"]
        best, best_d = None, 10**9
        for f in fields:
            fr = f["rect"]
            right = 0 <= fr["x"] - (lr["x"] + lr["w"]) <= 120 and abs(fr["y"] - lr["y"]) <= max(12, lr["h"])
            below = 0 <= fr["y"] - (lr["y"] + lr["h"]) <= 30 and abs(fr["x"] - lr["x"]) <= 40
            if right or below:
                d = abs(fr["x"] - lr["x"]) + abs(fr["y"] - lr["y"])
                if d < best_d:
                    best, best_d = f, d
        if best is not None:
            label_for[n["id"]] = best["id"]

    # tab order: focusable interactive controls in reading order (top-to-bottom, left-to-right)
    focusables = [n for n in nodes if roles[n["id"]] in INTERACTIVE and n.get("enabled", True)
                  and (n.get("focusable") or roles[n["id"]] in ("textbox", "combobox", "button", "checkbox", "radio"))]
    focusables.sort(key=lambda n: (round(n["rect"]["y"] / 10), n["rect"]["x"]))
    tab_index = {n["id"]: i + 1 for i, n in enumerate(focusables)}

    theme = original_theme(style, [])
    label_colors = []

    def make(n):
        role = roles[n["id"]]
        if role is None:
            return None
        rect = _rel_rect(n, win)
        node = {"id": sid[n["id"]], "role": role}
        name = n.get("name") or ""
        if role in TEXT_ROLES:
            if name:
                node["text"] = name
        elif name:
            node["name"] = name
        node["rect"] = rect

        val = n.get("value")
        if role == "checkbox" or role == "radio":
            if n.get("toggle_state") is not None:
                node["value"] = n["toggle_state"] == 1
        elif role in ("textbox", "combobox", "spinbutton") or val not in (None, ""):
            node["value"] = "" if val is None else val

        ai = controls.get(str(n["id"]), {})
        if role in INTERACTIVE:
            state = {"enabled": bool(n.get("enabled", True))}
            if role in ("textbox", "combobox", "spinbutton"):
                state["readonly"] = bool(n.get("readonly", False))
            if n.get("required") or ai.get("required"):
                state["required"] = True
            if n.get("password"):
                state["secret"] = True
            node["state"] = state
        if n.get("help_text"):
            node["tooltip"] = n["help_text"]
        if n["id"] in tab_index:
            node["tab_index"] = tab_index[n["id"]]
        hk = n.get("hotkey")
        m = HOTKEY_IN_TEXT.search(name)
        if hk or m:
            node["hotkey"] = hk or m.group(1)
        if ai.get("is_default"):
            node["is_default"] = True
        if n["id"] in label_for:
            node["label_for"] = sid[label_for[n["id"]]]
        if n.get("options"):
            node["options"] = n["options"]

        tbl = n.get("table")
        if role in ("table", "listbox") and tbl:
            rows = tbl.get("sample_rows", [])
            cols = tbl.get("columns") or [f"col{k}" for k in range(len(rows[0]) if rows else 0)]
            types = [infer_type([r[k] for r in rows if k < len(r)]) for k in range(len(cols))]
            node["columns"] = [{"key": c, "type": t} for c, t in zip(cols, types)]
            node["sample_rows"] = [[_coerce(v, types[k]) if k < len(types) else v for k, v in enumerate(r)]
                                   for r in rows]
            if tbl.get("row_count") is not None:
                node["row_count"] = tbl["row_count"]
            if tbl.get("selection"):
                node["selection"] = tbl["selection"]
        if ai.get("on_double_click"):
            node["on_double_click"] = ai["on_double_click"]

        if role in ("label", "status") and img is not None and name:
            color = _text_color(img, rect, theme["palette"].get("background"))
            if color:
                node["style"] = {"color": color}
                label_colors.append(color)

        if role in ("custom", "img") and img is not None and out is not None:
            kind = "assets" if role == "img" else "shots"
            rel = f"{kind}/{screen_id}_{sid[n['id']]}.png"
            x, y, w, h = rect
            img.crop((max(0, x), max(0, y), min(img.width, x + w), min(img.height, y + h))).save(out / rel)
            if role == "img":
                theme["assets"].append({"id": sid[n["id"]], "path": rel, "rect": rect})
            else:
                node["crop"] = rel

        loc = {"automation_id": n["automation_id"]} if n.get("automation_id") \
            else {"name": name, "control_type": n["role"]}
        if role not in ("label", "status", "group", "custom", "img", "separator"):
            node["locator"] = loc
        elif n.get("automation_id"):
            node["locator"] = loc
        node["raw"] = {"class": n.get("class_name", ""), "uia_role": n["role"]}
        if ai:
            node["ai"] = {k: ai[k] for k in ("label", "kind", "importance", "risk") if k in ai}

        kids = [make(m) for m in nodes if m.get("parent") == n["id"]]
        kids = [k for k in kids if k]
        if kids:
            node["children"] = kids
        return node

    top = [n for n in nodes if n.get("parent") == root_id] if root_id is not None else nodes
    tree = [t for t in (make(n) for n in top) if t]

    # Nemotron vision regions that don't match an existing custom node become custom nodes
    flat = []

    def _flatten(lst):
        for t in lst:
            flat.append(t)
            _flatten(t.get("children", []))

    _flatten(tree)
    for reg in labels.get("vision_regions", []):
        b = reg["box"]
        rr = [b["x"] - win.get("x", 0), b["y"] - win.get("y", 0), b["w"], b["h"]]
        match = next((t for t in flat if t["role"] == "custom" and _iou(t["rect"], rr) > 0.5), None)
        if match is not None:
            match.setdefault("ai", {}).update({"label": reg["label"], "kind": reg["kind"], "vision_region": reg["region_id"]})
            continue
        node = {"id": reg["region_id"], "role": "custom", "rect": rr, "raw": {"class": "", "uia_role": None},
                "ai": {"label": reg["label"], "kind": reg["kind"], "vision_region": reg["region_id"]}}
        if img is not None and out is not None:
            rel = f"shots/{screen_id}_{reg['region_id']}.png"
            x, y, w, h = rr
            img.crop((max(0, x), max(0, y), min(img.width, x + w), min(img.height, y + h))).save(out / rel)
            node["crop"] = rel
        tree.append(node)

    # measured text color now that we've seen the labels
    theme_final = original_theme(style, label_colors)
    theme_final["assets"] = theme["assets"]

    model = {
        "schema_version": SCHEMA_VERSION,
        "screen": {
            "id": screen_id,
            "source": snapshot.get("source", "uia"),
            "window": {
                "title": snapshot.get("app", {}).get("window_title"),
                "kind": snapshot.get("window_kind", "main"),
                "parent": snapshot.get("window_parent"),
                "w": win.get("w"), "h": win.get("h"),
                "x": win.get("x"), "y": win.get("y"), "dpi_scale": snapshot.get("dpi_scale", 1.0),
            },
            "screenshot": shots_rel or snapshot.get("screenshot_path"),
            "app": snapshot.get("app", {}).get("process"),
            "fingerprint": snapshot.get("fingerprint"),
            "ai": {
                "mode": labels.get("mode", "assist"),
                "purpose": labels.get("purpose", ""),
                "help": labels.get("help", ""),
                "warnings": labels.get("warnings", []),
                "confidence": labels.get("confidence", 0.0),
                "sections": [{"name": g["name"], "ids": [sid[i] for i in g["ids"] if i in sid]}
                             for g in labels.get("groups", [])],
                "model_ms": labels.get("model_ms", 0),
                "cached": labels.get("cached", False),
            },
        },
        "theme": theme_final,
        "tree": tree,
        "menus": snapshot.get("menus", []),
    }
    if labels.get("error"):
        model["screen"]["ai"]["error"] = labels["error"]
    return model


# ---------- validation (used by selftest; frontend can rely on these guarantees) ----------

ARIA_ROLES = set(UIA_TO_ARIA.values()) | {"listitem", "custom", "status", "textbox", "spinbutton"}


def check(model):
    """Return a list of problems (empty list = valid)."""
    problems = []
    if model.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version")
    for key in ("screen", "theme", "tree", "menus"):
        if key not in model:
            problems.append(f"missing {key}")
    win = model.get("screen", {}).get("window", {})
    for k in ("title", "kind", "w", "h"):
        if k not in win:
            problems.append(f"window.{k}")
    pal = model.get("theme", {}).get("palette", {})
    for k in ("background", "text", "accent", "error", "disabled"):
        if k not in pal:
            problems.append(f"palette.{k}")
    ids = set()

    def walk(lst):
        for n in lst:
            if n["id"] in ids:
                problems.append(f"duplicate id {n['id']}")
            ids.add(n["id"])
            if n.get("role") not in ARIA_ROLES:
                problems.append(f"bad role {n.get('role')} on {n['id']}")
            r = n.get("rect")
            if not (isinstance(r, list) and len(r) == 4):
                problems.append(f"bad rect on {n['id']}")
            walk(n.get("children", []))

    walk(model.get("tree", []))
    for s in model.get("screen", {}).get("ai", {}).get("sections", []):
        for i in s["ids"]:
            if i not in ids:
                problems.append(f"section id {i} not in tree")
    return problems


if __name__ == "__main__":
    import sys
    m = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    probs = check(m)
    print("valid" if not probs else "\n".join(probs))
