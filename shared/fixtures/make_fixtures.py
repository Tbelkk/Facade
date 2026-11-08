"""Generate a fake legacy screen (screenshot + matching Screen Snapshot) for offline work.

This is NOT real app data. It mimics a 2000s-era Windows business app so Persons 2 and 3
can build before real captures from the Windows laptop exist.

    python make_fixtures.py      # writes screenshot.png + snapshot.json next to this file
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
W, H = 1000, 640
GRAY, NAVY, TEAL, WHITE, DARK = (212, 208, 200), (0, 0, 128), (46, 125, 122), (255, 255, 255), (64, 64, 64)

nodes = []


def node(role, name, aid, x, y, w, h, parent=0, value=None, actions=(), enabled=True, **extra):
    nodes.append({"id": len(nodes), "parent": parent if nodes else None, "role": role, "name": name,
                  "automation_id": aid, "class_name": "WindowsForms10.Window.8.app", "rect": {"x": x, "y": y, "w": w, "h": h},
                  "value": value, "enabled": enabled, "actions": list(actions), **extra})
    return len(nodes) - 1


img = Image.new("RGB", (W, H), GRAY)
d = ImageDraw.Draw(img)


def bevel(x, y, w, h, sunken=False):
    hi, lo = (WHITE, DARK) if not sunken else (DARK, WHITE)
    d.line([(x, y + h), (x, y), (x + w, y)], fill=hi)
    d.line([(x, y + h), (x + w, y + h), (x + w, y)], fill=lo)


def text_field(label, aid, x, y, value):
    d.text((x, y - 14), label, fill=(0, 0, 0))
    d.rectangle([x, y, x + 180, y + 20], fill=WHITE)
    bevel(x, y, 180, 20, sunken=True)
    d.text((x + 4, y + 4), value, fill=(0, 0, 0))
    lid = node("Text", label, "", x, y - 14, 120, 12, parent=form)
    extra = {"focusable": True}
    if aid == "textLName":
        extra.update(help_text="Patient last name", required=True)
    if aid == "textBirthdate":
        extra.update(help_text="MM/DD/YYYY")
    fid = node("Edit", "", aid, x, y, 180, 20, parent=form, value=value, actions=["set_value", "focus"], **extra)
    return lid, fid


def button(label, aid, x, y, w=90):
    d.rectangle([x, y, x + w, y + 24], fill=GRAY)
    bevel(x, y, w, 24)
    d.text((x + 10, y + 6), label, fill=(0, 0, 0))
    return node("Button", label, aid, x, y, w, 24, parent=toolbar if y < 100 else form, actions=["invoke"])


root = node("Window", "Open Dental - Family", "FormOpenDental", 0, 0, W, H)
# title bar
d.rectangle([0, 0, W, 22], fill=NAVY)
d.text((8, 5), "Open Dental - Family   (FAKE FIXTURE)", fill=WHITE)
node("TitleBar", "Open Dental - Family", "", 0, 0, W, 22)
# left module bar (teal)
d.rectangle([0, 22, 90, H], fill=TEAL)
modbar = node("Pane", "", "myOutlookBar", 0, 22, 90, H - 22)
for i, m in enumerate(["Appts", "Family", "Account", "TreatPlan", "Chart", "Manage"]):
    y = 40 + i * 70
    d.rectangle([12, y, 78, y + 50], outline=WHITE)
    d.text((18, y + 18), m, fill=WHITE)
    node("ListItem", m, "", 12, y, 66, 50, parent=modbar, actions=["select"])
# toolbar
toolbar = node("ToolBar", "", "ToolBarMain", 90, 22, W - 90, 40)
d.rectangle([90, 22, W, 62], fill=GRAY)
bevel(90, 22, W - 91, 40)
for i, (lbl, aid) in enumerate([("Select Pat (F2)", "butSelectPat"), ("Add Fam", "butAddFam"),
                                ("Delete Fam", "butDeleteFam"), ("Print", "butPrint")]):
    button(lbl, aid, 100 + i * 100, 30, w=95)
# patient info form
form = node("Group", "Patient Information", "groupPatInfo", 110, 80, 420, 300)
d.rectangle([110, 80, 530, 380], outline=DARK)
d.text((118, 72), " Patient Information ", fill=(0, 0, 0))
fields = [("LName", "textLName", "Smith"), ("FName", "textFName", "Jordan"), ("Birthdate", "textBirthdate", "03/14/1987"),
          ("HmPhone", "textHmPhone", ""), ("WirelessPhone", "textWirelessPhone", "(214) 555-0142"),
          ("Address", "textAddress", "800 W Campbell Rd")]
for i, (lbl, aid, val) in enumerate(fields):
    col, row = i % 2, i // 2
    text_field(lbl, aid, 130 + col * 200, 115 + row * 60, val)
node("CheckBox", "chkDebugMode", "checkDebug", 130, 300, 140, 16, parent=form, actions=["toggle"], toggle_state=0,
     focusable=True)
d.rectangle([130, 300, 142, 312], fill=WHITE)
bevel(130, 300, 12, 12, sunken=True)
d.text((148, 300), "chkDebugMode", fill=(0, 0, 0))
button("OK", "butOK", 330, 340)
button("Cancel", "butCancel", 430, 340)
# family grid (custom-drawn: only a bare Pane in the accessibility tree, like many real apps)
d.rectangle([550, 80, 980, 380], fill=WHITE, outline=DARK)
d.rectangle([550, 80, 980, 100], fill=(236, 233, 216))
for j, hdr in enumerate(["Name", "Position", "Gender", "Status", "Age"]):
    d.text((556 + j * 84, 85), hdr, fill=(0, 0, 0))
rows = [["Smith, Jordan", "Guarantor", "M", "Patient", "39"], ["Smith, Avery", "Spouse", "F", "Patient", "37"],
        ["Smith, Kai", "Child", "M", "Patient", "9"]]
for r, row in enumerate(rows):
    y = 104 + r * 22
    if r == 0:
        d.rectangle([551, y - 2, 979, y + 16], fill=(49, 106, 197))
    for j, cell in enumerate(row):
        d.text((556 + j * 84, y), cell, fill=WHITE if r == 0 else (0, 0, 0))
node("Pane", "", "gridFamily", 550, 80, 430, 300)
# status bar
d.rectangle([90, H - 24, W, H], fill=GRAY)
bevel(90, H - 24, W - 91, 23, sunken=True)
d.text((98, H - 18), "Ready  |  Server: localhost  |  DB: demo", fill=(0, 0, 0))
sb = node("StatusBar", "", "statusBar", 90, H - 24, W - 90, 24)
node("Text", "Ready  |  Server: localhost  |  DB: demo", "", 96, H - 20, 300, 14, parent=sb)
# provider dropdown (appended so earlier ids stay stable)
d.text((330, 280), "Prov", fill=(0, 0, 0))
node("Text", "Prov", "", 330, 280, 60, 12, parent=form)
d.rectangle([330, 294, 510, 314], fill=WHITE)
bevel(330, 294, 180, 20, sunken=True)
d.text((334, 298), "DOC1 - Lee", fill=(0, 0, 0))
d.rectangle([494, 296, 508, 312], fill=GRAY)
node("ComboBox", "", "comboPriProv", 330, 294, 180, 20, parent=form, value="DOC1 - Lee",
     actions=["expand", "set_value"], options=["DOC1 - Lee", "DOC2 - Patel", "HYG1 - Nguyen"], focusable=True)

img.save(HERE / "screenshot.png")
snapshot = {
    "snapshot_id": "snap_fixture_001",
    "app": {"process": "OpenDental.exe", "window_title": "Open Dental - Family", "hwnd": 0},
    "window_rect": {"x": 0, "y": 0, "w": W, "h": H},
    "dpi_scale": 1.0,
    "fingerprint": "OpenDental.exe|WindowsForms10|fixture001",
    "source": "uia",
    "window_kind": "main",
    "window_parent": None,
    "menus": [{"name": "File", "hotkey": "Alt+F", "items": []}, {"name": "Setup", "hotkey": "Alt+S", "items": []}],
    "screenshot_path": "screenshot.png",
    "nodes": nodes,
    "node_count": len(nodes),
    "truncated": False,
    "walk_ms": 0,
    "_note": "FAKE FIXTURE for offline development. Not real application data.",
}
(HERE / "snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
print(f"wrote screenshot.png and snapshot.json ({len(nodes)} nodes)")
