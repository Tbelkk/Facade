"""Recipes: how to READ (and later WRITE) each page type, so the Operator runs without Nemotron.

Built from the page models the explorer already captured (everything here is measured from the DOM).
Written to <run folder>/recipes.json next to site_map.json.

One recipe per page type:
    list    table index + column mapping (+ split patterns, formats), row/detail link pattern, next page
    detail  label -> field for every label:value block
    form    fields by label (role/label locator + css backup), required, options, submit buttons

Generic on purpose (team rule 2): no knowledge of any particular site.
"""
import re
import time
from collections import Counter

from .capture_dom import NEXT_TEXT, PREV_TEXT
from .urlpattern import normalize, type_key, url_pattern

RECIPES_VERSION = 1

# Value formats we can recognise from samples. First full match on EVERY non-empty sample wins.
FORMATS = [
    ("date", "MM/DD/YYYY", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
    ("date", "YYYY-MM-DD", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("datetime", "MM/DD/YYYY HH:MM", re.compile(r"^\d{1,2}/\d{1,2}/\d{4},? \d{1,2}:\d{2}(\s?[AP]M)?$", re.I)),
    ("time", "HH:MM", re.compile(r"^\d{1,2}:\d{2}(\s?[AP]M)?$", re.I)),
    ("money", None, re.compile(r"^-?[$€£]\s?\d[\d,]*(\.\d+)?$")),
    ("number", None, re.compile(r"^-?\d[\d,]*(\.\d+)?$")),
    ("phone", None, re.compile(r"^\+?[\d\s().-]{7,}$")),
    ("email", None, re.compile(r"^[^@\s]+@[^@\s]+\.\w+$")),
]
# Cells that hold several values in one string, e.g. "Smith, John". Tried in order.
SPLITS = [", ", " / ", " | ", " - "]


def field_name(label):
    """'Last Name' -> last_name ; 'DOB (MM/DD/YYYY)' -> dob (hints in brackets are not part of the name)."""
    base = re.sub(r"\(.*?\)|\[.*?\]", "", label or "").strip() or (label or "")
    s = re.sub(r"[^A-Za-z0-9]+", "_", base.strip().lower()).strip("_")
    return s[:48] or "field"


def detect_format(values):
    vals = [v.strip() for v in values if v and v.strip()]
    if not vals:
        return None
    for typ, fmt, rx in FORMATS:
        if all(rx.match(v) for v in vals):
            return {"type": typ, **({"format": fmt} if fmt else {})}
    return None


def detect_split(header, values):
    """A separator that splits EVERY non-empty sample into the same number (2-3) of non-empty parts."""
    vals = [v.strip() for v in values if v and v.strip()]
    if len(vals) < 2:
        return None
    for sep in SPLITS:
        counts = {len(v.split(sep)) for v in vals}
        if len(counts) == 1 and next(iter(counts)) in (2, 3) and all(all(p.strip() for p in v.split(sep))
                                                                       for v in vals):
            n = next(iter(counts))
            base = field_name(header)
            # "Last, First" is the near-universal comma convention for person names.
            if sep == ", " and n == 2 and "name" in base:
                into = ["last_name", "first_name"]
            else:
                into = [f"{base}_{i + 1}" for i in range(n)]
            parts = [list(map(str.strip, v.split(sep))) for v in vals]
            fmts = [detect_format([p[i] for p in parts]) for i in range(n)]
            out = {"separator": sep, "into": into, "regex": "^" + re.escape(sep).join(["(.+?)"] * n) + "$",
                   "example": vals[0]}
            if any(fmts):
                out["part_formats"] = fmts
            return out
    return None


def _id_params(pattern):
    return re.findall(r"\{(\w+)\}", pattern or "")


def _pattern_regex(pattern):
    """'/patients/{id}?tab={tab}' -> regex with named groups, matched against path?query."""
    rx = re.escape(pattern)
    rx = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/?&#]+)", rx)
    return "^" + rx + "$"


# ------------------------------------------------------------------ per kind

def _list_recipe(model, key_to_id):
    d = model["dom"]
    grids = [t for t in d["tables"] if t["kind"] == "grid"]
    grid = max(grids, key=lambda t: (bool(t["link_columns"]), t["row_count"]), default=None)
    out = {}

    if grid:
        cols = []
        width = max([len(grid["headers"])] + [len(r) for r in grid["rows"]])
        headers = [(grid["headers"][k] if k < len(grid["headers"]) else "") for k in range(width)]
        for i, h in enumerate(headers):
            samples = [r[i] for r in grid["rows"] if i < len(r)]
            col = {"index": i, "header": h, "field": field_name(h) if h else f"col{i}",
                   "is_link": i in grid["link_columns"], "samples": samples[:3]}
            split = detect_split(h, samples)
            if split:
                col["split"] = split
            fmt = detect_format(samples)
            if fmt and not split:
                col.update(fmt)
            cols.append(col)
        out["table"] = {"index": grid["index"], "selector": f"table >> nth={grid['index']}",
                        "header_row": bool(grid["headers"]), "headers": grid["headers"],
                        "rows_seen": grid["row_count"], "columns": cols}

    # Row -> detail link: the most common (column, target pattern) among links inside the data rows.
    tally = Counter()
    sample_href = {}
    for l in d["links"]:
        href = l.get("href") or ""
        if not href.startswith("http") or NEXT_TEXT.search(l.get("text") or "") or PREV_TEXT.search(l.get("text") or ""):
            continue
        if grid and l.get("in_table") and l.get("table_index") == grid["index"]:
            k = ("table", l.get("column"), l.get("header"), url_pattern(normalize(href)))
        elif l.get("in_repeat"):
            k = ("repeat", None, None, url_pattern(normalize(href)))
        else:
            continue
        tally[k] += 1
        sample_href.setdefault(k, normalize(href))
    if tally:
        (where, col, header, pat), n = tally.most_common(1)[0]
        href = sample_href[(where, col, header, pat)]
        params = _id_params(pat)
        out["detail_link"] = {
            "where": "table_cell" if where == "table" else "repeated_link",
            "column_index": col, "column_header": header,
            "url_pattern": pat, "url_regex": _pattern_regex(pat),
            "id_param": params[0] if params else None,
            "goes_to": key_to_id.get(type_key(href)),
            "example": href, "links_seen": n,
        }

    pag = model["screen"]["heuristic"].get("pagination")
    if pag and pag.get("next"):
        out["next_page"] = {
            "how": "follow the link with this text until there is none",
            "link": pag["next"],                           # {"role": "link", "name": "Next >>"}
            "text_regex": NEXT_TEXT.pattern,               # fallback if the exact text changes
            "url_pattern": pag.get("next_url_pattern"),
            "page_param": _page_param(pag.get("next_url_pattern")),
            "page_size": pag.get("page_size"),
        }
    else:
        out["next_page"] = None
    return out


def _page_param(pattern):
    for p in _id_params((pattern or "").partition("?")[2]):
        if p.lower() in {"page", "p", "pg", "pagenum", "page_num", "offset", "start", "skip"}:
            return p
    return None


def _detail_recipe(model):
    blocks = [t for t in model["dom"]["tables"] if t["kind"] == "key_value"]
    labels, seen = [], set()
    for t in blocks:
        for label, value in t["pairs"]:
            if not label or label in seen:
                continue
            seen.add(label)
            item = {"label": label, "field": field_name(label), "table_index": t["index"],
                    "source": "dl" if t["index"] == -1 else "table", "sample": value}
            fmt = detect_format([value])
            if fmt:
                item.update(fmt)
            labels.append(item)
    params = _id_params(model["screen"]["url_pattern"])
    return {"id_param": params[0] if params else None, "labels": labels,
            "how": "for each label, read the cell next to it (row whose first cell == label)"}


def _form_recipe(model):
    forms = [f for f in model["dom"]["forms"] if f["fields"]]
    form = max(forms, key=lambda f: len(f["fields"]), default=None)
    if not form:
        return {"form": None}
    fields = []
    for f in form["fields"]:
        item = {"label": f["label"], "field": field_name(f["label"] or f["name"]), "type": f["type"],
                "required": f["required"], "locator": f.get("locator") or
                {"role": f["role"], "label": f["label"], "css": f["css"]}}
        for k in ("options", "maxlength", "pattern", "placeholder"):
            if f.get(k):
                item[k] = f[k]
        if f.get("value"):
            item["current_value"] = f["value"]
        fields.append(item)
    params = _id_params(model["screen"]["url_pattern"])
    return {"form": {"index": form["index"], "method": form["method"],
                     "action_pattern": url_pattern(form["action"]) if form.get("action") else None,
                     "fields": fields, "submit": form["buttons"]},
            "id_params": params,
            "messages_seen": model["dom"]["messages"]}


# ------------------------------------------------------------------ build / validate

def build(site_map, models, key_to_id):
    """site_map: format 7.2 dict. models: {page_id: page model}. key_to_id: {type_key: page_id}."""
    recipes = []
    for p in site_map["pages"]:
        model = models.get(p["id"])
        if not model or p["kind"] not in ("list", "detail", "form"):
            continue
        r = {"page_id": p["id"], "kind": p["kind"], "entity": p.get("entity"),
             "url_pattern": p["url_pattern"], "url_regex": _pattern_regex(p["url_pattern"]),
             "example_url": p.get("example_url")}
        if p["kind"] == "list":
            r.update(_list_recipe(model, key_to_id))
        elif p["kind"] == "detail":
            r.update(_detail_recipe(model))
        else:
            r.update(_form_recipe(model))
        recipes.append(r)
    return {"schema_version": RECIPES_VERSION, "site": site_map["site"], "generated_at":
            time.strftime("%Y-%m-%dT%H:%M:%S"), "site_map": "site_map.json", "recipes": recipes}


def validate(rec):
    """Problems with a recipes dict (empty list = OK)."""
    problems = []
    ids = {r["page_id"] for r in rec.get("recipes", [])}
    for r in rec.get("recipes", []):
        pid = r["page_id"]
        if r["kind"] == "list":
            t = r.get("table")
            if t and not t["columns"]:
                problems.append(f"{pid}: table has no columns")
            dl = r.get("detail_link")
            if dl and dl.get("goes_to") and dl["goes_to"] not in ids:
                problems.append(f"{pid}: detail_link goes to {dl['goes_to']}, which has no read recipe")
            if not t and not dl:
                problems.append(f"{pid}: list with neither a table nor row links")
        elif r["kind"] == "detail" and not r["labels"]:
            problems.append(f"{pid}: detail page with no labels")
        elif r["kind"] == "form" and not r.get("form"):
            problems.append(f"{pid}: form page with no form")
    return problems


def from_run_dir(run_dir):
    """Rebuild recipes.json from an existing run folder (site_map.json + pages/*.json). No browser needed."""
    import json
    from pathlib import Path

    run_dir = Path(run_dir)
    site_map = json.loads((run_dir / "site_map.json").read_text(encoding="utf-8"))
    models, key_to_id = {}, {}
    for p in site_map["pages"]:
        f = run_dir / p.get("capture", f"pages/{p['id']}.json")
        if f.exists():
            models[p["id"]] = json.loads(f.read_text(encoding="utf-8"))
        if p.get("example_url"):
            key_to_id[type_key(p["example_url"])] = p["id"]
    rec = build(site_map, models, key_to_id)
    out = run_dir / "recipes.json"
    out.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    return out, rec


def main(argv=None):
    import sys

    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        raise SystemExit("usage: python -m explore.recipes <run folder>")
    out, rec = from_run_dir(argv[0])
    print(f"wrote {out}: {len(rec['recipes'])} recipes")
    for problem in validate(rec):
        print(f"  warning: {problem}")


if __name__ == "__main__":
    main()
