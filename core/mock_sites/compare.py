"""Ground truth check: does the extracted data match the mock site's own data file?"""
from explore.recipes import field_name


def expected_records(site, entity):
    """Mock data -> what a perfect extraction would produce (field names come from the LABELS the site shows)."""
    from .server import display
    out = {}
    for rec in entity["records"]:
        exp = {}
        for f in entity["fields"]:
            name, v = field_name(f["label"]), rec.get(f["key"])
            v = None if v in ("", None) else v
            if f.get("ref"):
                target = site["_by_name"][f["ref"]]
                ref = target["_by_id"].get(str(v)) if v is not None else None
                exp[name] = display(site, target, ref) if ref else None
                exp[name + "_id"] = str(v) if v is not None else None
            elif f.get("type") == "money":
                exp[name] = float(v) if v is not None else None
            else:
                exp[name] = v
        out[str(rec["id"])] = exp
    return out


def compare(site, extract_result_data, recipes):
    """-> {entity: {expected, extracted, missing, extra, fields_checked, fields_wrong, mismatches[]}}"""
    # Match extracted entity names to mock entities by URL path, not by name (Nemotron may name them differently).
    path_to_entity = {}
    for r in recipes["recipes"]:
        if r["kind"] == "detail" and r.get("entity"):
            path_to_entity[r["url_pattern"].strip("/").split("/")[0]] = r["entity"]
    report = {}
    for e in site["entities"]:
        got_name = path_to_entity.get(e["path"])
        got = {r["legacy_id"]: r for r in extract_result_data.get(got_name, [])}
        exp = expected_records(site, e)
        rep = {"extracted_as": got_name, "expected": len(exp), "extracted": len(got),
               "missing": sorted(set(exp) - set(got)), "extra": sorted(set(got) - set(exp)),
               "fields_checked": 0, "fields_wrong": 0, "mismatches": []}
        for lid, want in exp.items():
            have = got.get(lid)
            if not have:
                continue
            for k, v in want.items():
                rep["fields_checked"] += 1
                if have.get(k) != v:
                    rep["fields_wrong"] += 1
                    if len(rep["mismatches"]) < 15:
                        rep["mismatches"].append({"legacy_id": lid, "field": k, "expected": v, "got": have.get(k)})
        total = rep["fields_checked"] + len(rep["missing"]) * len(e["fields"])
        rep["accuracy"] = round(100 * (rep["fields_checked"] - rep["fields_wrong"]) / total, 1) if total else 0.0
        report[e["name"]] = rep
    return report
