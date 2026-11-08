"""Tidy the extracted data before the API is designed, so endpoints and JSON fields explain themselves.

The Explorer names things one page at a time. This pass looks at everything it found at once:
  code      drops entities with no records (and no form), and fields that never had a value
  Nemotron  renames vague entities/fields to what the values really are, writes a one-line description
            for every entity and field, merges entities that are the same kind of record, and drops
            ones that are only page layout (a navigation menu, a page wrapper)
  code      checks every suggestion (valid names, no collisions, nothing invented) and applies only those

The run folder is rewritten (data_model.json + records/*.jsonl) so the database and the API both get the
clean names. Without Nemotron only the code steps run.
"""
import json
import re
from pathlib import Path

ENTITY_RE = re.compile(r"^[A-Z][A-Za-z0-9]{1,40}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")

SYSTEM = """You are the Operator agent of RESTore, cleaning up data that another agent extracted from a legacy
website, BEFORE it becomes a public REST API. Developers will only see entity names (they become endpoints like
/announcements) and field names (JSON keys). They must understand every one without opening the old site.

You get each entity with its fields and real sample values. Return JSON only:
{"entities": [
   {"from": "<current entity name>",
    "name": "<clear PascalCase singular name of what ONE record is, e.g. Announcement, Course, CourseInfo>",
    "description": "<one plain sentence: what one record is, e.g. 'A dated announcement posted on the home page.'>",
    "fields": {"<current field name>": {"name": "<clear snake_case name>", "description": "<what the value is>"}},
    "drop_fields": ["<fields that are page layout, not data: navigation menu text, empty markers like ';'>"]}
 ],
 "move": [{"from": "<entity>", "page": "<one of its by_source pages>", "to": "<PascalCase entity for those rows>",
           "description": "<one sentence>"}],
 "drop": ["<entities that are only page layout, not business data, or that duplicate another entity>"]}

Rules:
- Name things by what the VALUES are (look at the samples), not by the old names. A record of
  {"note": "Office and Hours", "note_detail": "Room: SCI 1.220"} is course information with a "topic" and "details".
- Never use vague names: Item, Record, Entry, Note, Info, Data, Content; fields col1, value, text, note, note_detail.
- Two entities holding the same kind of record get the SAME new name (they will be merged).
- "by_source" shows an entity's rows grouped by the page they came from. If one group is a different kind of
  record (e.g. Course rows from a course's own page that are really "Office and Hours", "Textbook", "Graders"),
  "move" that group to its own entity (e.g. CourseInfo). Never move the main group.
- Keep every entity that holds real information; drop only layout or duplicates. Never invent fields."""


def _sample(rows, field, n=3):
    vals = [r.get(field) for r in rows if r.get(field) not in (None, "")]
    return [str(v)[:120] for v in vals[:n]]


def code_clean(dm, records, report):
    """No-AI part: empty entities and never-filled fields go."""
    keep = []
    for e in dm["entities"]:
        rows = records.get(e["name"], [])
        if not rows and not e.get("forms"):
            report["dropped_entities"].append({"entity": e["name"], "why": "no records"})
            continue
        form_fields = {x["name"] for f in e.get("forms", []) for x in f.get("fields", [])}
        before = len(e["fields"])
        e["fields"] = [f for f in e["fields"]
                       if f["name"] in form_fields or any(r.get(f["name"]) not in (None, "") for r in rows)]
        if len(e["fields"]) < before:
            report["dropped_fields"].append({"entity": e["name"], "count": before - len(e["fields"]),
                                             "why": "never had a value"})
        keep.append(e)
    dm["entities"] = keep


def read_sources(run_dir):
    """{entity: {legacy_id: page pattern}} from the _page the Explorer keeps on each record."""
    from operator_agent.inputs import legacy_id_of
    out = {}
    for p in (Path(run_dir) / "records").glob("*.jsonl"):
        m = out.setdefault(p.stem, {})
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("_page"):
                    m[legacy_id_of(r)] = r["_page"]
    return out


def by_source(rows, src):
    groups = {}
    for r in rows:
        groups.setdefault(src.get(r.get("legacy_id")) or "?", []).append(r)
    return groups


def ask_nemotron(dm, records, sources=None, model=None, budget=None):
    from ingest import nemotron
    prof = []
    for e in dm["entities"]:
        rows = records.get(e["name"], [])
        p = {"entity": e["name"], "record_count": len(rows),
             "fields": {f["name"]: _sample(rows, f["name"]) for f in e["fields"]}}
        groups = by_source(rows, (sources or {}).get(e["name"], {}))
        if len(groups) > 1:
            p["by_source"] = [{"page": pg, "count": len(g),
                               "samples": [{k: str(v)[:80] for k, v in r.items() if k != "legacy_id"} for r in g[:2]]}
                              for pg, g in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:6]]
        prof.append(p)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Site: " + str(dm.get("site")) + "\nEntities:\n"
                 + json.dumps(prof, ensure_ascii=False, indent=1)[:14000]}]
    res = nemotron.chat(messages, purpose="operator_tidy", model=model, budget=budget, answer_tokens=4000,
                        temperature=0.2)
    return nemotron.extract_json(res["text"]), res["ms"]


def validate_moves(plan, dm, records, sources):
    """Moves of one source page's rows to another entity; never the biggest group, never all rows."""
    names = {e["name"] for e in dm["entities"]}
    ok, problems = [], []
    for mv in (plan.get("move") or []) if isinstance(plan, dict) else []:
        if not isinstance(mv, dict) or mv.get("from") not in names:
            continue
        groups = by_source(records.get(mv["from"], []), sources.get(mv["from"], {}))
        biggest = max(groups, key=lambda k: len(groups[k])) if groups else None
        if mv.get("page") not in groups or mv["page"] == biggest:
            problems.append(f"move {mv.get('from')}/{mv.get('page')}: not a movable group")
        elif not ENTITY_RE.match(str(mv.get("to") or "")) or mv["to"] == mv["from"]:
            problems.append(f"move to {mv.get('to')!r}: not a valid new entity name")
        else:
            ok.append(mv)
    return ok, problems


def apply_moves(dm, records, moves, sources, report):
    ents = {e["name"]: e for e in dm["entities"]}
    for mv in moves:
        src = sources.get(mv["from"], {})
        rows = records.get(mv["from"], [])
        moving = [r for r in rows if src.get(r.get("legacy_id")) == mv["page"]]
        records[mv["from"]] = [r for r in rows if src.get(r.get("legacy_id")) != mv["page"]]
        keys = {k for r in moving for k in r if k != "legacy_id"}
        old = ents[mv["from"]]
        tgt = ents.get(mv["to"])
        if tgt is None:
            tgt = ents[mv["to"]] = {"name": mv["to"], "description": str(mv.get("description") or "")[:240],
                                    "fields": [], "rules": [], "forms": [], "relations": [], "key": "legacy_id"}
            dm["entities"].append(tgt)
        have = {f["name"] for f in tgt["fields"]}
        tgt["fields"] += [dict(f) for f in old["fields"] if f["name"] in keys and f["name"] not in have]
        records[mv["to"]] = records.get(mv["to"], []) + moving
        report["moved"].append({"from": mv["from"], "page": mv["page"], "to": mv["to"], "count": len(moving)})
    for e in dm["entities"]:   # a field no row of the entity uses any more goes
        rows = records.get(e["name"], [])
        if rows:
            e["fields"] = [f for f in e["fields"] if any(r.get(f["name"]) not in (None, "") for r in rows)
                           or f["name"] in {x["name"] for fm in e.get("forms", []) for x in fm.get("fields", [])}]


def validate(plan, dm):
    """Keep only suggestions that are safe to apply. Returns (entity plans by old name, drops, problems)."""
    names = {e["name"]: e for e in dm["entities"]}
    problems, out, drops = [], {}, []
    if not isinstance(plan, dict):
        return {}, [], ["answer is not a JSON object"]
    for d in plan.get("drop") or []:
        if d in names:
            drops.append(d)
        else:
            problems.append(f"drop: no entity {d!r}")
    if len(drops) >= len(names):
        problems.append("would drop every entity; ignoring drops")
        drops = []
    for p in plan.get("entities") or []:
        if not isinstance(p, dict) or p.get("from") not in names or p["from"] in drops:
            continue
        e = names[p["from"]]
        new = p.get("name") if isinstance(p.get("name"), str) and ENTITY_RE.match(p.get("name", "")) else e["name"]
        have = {f["name"] for f in e["fields"]}
        drop_f = [f for f in (p.get("drop_fields") or []) if f in have]
        if len(drop_f) >= len(have):
            drop_f = []   # never empty an entity
        renames, descs, used = {}, {}, set()
        for old, spec in (p.get("fields") or {}).items():
            if old not in have or old in drop_f:
                continue
            spec = spec if isinstance(spec, dict) else {"name": spec}
            nn = spec.get("name") if isinstance(spec.get("name"), str) and FIELD_RE.match(spec.get("name") or "") else old
            if nn in used or (nn != old and nn in have and nn not in (p.get("fields") or {})):
                problems.append(f"{e['name']}.{old} -> {nn}: name already taken")
                nn = old
            used.add(nn)
            renames[old] = nn
            if isinstance(spec.get("description"), str):
                descs[nn] = spec["description"][:200]
        out[e["name"]] = {"name": new, "description": str(p.get("description") or "")[:240],
                          "renames": renames, "descriptions": descs, "drop_fields": drop_f}
    return out, drops, problems


def apply(dm, records, plans, drops, report):
    merged = {}   # new name -> entity dict
    new_records = {}
    for e in dm["entities"]:
        if e["name"] in drops:
            report["dropped_entities"].append({"entity": e["name"], "why": "page layout or duplicate (Nemotron)"})
            continue
        p = plans.get(e["name"], {"name": e["name"], "renames": {}, "descriptions": {}, "drop_fields": [],
                                  "description": ""})
        ren = lambda f: p["renames"].get(f, f)
        fields = []
        for f in e["fields"]:
            if f["name"] in p["drop_fields"]:
                continue
            f = {**f, "name": ren(f["name"])}
            if p["descriptions"].get(f["name"]):
                f["description"] = p["descriptions"][f["name"]]
            fields.append(f)
        rows = [{ren(k): v for k, v in r.items() if k not in p["drop_fields"]} for r in records.get(e["name"], [])]
        if p["name"] != e["name"] or p["renames"] or p["drop_fields"]:
            report["renamed"].append({"from": e["name"], "to": p["name"],
                                      "fields": {k: v for k, v in p["renames"].items() if k != v},
                                      "dropped_fields": p["drop_fields"]})
        tgt = merged.get(p["name"])
        if tgt is None:
            tgt = merged[p["name"]] = {**e, "name": p["name"], "fields": fields}
            if p["description"]:
                tgt["description"] = p["description"]
            new_records[p["name"]] = rows
        else:   # same kind of record found under two names: one entity
            report["merged"].append({"from": e["name"], "into": p["name"]})
            have = {f["name"] for f in tgt["fields"]}
            tgt["fields"] += [f for f in fields if f["name"] not in have]
            tgt["forms"] = tgt.get("forms", []) + e.get("forms", [])
            tgt["rules"] = sorted(set(tgt.get("rules", [])) | set(e.get("rules", [])))
            by_id = {r["legacy_id"]: r for r in new_records[p["name"]]}
            for r in rows:
                by_id[r["legacy_id"]] = {**by_id.get(r["legacy_id"], {}), **r}
            new_records[p["name"]] = list(by_id.values())
    dm["entities"] = list(merged.values())
    return dm, new_records


def write(run_dir, dm, records):
    """Rewrite the run folder with the clean names (the old per-entity files are replaced)."""
    run_dir = Path(run_dir)
    rec_dir = run_dir / "records"
    for p in list(rec_dir.glob("*.jsonl")) + list(rec_dir.glob("*.csv")):
        p.unlink()
    for e in dm["entities"]:
        with (rec_dir / f"{e['name']}.jsonl").open("w", encoding="utf-8") as f:
            for r in records.get(e["name"], []):
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        e["record_count"] = len(records.get(e["name"], []))
    (run_dir / "data_model.json").write_text(json.dumps(dm, indent=2, ensure_ascii=False, default=str),
                                             encoding="utf-8")


def tidy(run_dir, dm, records, use_nemotron=True, log=print):
    """-> (dm, records, report). Cleans in place and rewrites the run folder."""
    import os
    report = {"by": "code", "dropped_entities": [], "dropped_fields": [], "renamed": [], "merged": [],
              "moved": [], "problems": [], "nemotron_ms": 0}
    sources = read_sources(run_dir)
    code_clean(dm, records, report)
    if use_nemotron and dm["entities"]:
        try:
            model = os.getenv("MODEL_AGENT") or None
            plan, ms = ask_nemotron(dm, records, sources, model=model)
            moves, mp = validate_moves(plan, dm, records, sources)
            apply_moves(dm, records, moves, sources, report)
            plans, drops, problems = validate(plan, dm)
            report.update(by="nemotron", nemotron_ms=ms, problems=mp + problems)
            dm, records = apply(dm, records, plans, drops, report)
        except Exception as e:   # network/JSON trouble: keep the names we have, say so
            report["problems"].append(f"Nemotron tidy failed: {str(e)[:160]}")
    write(run_dir, dm, records)
    for d in report["dropped_entities"]:
        log(f"  tidy: dropped {d['entity']} ({d['why']})")
    for rn in report["renamed"]:
        f = ", ".join(f"{a}->{b}" for a, b in rn["fields"].items())
        log(f"  tidy: {rn['from']} -> {rn['to']}" + (f"  [{f}]" if f else "")
            + (f"  dropped {rn['dropped_fields']}" if rn["dropped_fields"] else ""))
    for m in report["moved"]:
        log(f"  tidy: moved {m['count']} {m['from']} rows from {m['page']} into {m['to']}")
    for m in report["merged"]:
        log(f"  tidy: merged {m['from']} into {m['into']}")
    return dm, records, report
