"""Operator agent: extracted data -> operations.json + api_docs.md. No API key needed (Nemotron is simulated)."""
import json
import shutil
from pathlib import Path

from operator_agent import design, inputs, run as op_run

EXAMPLES = Path(__file__).resolve().parent.parent / "operator_agent" / "examples"


def _copy(name, tmp_path):
    dst = tmp_path / name
    shutil.copytree(EXAMPLES / name, dst, ignore=shutil.ignore_patterns("operations.json", "api_docs.md"))
    return dst


def test_news_is_read_only_with_real_filters(tmp_path):
    d = _copy("news", tmp_path)
    doc = op_run.run(d, use_nemotron=False, log=lambda *a: None)
    ops = {o["name"]: o for o in doc["operations"]}
    assert (d / "operations.json").exists() and (d / "api_docs.md").exists()
    assert all(o["source"] == "database" and o["method"] == "GET" for o in ops.values())   # no form -> no writes
    names = [i["name"] for i in ops["list_posts"]["inputs"]]
    assert {"min_points", "max_points", "author", "author_id"} <= set(names)
    assert ops["get_post"]["path"] == "/posts/{id}" and ops["search_posts"]["path"] == "/posts/search"
    ex = ops["list_posts"]["example"]
    assert ex["response"]["total"] > 0 and ex["request"].startswith("/posts?")
    dm, _, _ = inputs.load(d)
    assert design.check(doc["operations"], dm) == []
    assert "No form was seen" in (d / "api_docs.md").read_text()


def test_clinic_writes_come_from_forms(tmp_path):
    d = _copy("clinic", tmp_path)
    doc = op_run.run(d, use_nemotron=False, log=lambda *a: None)
    ops = {o["name"]: o for o in doc["operations"]}
    cp = ops["create_patient"]
    assert cp["method"] == "POST" and cp["path"] == "/patients" and cp["source"] == "legacy"
    req = {i["name"] for i in cp["inputs"] if i["required"]}
    assert req == {"last_name"}
    ca = ops["create_appointment"]
    assert {"date", "time", "patient_id"} <= {i["name"] for i in ca["inputs"] if i["required"]}
    prov = next(i for i in ca["inputs"] if i["name"] == "provider")
    assert prov["values"] == ["Dr. Lee", "Dr. Patel", "Hyg. Kim"]
    assert ops["update_patient"]["method"] == "PATCH" and ops["update_patient"]["path"] == "/patients/{id}"


def test_checker_catches_bad_designs(tmp_path):
    dm, _, records = inputs.load(_copy("news", tmp_path))
    good = design.heuristic(dm, inputs.profile(dm, records))
    assert design.check(good, dm) == []
    bad = json.loads(json.dumps(good))
    bad[0]["inputs"].append({"name": "min_title", "in": "query", "field": "title", "match": "gte"})
    bad[0]["inputs"].append({"name": "x", "in": "query", "field": "nope", "match": "eq"})
    bad.append({**bad[1], "name": "get_post_again"})                                 # duplicate path
    bad.append({"name": "Create Post", "method": "POST", "path": "/posts", "entity": "Post", "kind": "create",
                "source": "legacy", "inputs": []})
    text = "\n".join(design.check(bad, dm))
    assert "gte/lte only work on numbers/dates" in text
    assert "uses field 'nope'" in text
    assert "duplicates another endpoint's path" in text
    assert "has no form on the old site" in text
    assert "snake_case" in text


def test_nemotron_designs_then_fixes_once(tmp_path, monkeypatch):
    from ingest import nemotron
    d = _copy("clinic", tmp_path)
    dm, _, records = inputs.load(d)
    good = design.heuristic(dm, inputs.profile(dm, records))
    broken = json.loads(json.dumps(good))
    broken[0]["inputs"].append({"name": "min_phone", "in": "query", "field": "phone", "match": "gte"})
    calls = []

    def fake_chat(messages, purpose="call", model=None, **kw):
        if purpose == "operator_tidy":   # the clean-up pass: keep the names as they are
            return {"text": "{}", "ms": 1}
        calls.append(messages[-1]["content"])
        return {"text": json.dumps({"operations": broken if len(calls) == 1 else good}), "ms": 7}

    monkeypatch.setattr(nemotron, "chat", fake_chat)
    doc = op_run.run(d, use_nemotron=True, log=lambda *a: None)
    m = doc["designed_by"]
    assert m["by"] == "nemotron" and m["attempts"] == 2
    assert any("min_phone" in p for p in m["problems_found"]) and m["problems_after_fix"] == []
    assert "min_phone" in calls[1]                       # Nemotron was told exactly what was wrong
    assert len(doc["operations"]) == len(good)


def test_nemotron_failure_falls_back(tmp_path, monkeypatch):
    from ingest import nemotron
    monkeypatch.setattr(nemotron, "chat", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("timeout")))
    doc = op_run.run(_copy("news", tmp_path), use_nemotron=True, log=lambda *a: None)
    assert doc["designed_by"]["by"] == "heuristic_fallback" and doc["operations"]
