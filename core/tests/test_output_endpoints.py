"""The final endpoint data SpacetimeDB receives (shared/output/<site>/) is correct.

1. Every published site passes every check (records typed, endpoints answer correctly, examples current).
2. The checker really catches problems: each test breaks a copy of a site in one way and expects the error.
No API key and no database needed.
"""
import json
import shutil
from pathlib import Path

import pytest

from operator_agent import verify

SITES = verify.sites()


@pytest.mark.parametrize("folder", SITES, ids=[p.name for p in SITES])
def test_published_site_is_correct(folder):
    rep = verify.verify(folder)
    assert rep["errors"] == [], "\n".join(rep["errors"])
    assert rep["checks"] > 50


def test_there_is_published_output():
    assert SITES, "shared/output/ has no sites: publish one with python -m operator_agent.run <run folder>"


# ------------------------------------------------------------------ the checker catches real problems

@pytest.fixture()
def clinic(tmp_path):
    src = verify.OUTPUT / "clinic"
    if not src.exists():
        pytest.skip("shared/output/clinic is not published")
    dst = tmp_path / "clinic"
    shutil.copytree(src, dst)
    return dst


def _rewrite(path, fn):
    lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    lines = fn(lines)
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))


def _errors(folder):
    return "\n".join(verify.verify(folder)["errors"])


def test_clean_copy_passes(clinic):
    assert _errors(clinic) == ""


def test_catches_wrong_value_type(clinic):
    def bad(rows):
        rows[0]["data"]["dob"] = "03/13/1960"          # legacy format instead of ISO
        rows[0]["hash"] = verify._hash(rows[0]["data"])
        return rows
    _rewrite(clinic / "records" / "Patient.jsonl", bad)
    assert "Patient.dob: value '03/13/1960'" in _errors(clinic)


def test_catches_duplicate_id_and_bad_hash(clinic):
    def bad(rows):
        rows[1]["legacy_id"] = rows[0]["legacy_id"]
        rows[2]["data"]["phone"] = "changed"           # data changed, hash not updated
        return rows
    _rewrite(clinic / "records" / "Patient.jsonl", bad)
    err = _errors(clinic)
    assert "is empty or repeated" in err and "hash does not match" in err


def test_catches_unknown_field_and_broken_reference(clinic):
    def bad(rows):
        rows[0]["data"]["surprise"] = 1
        rows[1]["data"]["patient_id"] = "99999"
        for r in rows[:2]:
            r["hash"] = verify._hash(r["data"])
        return rows
    _rewrite(clinic / "records" / "Appointment.jsonl", bad)
    err = _errors(clinic)
    assert "fields not in the data model: ['surprise']" in err
    assert "points at Patient ids that do not exist" in err


def test_catches_stale_example_and_manifest_mismatch(clinic):
    ops = json.loads((clinic / "operations.json").read_text())
    lst = next(o for o in ops["operations"] if o["kind"] == "list")
    lst["example"]["response"]["total"] += 1
    (clinic / "operations.json").write_text(json.dumps(ops))
    _rewrite(clinic / "records" / "Patient.jsonl", lambda rows: rows[:-1])
    err = _errors(clinic)
    assert "no longer matches what the endpoint returns" in err
    assert "manifest says 35 Patient records" in err


def test_catches_endpoint_on_missing_field_and_write_without_form(clinic):
    ops = json.loads((clinic / "operations.json").read_text())
    lst = next(o for o in ops["operations"] if o["kind"] == "list" and o["entity"] == "Patient")
    lst["inputs"].append({"name": "min_height", "in": "query", "type": "integer", "field": "height", "match": "gte"})
    dm = json.loads((clinic / "data_model.json").read_text())
    for e in dm["entities"]:
        e["forms"] = []                                 # pretend no form was ever seen
    (clinic / "data_model.json").write_text(json.dumps(dm))
    (clinic / "operations.json").write_text(json.dumps(ops))
    err = _errors(clinic)
    assert "uses field 'height'" in err
    assert "has write endpoints but no form was seen" in err


def test_catches_filter_that_does_not_filter(clinic, monkeypatch):
    from operator_agent import query
    real = query.run
    monkeypatch.setattr(query, "run", lambda op, params, records: real(op, {k: v for k, v in params.items()
                                                                           if k in ("limit", "offset", "id")}, records))
    assert "returned records that do not match" in _errors(clinic)


def test_cli_exit_code(clinic, capsys):
    with pytest.raises(SystemExit) as ok:
        verify.main([str(clinic)])
    assert ok.value.code == 0 and "[PASS] clinic" in capsys.readouterr().out
    _rewrite(clinic / "records" / "Patient.jsonl", lambda rows: [{**rows[0], "legacy_id": ""}] + rows[1:])
    with pytest.raises(SystemExit) as bad:
        verify.main([str(clinic)])
    assert bad.value.code == 1
