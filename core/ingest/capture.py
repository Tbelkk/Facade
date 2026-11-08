"""WINDOWS ONLY: capture an app window -> Screen Snapshot (contract 6.1) + screenshot.

Usage (from core/, terminal opened "as administrator"):
    python -m ingest.capture          # 3-second countdown, then captures the window in front
    python -m ingest.capture 5        # custom countdown
Output: cache/snapshots/snap_<ms>.json and .png
"""
import ctypes
import hashlib
import json
import sys
import time

from .paths import CACHE_DIR

if sys.platform != "win32":
    raise SystemExit("capture.py needs Windows (UI Automation). On Mac, use the fixtures in shared/fixtures/.")

# Physical pixels so accessibility rects and screenshots line up. Must run before anything else.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
except Exception:
    pass

import mss  # noqa: E402
import mss.tools  # noqa: E402
import uiautomation as auto  # noqa: E402

MAX_NODES = 300
MAX_DEPTH = 12
SNAP_DIR = CACHE_DIR / "snapshots"

PATTERNS = {
    "set_value": auto.PatternId.ValuePattern,
    "invoke": auto.PatternId.InvokePattern,
    "select": auto.PatternId.SelectionItemPattern,
    "expand": auto.PatternId.ExpandCollapsePattern,
    "toggle": auto.PatternId.TogglePattern,
    "scroll_into_view": auto.PatternId.ScrollItemPattern,
}


def rect_of(c):
    r = c.BoundingRectangle
    return {"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top}


def actions_of(c):
    acts = []
    for name, pid in PATTERNS.items():
        try:
            if c.GetPattern(pid):
                acts.append(name)
        except Exception:
            pass
    return acts


def value_of(c):
    try:
        p = c.GetPattern(auto.PatternId.ValuePattern)
        if p:
            return p.Value
    except Exception:
        pass
    return None


def _get(c, attr, default=None):
    try:
        v = getattr(c, attr)
        return v if v not in ("", None) else default
    except Exception:
        return default


def _pattern(c, pid):
    try:
        return c.GetPattern(pid)
    except Exception:
        return None


def combobox_options(c, limit=50):
    opts = []
    try:
        for item, _depth in auto.WalkControl(c, maxDepth=3):
            if item.ControlTypeName == "ListItemControl" and item.Name:
                opts.append(item.Name[:80])
                if len(opts) >= limit:
                    break
    except Exception:
        pass
    return opts


def _cell_text(cell):
    v = value_of(cell)
    return v if v not in (None, "") else (cell.Name or "")


def table_info(c, max_rows=3, max_cols=12):
    """Columns + a few sample rows. Tries GridPattern/TablePattern, then WinForms-style row children."""
    info = {}
    grid = _pattern(c, auto.PatternId.GridPattern)
    table = _pattern(c, auto.PatternId.TablePattern)
    try:
        if table:
            heads = table.GetColumnHeaders() or []
            info["columns"] = [h.Name or f"col{i}" for i, h in enumerate(heads[:max_cols])]
    except Exception:
        pass
    try:
        if grid:
            rows, cols = grid.RowCount, grid.ColumnCount
            info["row_count"] = rows
            info["sample_rows"] = [[_cell_text(grid.GetItem(r, k)) for k in range(min(cols, max_cols))]
                                   for r in range(min(rows, max_rows))]
            info.setdefault("columns", [f"col{k}" for k in range(min(cols, max_cols))])
    except Exception:
        pass
    if "sample_rows" not in info:  # DataGridView: children "Top Row" (headers) + "Row 0", "Row 1"...
        try:
            kids = c.GetChildren()
            header = next((k for k in kids if (k.Name or "").lower().startswith("top row")), None)
            if header and "columns" not in info:
                info["columns"] = [h.Name for h in header.GetChildren()[:max_cols] if h.Name]
            data_rows = [k for k in kids if (k.Name or "").lower().startswith("row ")]
            info["row_count"] = len(data_rows)
            info["sample_rows"] = [[_cell_text(cell) for cell in r.GetChildren()[:max_cols]]
                                   for r in data_rows[:max_rows]]
        except Exception:
            pass
    sel = _pattern(c, auto.PatternId.SelectionPattern)
    try:
        if sel is not None:
            info["selection"] = "multiple" if sel.CanSelectMultiple else "single"
    except Exception:
        pass
    return info


def extras_of(c, role):
    """Extra fields used by the screen model (tooltip, hotkeys, state, options, tables)."""
    ex = {}
    help_text = _get(c, "HelpText")
    if help_text:
        ex["help_text"] = str(help_text)[:160]
    accel = _get(c, "AcceleratorKey") or _get(c, "AccessKey")
    if accel:
        ex["hotkey"] = str(accel)[:20]
    if _get(c, "IsKeyboardFocusable", False):
        ex["focusable"] = True
    if _get(c, "IsRequiredForForm", False):
        ex["required"] = True
    if _get(c, "IsPassword", False):
        ex["password"] = True
    vp = _pattern(c, auto.PatternId.ValuePattern)
    try:
        if vp is not None and vp.IsReadOnly:
            ex["readonly"] = True
    except Exception:
        pass
    tp = _pattern(c, auto.PatternId.TogglePattern)
    try:
        if tp is not None:
            ex["toggle_state"] = int(tp.ToggleState)  # 0 off, 1 on, 2 indeterminate
    except Exception:
        pass
    if role == "ComboBox":
        opts = combobox_options(c)
        if opts:
            ex["options"] = opts
    if role in ("DataGrid", "Table", "List"):
        info = table_info(c)
        if info:
            ex["table"] = info
    return ex


def window_kind(window):
    """('main' | 'dialog', owner window title or None)."""
    kind, owner_title = "main", None
    wp = _pattern(window, auto.PatternId.WindowPattern)
    try:
        if wp is not None and wp.IsModal:
            kind = "dialog"
    except Exception:
        pass
    try:
        owner = ctypes.windll.user32.GetWindow(window.NativeWindowHandle, 4)  # GW_OWNER
        if owner:
            kind = "dialog"
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(owner, buf, 256)
            owner_title = buf.value or None
    except Exception:
        pass
    return kind, owner_title


def menus_of(nodes):
    """Top-level menu bar items (we don't open menus: that would change the app's state)."""
    bars = [n["id"] for n in nodes if n["role"] == "MenuBar"]
    out = []
    for n in nodes:
        if n["role"] == "MenuItem" and n["parent"] in bars and n["name"] not in ("System",):
            out.append({"name": n["name"], "hotkey": n.get("hotkey"), "items": []})
    return out


def walk(root):
    nodes, next_id, truncated = [], [0], [False]

    def visit(c, parent_id, depth):
        if len(nodes) >= MAX_NODES:
            truncated[0] = True
            return
        if depth > MAX_DEPTH:
            return
        try:
            if c.IsOffscreen:
                return
            rect = rect_of(c)
        except Exception:
            return
        if rect["w"] <= 0 or rect["h"] <= 0:
            return
        my_id = next_id[0]
        next_id[0] += 1
        role = c.ControlTypeName.replace("Control", "")
        node = {
            "id": my_id,
            "parent": parent_id,
            "role": role,
            "name": (c.Name or "")[:120],
            "automation_id": c.AutomationId or "",
            "class_name": c.ClassName or "",
            "rect": rect,
            "value": value_of(c),
            "enabled": bool(c.IsEnabled),
            "actions": actions_of(c),
        }
        node.update(extras_of(c, role))
        nodes.append(node)
        try:
            children = c.GetChildren()
        except Exception:
            children = []
        for ch in children:
            visit(ch, my_id, depth + 1)

    visit(root, None, 0)
    return nodes, truncated[0]


def fingerprint(process_name, window, nodes):
    # Structure only (roles + automation ids + class names), not values: the same
    # screen showing different data gets the same fingerprint, so the cache works.
    skeleton = "|".join(f'{n["role"]}:{n["automation_id"]}:{n["class_name"]}' for n in nodes)
    return f"{process_name}|{window.ClassName}|{hashlib.sha1(skeleton.encode()).hexdigest()[:10]}"


def process_name(pid):
    try:
        import psutil
        return psutil.Process(pid).name()
    except Exception:
        return f"pid{pid}"


def capture(window):
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    snap_id = f"snap_{int(time.time() * 1000)}"
    t = time.time()
    nodes, truncated = walk(window)
    walk_ms = int((time.time() - t) * 1000)

    rect = rect_of(window)
    png_path = SNAP_DIR / f"{snap_id}.png"
    with mss.mss() as sct:
        shot = sct.grab({"left": rect["x"], "top": rect["y"], "width": rect["w"], "height": rect["h"]})
        mss.tools.to_png(shot.rgb, shot.size, output=str(png_path))

    hwnd = window.NativeWindowHandle
    try:
        dpi_scale = ctypes.windll.user32.GetDpiForWindow(hwnd) / 96
    except Exception:
        dpi_scale = 1.0

    pname = process_name(window.ProcessId)
    kind, owner_title = window_kind(window)
    snapshot = {
        "snapshot_id": snap_id,
        "source": "uia",
        "window_kind": kind,
        "window_parent": owner_title,
        "menus": menus_of(nodes),
        "app": {"process": pname, "window_title": window.Name, "hwnd": hwnd},
        "window_rect": rect,
        "dpi_scale": dpi_scale,
        "fingerprint": fingerprint(pname, window, nodes),
        "screenshot_path": str(png_path.resolve()),
        "nodes": nodes,
        "node_count": len(nodes),
        "truncated": truncated,
        "walk_ms": walk_ms,
    }
    (SNAP_DIR / f"{snap_id}.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return snapshot


def capture_foreground(delay=3):
    """Wait, then capture whatever window is in front. Returns the snapshot dict."""
    print(f"Click the window you want to capture... {delay}s")
    time.sleep(delay)
    with auto.UIAutomationInitializerInThread():
        win = auto.GetForegroundControl().GetTopLevelControl()
        return capture(win)


def summarize(snap):
    print(f"Captured: {snap['app']['window_title']!r} ({snap['app']['process']})")
    print(f"  nodes={snap['node_count']} truncated={snap['truncated']} walk={snap['walk_ms']}ms dpi={snap['dpi_scale']}")
    print(f"  fingerprint={snap['fingerprint']}")
    roles = {}
    for n in snap["nodes"]:
        roles[n["role"]] = roles.get(n["role"], 0) + 1
    print("  roles:", dict(sorted(roles.items(), key=lambda kv: -kv[1])))
    named = sum(1 for n in snap["nodes"] if n["name"] or n["automation_id"])
    print(f"  named/identified nodes: {named}/{snap['node_count']}  <- low ratio = needs vision mode")
    print(f"  saved {snap['screenshot_path']} (+ .json)")


if __name__ == "__main__":
    summarize(capture_foreground(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
