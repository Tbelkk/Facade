"""Load the Operator's inputs from a run folder and profile the real values.

Inputs (written by the explorer + extractor, or hand-made mock JSON):
    data_model.json          entities, typed fields, relations, forms seen
    site_map.json            page types (list / detail / form)
    records/<Entity>.jsonl   {"legacy_id", "hash", "extracted_at", "data": {...}} per line
"""
import json
import re
import statistics
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


TYPE_ALIASES = {"int": "integer", "integer": "integer", "float": "number", "decimal": "number", "number": "number",
                "money": "number", "bool": "boolean", "boolean": "boolean", "textarea": "string", "text": "string",
                "str": "string", "string": "string", "date": "date", "datetime": "string", "time": "string",
                "enum": "enum", "ref": "ref"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def legacy_id_of(r):
    """Our records carry legacy_id; Daniel's agent writes _key (often the detail URL): item?id=42 -> '42'."""
    if r.get("legacy_id") is not None:
        return str(r["legacy_id"])
    key = str(r.get("_key", ""))
    if key.startswith(("http://", "https://")):
        u = urlsplit(key)
        for _, v in parse_qsl(u.query):
            if re.fullmatch(r"[\w-]+", v) and any(ch.isdigit() for ch in v):
                return v
        seg = [s for s in u.path.split("/") if s]
        return seg[-1] if seg else key
    return key or None


def _coerce(v, t):
    if v is None or v == "":
        return None
    if t == "integer":
        n = str(v).replace(",", "").strip()
        return int(n) if re.fullmatch(r"-?\d+", n) else v
    if t == "number":
        n = re.sub(r"[^\d.\-]", "", str(v))
        try:
            return float(n) if n else v
        except ValueError:
            return v
    if t == "boolean":
        s = str(v).strip().lower()
        return True if s in ("true", "yes", "1", "y", "on") else False if s in ("false", "no", "0", "n", "off") else v
    return v


def normalize(dm, records):
    """Make any explorer's output fit one shape: canonical types, typed values, a type that matches the values."""
    for e in dm["entities"]:
        rows = records.get(e["name"], [])
        for f in e["fields"]:
            raw_type = f.get("type", "string")
            t = TYPE_ALIASES.get(str(raw_type).lower(), "string")
            if t == "integer" and f.get("format") == "money":
                t = "number"
            vals = [r.get(f["name"]) for r in rows if r.get(f["name"]) not in (None, "")]
            if t in ("integer", "number", "boolean"):
                coerced = [_coerce(v, t) for v in vals]
                ok = all(isinstance(c, bool) if t == "boolean" else isinstance(c, (int, float)) and not isinstance(c, bool)
                         for c in coerced)
                if ok:
                    for r in rows:
                        if f["name"] in r:
                            r[f["name"]] = _coerce(r[f["name"]], t)
                else:
                    t = "string"
            if t == "date" and not all(ISO_DATE.match(str(v)) for v in vals):
                t = "string"  # e.g. "2 hours ago": not a real date, so no date range filters
                f.setdefault("note", "values are not ISO dates (for example relative times)")
            if t != raw_type:
                f["source_type"] = raw_type
            f["type"] = t
            f.setdefault("label", f["name"])
        e.setdefault("key", "legacy_id")
        e.setdefault("forms", [])
        e.setdefault("relations", [])
    return dm, records


def load(run_dir):
    run_dir = Path(run_dir)
    dm = json.loads((run_dir / "data_model.json").read_text(encoding="utf-8"))
    sm_path = run_dir / "site_map.json"
    site_map = json.loads(sm_path.read_text(encoding="utf-8")) if sm_path.exists() else {"pages": []}
    dm.setdefault("site", site_map.get("site"))
    records = {}
    for e in dm["entities"]:
        p = run_dir / "records" / f"{e['name']}.jsonl"
        rows = []
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                data = r["data"] if isinstance(r.get("data"), dict) else \
                    {k: v for k, v in r.items() if not k.startswith("_") and k not in ("legacy_id", "hash", "extracted_at")}
                rows.append({"legacy_id": legacy_id_of(r), **data})
        records[e["name"]] = rows
    normalize(dm, records)
    return dm, site_map, records


def profile_field(field, rows):
    name = field["name"]
    vals = [r.get(name) for r in rows]
    present = [v for v in vals if v is not None and v != ""]
    p = {"name": name, "label": field.get("label"), "type": field["type"], "non_null": len(present),
         "distinct": len({json.dumps(v) for v in present})}
    for k in ("description", "format", "to", "values", "display_of"):
        if field.get(k):
            p[k] = field[k]
    if field["type"] in ("integer", "number") and present:
        nums = [v for v in present if isinstance(v, (int, float))]
        if nums:
            p.update(min=min(nums), max=max(nums), median=statistics.median(nums))
    elif field["type"] == "date" and present:
        p.update(min=min(present), max=max(present))
    elif field["type"] in ("string", "enum", "ref", "boolean"):
        strs = [str(v) for v in present]
        if strs:
            p["avg_len"] = round(sum(map(len, strs)) / len(strs), 1)
        counts = {}
        for v in strs:
            counts[v] = counts.get(v, 0) + 1
        if 0 < p["distinct"] <= 12:
            p["value_counts"] = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
    p["samples"] = present[:3]
    return p


def profile(dm, records):
    """Compact, model-friendly description of every entity: fields + real value statistics + forms."""
    out = []
    for e in dm["entities"]:
        rows = records.get(e["name"], [])
        out.append({
            "entity": e["name"], "description": e.get("description", ""), "record_count": len(rows), "key": "legacy_id",
            "key_samples": [r["legacy_id"] for r in rows[:3]],
            "fields": [profile_field(f, rows) for f in e["fields"]],
            "relations": e.get("relations", []),
            "forms": [{"page_id": f["page_id"], "purpose": f["purpose"],
                       "fields": [{k: x[k] for k in ("name", "label", "required", "options") if k in x}
                                  for x in f["fields"]]} for f in e.get("forms", [])],
        })
    return out
