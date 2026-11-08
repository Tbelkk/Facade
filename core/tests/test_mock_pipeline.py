"""Mock website -> Explorer -> recipes -> Extractor -> SpacetimeDB-shaped JSON, checked against the mock data."""
import json
from pathlib import Path

import pytest

from extract.extractor import Extractor
from mock_sites import run as mock_run


def _conforms(rec, schema):
    props, req = schema["properties"], schema["required"]
    assert set(rec) <= set(props), set(rec) - set(props)
    for k in req:
        assert rec.get(k) is not None, k


@pytest.mark.parametrize("name", ["clinic", "inventory"])
def test_mock_site_extracts_exactly(name, tmp_path):
    r = mock_run.run(name, out=tmp_path / name, quiet=True)
    assert r["writes"] == []                                  # read-only, end to end
    for ent, c in r["check"].items():
        assert c["missing"] == [] and c["extra"] == [], (ent, c)
        assert c["accuracy"] == 100.0, (ent, c["mismatches"])

    out = Path(r["out"]) / "extract"
    tables = {t: json.loads((out / "spacetime" / f"{t}.json").read_text())
              for t in ("site", "entity_schema", "record", "job", "event")}
    assert set(tables["record"][0]) == {"id", "entity", "legacy_id", "data_json", "hash", "extracted_at"}
    assert set(tables["site"][0]) == {"url", "site_map_json", "model_json", "ops_json", "docs_md", "updated_at"}
    assert set(tables["entity_schema"][0]) == {"name", "fields_json", "rules_json"}
    assert all(j["status"] == "done" and j["done"] == j["total"] for j in tables["job"])

    schema = json.loads((out / "schema.json").read_text())
    for row in tables["record"]:
        _conforms({"legacy_id": row["legacy_id"], **json.loads(row["data_json"])}, schema["$defs"][row["entity"]])


def test_clinic_relogin_duplicates_and_rerun(tmp_path):
    r = mock_run.run("clinic", out=tmp_path / "c", quiet=True)
    assert r["session_expired"] >= 1 and r["extract"]["relogins"] >= 1
    assert any(set(d["legacy_ids"]) == {"1", "35"} for d in r["extract"]["duplicates"])
    fields = {f["name"]: f for f in r["extract"]["model"]["entities"][1]["fields"]}
    assert fields["patient_id"]["type"] == "ref" and fields["patient_id"]["to"] == "Patient"
    assert fields["provider"]["type"] == "enum" and fields["date"]["type"] == "date"
    assert fields["date"]["required"] is True

    # a second extraction of unchanged data marks every record "unchanged"
    from mock_sites import server
    srv = server.start("clinic")
    try:
        # the run folder still points at the old port: rewrite the start URL to the new server
        sm_path = Path(r["out"]) / "site_map.json"
        old = json.loads(sm_path.read_text())["site"]
        for f in [sm_path, Path(r["out"]) / "recipes.json"]:
            f.write_text(f.read_text().replace(old, srv.url))
        lg = srv.site["login"]
        res = Extractor(r["out"], login="env", username=lg["username"], password=lg["password"], log=False).run()
    finally:
        srv.shutdown()
    recs = [json.loads(l) for l in (Path(res["out_dir"]) / "records.jsonl").read_text().splitlines()]
    assert recs and all(x["change"] == "unchanged" for x in recs)
