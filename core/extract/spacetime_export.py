"""Write extraction results in the SpacetimeDB shape (plan 7.5) without needing the database.

<run>/extract/
    spacetime/<table>.json   rows exactly as the tables hold them: site, entity_schema, record, job, event
                             (*_json columns are JSON strings, like the reducers take them)
    schema.json              JSON Schema (draft 2020-12) per entity: what the API returns for a record
    data.json                {entity: [{legacy_id, ...fields}]}: what GET /<entity> would answer
    records.jsonl            one record per line (with hash + change), used to detect changes next run
    duplicates.json          possible duplicates (flagged, never merged)

When the SpacetimeDB module is live, each row maps 1:1 to a reducer call:
    record -> upsert_record, entity_schema -> upsert_schema, site -> save_site, job -> start_job/update_job,
    event -> log_event.
"""
import json
import re
import time

from explore.recipes import field_name

_PLACEHOLDER = re.compile(r"^\s*(-+.*-+|select.*|choose.*|\(none\)|none)?\s*$", re.I)


def _form_info(recipes, entity):
    """field -> {required, options} from every form recipe of this entity."""
    info = {}
    for r in recipes["recipes"]:
        if r["kind"] != "form" or r.get("entity") != entity or not r.get("form"):
            continue
        for f in r["form"]["fields"]:
            i = info.setdefault(f["field"], {"required": False, "options": None, "page": r["page_id"]})
            i["required"] = i["required"] or bool(f.get("required"))
            opts = [o for o in (f.get("options") or []) if not _PLACEHOLDER.match(o)]
            if opts and not i["options"]:
                i["options"] = opts
    return info


def _labels(recipes, entity):
    out = {}
    for r in recipes["recipes"]:
        if r.get("entity") != entity:
            continue
        for l in r.get("labels", []):
            out.setdefault(l["field"], l["label"])
        for c in (r.get("table") or {}).get("columns", []):
            out.setdefault(c["field"], c["header"])
    return out


def entity_fields(ex, entity, types):
    """The typed field list for one entity (format 7.3 style)."""
    form = _form_info(ex.recipes, entity)
    labels = _labels(ex.recipes, entity)
    recs = [r for r in ex.records if r["entity"] == entity]
    fields = []
    for name, t in types.items():
        f = {"name": name, "label": labels.get(name, name.replace("_", " ").title())}
        fi = form.get(name, {})
        vals = [r["data"].get(name) for r in recs if r["data"].get(name) is not None]
        typ = t.get("type")
        if typ == "ref":
            fields.append({**f, "type": "string", "display_of": f"{name}_id"})
            fields.append({"name": f"{name}_id", "label": f["label"], "type": "ref", "to": t["to"],
                           "required": fi.get("required", False)})
            continue
        if typ == "date":
            f.update(type="date", format="YYYY-MM-DD", legacy_format=t.get("format"))
        elif typ == "money":
            f.update(type="number", format="money")
        elif typ == "number":
            f["type"] = "integer" if all(isinstance(v, int) for v in vals) else "number"
        elif fi.get("options") and all(v in fi["options"] for v in vals):
            f.update(type="enum", values=fi["options"])
        else:
            f["type"] = "string"
            if typ in ("time", "phone", "email", "datetime"):
                f["format"] = typ
        f["required"] = fi.get("required", False)
        fields.append(f)
    return fields


def _json_schema(entity, fields):
    props = {"legacy_id": {"type": "string", "description": "id in the legacy system"}}
    req = ["legacy_id"]
    for f in fields:
        null = [] if f.get("required") else ["null"]
        t = f["type"]
        if t == "date":
            p = {"type": ["string"] + null, "format": "date"}
        elif t in ("integer", "number"):
            p = {"type": [t] + null}
        elif t == "enum":
            p = {"enum": f["values"] + ([None] if null else [])}
        elif t == "ref":
            p = {"type": ["string"] + null, "x-ref": f["to"], "description": f"legacy_id of a {f['to']}"}
        else:
            p = {"type": ["string"] + null}
            if f.get("format") == "email":
                p["format"] = "email"
        p["title"] = f["label"]
        if len(p["type"] if "type" in p else []) == 1:
            p["type"] = p["type"][0]
        props[f["name"]] = p
        if f.get("required"):
            req.append(f["name"])
    return {"type": "object", "title": entity, "properties": props, "required": req, "additionalProperties": False}


def _ops(entities):
    ops = []
    for e in entities:
        plural = field_name(e) + "s"
        ops.append({"name": f"search_{plural}", "kind": "list", "entity": e, "source": "database",
                    "inputs": {"q": "string?", "limit": "integer?", "offset": "integer?"}})
        ops.append({"name": f"get_{field_name(e)}", "kind": "get", "entity": e, "source": "database",
                    "inputs": {"legacy_id": "string"}})
    return ops


def entity_forms(recipes, entity, fields):
    """Forms seen for an entity -> what a write endpoint would need (field names match the data model)."""
    names = {f["name"] for f in fields}
    forms = []
    for r in recipes["recipes"]:
        if r["kind"] != "form" or r.get("entity") != entity or not r.get("form"):
            continue
        path = r["url_pattern"].split("?")[0]
        purpose = "edit" if "{" in path else "create"
        ff = []
        for f in r["form"]["fields"]:
            name = f["field"]
            if f"{name}_id" in names and name in names:  # a reference: the form takes the other record's id
                name = f"{name}_id"
            item = {"name": name, "label": f["label"], "required": bool(f.get("required")),
                    "in_data_model": name in names, "input": f.get("type")}
            opts = [o for o in (f.get("options") or []) if not _PLACEHOLDER.match(o)]
            if opts:
                item["options"] = opts
            ff.append(item)
        forms.append({"page_id": r["page_id"], "purpose": purpose, "url_pattern": r["url_pattern"],
                      "id_params": r.get("id_params", []), "fields": ff,
                      "submit": [b["text"] for b in r["form"].get("submit", []) if b.get("type") != "reset"]})
    return forms


def _write_operator_inputs(ex, model, data):
    """The Operator's inputs, at the top of the run folder: data_model.json + records/<Entity>.jsonl."""
    root = ex.run_dir
    pages = {p["id"]: p for p in ex.site_map["pages"]}
    dm = {"site": ex.site_map["site"], "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "entities": [],
          "rules": model["rules"], "not_visible": model["not_visible"]}
    for e in model["entities"]:
        lists = [p for p in pages.values() if p.get("entity") == e["name"] and p["kind"] == "list"]
        details = [p for p in pages.values() if p.get("entity") == e["name"] and p["kind"] == "detail"]
        dm["entities"].append({
            **e, "record_count": len(data.get(e["name"], [])),
            "pages": {"list": lists[0]["id"] if lists else None, "detail": details[0]["id"] if details else None},
            "forms": entity_forms(ex.recipes, e["name"], e["fields"])})
    (root / "data_model.json").write_text(json.dumps(dm, indent=2, ensure_ascii=False), encoding="utf-8")
    rec_dir = root / "records"
    rec_dir.mkdir(exist_ok=True)
    for old in rec_dir.glob("*.jsonl"):
        old.unlink()
    for r in ex.records:
        with (rec_dir / f"{r['entity']}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"legacy_id": r["legacy_id"], "hash": r["hash"], "extracted_at": r["extracted_at"],
                                "data": r["data"]}, ensure_ascii=False) + "\n")


def write(ex, all_types):
    out = ex.out_dir
    (out / "spacetime").mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    schemas, model_entities, rules = [], [], []
    for entity, types in all_types.items():
        fields = entity_fields(ex, entity, types)
        ent_rules = [{"id": f"r{len(rules) + i + 1}", "entity": entity, "text": f"{f['label']} is required",
                      "source": "required marker on the form"} for i, f in enumerate(f for f in fields if f.get("required"))]
        rules += ent_rules
        relations = [{"field": f["name"], "to": f["to"]} for f in fields if f["type"] == "ref"]
        model_entities.append({"name": entity, "key": "legacy_id", "fields": fields, "relations": relations})
        schemas.append({"name": entity, "fields_json": json.dumps(fields), "rules_json": json.dumps(ent_rules)})

    model = {"entities": model_entities, "rules": rules,
             "not_visible": ["Anything the screens do not show (server-side logic, permissions, nightly jobs)"]}
    ops = {"operations": _ops(all_types)}
    tables = {
        "site": [{"url": ex.site_map["site"], "site_map_json": json.dumps(ex.site_map), "model_json": json.dumps(model),
                  "ops_json": json.dumps(ops), "docs_md": "", "updated_at": now}],
        "entity_schema": schemas,
        "record": [{"id": i + 1, "entity": r["entity"], "legacy_id": r["legacy_id"], "data_json": json.dumps(r["data"]),
                    "hash": r["hash"], "extracted_at": r["extracted_at"]} for i, r in enumerate(ex.records)],
        "job": [{"id": i + 1, **{k: j.get(k) for k in ("kind", "entity", "status", "done", "total", "started_at")}}
                for i, j in enumerate(ex.jobs)],
        "event": [{"id": i + 1, "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(e["ts"])), "actor": e["actor"],
                   "level": e["level"], "message": e["message"], "data_json": json.dumps(e["data"])}
                  for i, e in enumerate(ex.events)],
    }
    for name, rows in tables.items():
        (out / "spacetime" / f"{name}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": f"{ex.site_map['site']} records",
              "$defs": {e["name"]: _json_schema(e["name"], e["fields"]) for e in model_entities}}
    (out / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    (out / "model.json").write_text(json.dumps(model, indent=2), encoding="utf-8")
    data = {}
    for r in ex.records:
        data.setdefault(r["entity"], []).append({"legacy_id": r["legacy_id"], **r["data"]})
    (out / "data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    with (out / "records.jsonl").open("w", encoding="utf-8") as f:
        for r in ex.records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "duplicates.json").write_text(json.dumps(ex.duplicates, indent=2), encoding="utf-8")
    _write_operator_inputs(ex, model, data)
    from . import view
    view.render(out)
    return {"out_dir": str(out), "records": len(ex.records), "entities": {e: len(v) for e, v in data.items()},
            "relogins": ex.relogins, "duplicates": ex.duplicates, "model": model, "schema": schema}
