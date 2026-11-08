"""Load the Operator's inputs from a run folder and profile the real values.

Inputs (written by the explorer + extractor, or hand-made mock JSON):
    data_model.json          entities, typed fields, relations, forms seen
    site_map.json            page types (list / detail / form)
    records/<Entity>.jsonl   {"legacy_id", "hash", "extracted_at", "data": {...}} per line
"""
import json
import statistics
from pathlib import Path


def load(run_dir):
    run_dir = Path(run_dir)
    dm = json.loads((run_dir / "data_model.json").read_text(encoding="utf-8"))
    sm_path = run_dir / "site_map.json"
    site_map = json.loads(sm_path.read_text(encoding="utf-8")) if sm_path.exists() else {"pages": []}
    records = {}
    for e in dm["entities"]:
        p = run_dir / "records" / f"{e['name']}.jsonl"
        rows = []
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    rows.append({"legacy_id": str(r["legacy_id"]), **(r.get("data") or {})})
        records[e["name"]] = rows
    return dm, site_map, records


def profile_field(field, rows):
    name = field["name"]
    vals = [r.get(name) for r in rows]
    present = [v for v in vals if v is not None and v != ""]
    p = {"name": name, "label": field.get("label"), "type": field["type"], "non_null": len(present),
         "distinct": len({json.dumps(v) for v in present})}
    for k in ("format", "to", "values", "display_of"):
        if field.get(k):
            p[k] = field[k]
    if field["type"] in ("integer", "number") and present:
        nums = [v for v in present if isinstance(v, (int, float))]
        if nums:
            p.update(min=min(nums), max=max(nums), median=statistics.median(nums))
    elif field["type"] == "date" and present:
        p.update(min=min(present), max=max(present))
    elif field["type"] in ("string", "enum", "ref"):
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
            "entity": e["name"], "record_count": len(rows), "key": "legacy_id",
            "key_samples": [r["legacy_id"] for r in rows[:3]],
            "fields": [profile_field(f, rows) for f in e["fields"]],
            "relations": e.get("relations", []),
            "forms": [{"page_id": f["page_id"], "purpose": f["purpose"],
                       "fields": [{k: x[k] for k in ("name", "label", "required", "options") if k in x}
                                  for x in f["fields"]]} for f in e.get("forms", [])],
        })
    return out
