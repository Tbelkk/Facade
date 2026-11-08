"""shared/output/<site>/: replaced as a whole on each publish, never mixing runs; index.json tracks them."""
import json
import shutil
from pathlib import Path

from extract import handoff

EX = Path(__file__).resolve().parent.parent / "operator_agent" / "examples"


def test_publish_replaces_site_folder_and_indexes(tmp_path):
    root = tmp_path / "output"
    handoff.publish(EX / "clinic", root=root, log=lambda *a: None)
    m = json.loads((root / "clinic" / "manifest.json").read_text())
    assert m["records"] == {"Appointment": 27, "Patient": 35} and m["operations"]["count"] > 0

    run = tmp_path / "clinic_20261108-120000"          # a newer run of the same site, no API design yet
    shutil.copytree(EX / "news", run)
    (run / "operations.json").unlink()
    handoff.publish(run, root=root, log=lambda *a: None)
    m = json.loads((root / "clinic" / "manifest.json").read_text())
    assert set(m["records"]) == {"Post", "User"} and m["operations"] is None
    assert not (root / "clinic" / "records" / "Patient.jsonl").exists()   # nothing left from the old run
    assert not (root / "clinic" / "operations.json").exists()              # no stale API design

    handoff.publish(EX / "news", root=root, log=lambda *a: None)
    idx = json.loads((root / "index.json").read_text())
    assert idx["latest"] == "news" and set(idx["sites"]) == {"clinic", "news"}
    assert not any(p.name.startswith(".") for p in root.iterdir())


def test_site_name():
    assert handoff.site_name("/x/cache/mock/clinic_20261108-001314") == "clinic"
    assert handoff.site_name("/repo/shared/samples/hackernews") == "hackernews"
    assert handoff.site_name("/x/127_0_0_1_5055_20261108-001314", "http://127.0.0.1:5055") == "127_0_0_1_5055"


def test_flat_records_are_published_canonical(tmp_path):
    run = tmp_path / "hn"
    (run / "records").mkdir(parents=True)
    (run / "data_model.json").write_text(json.dumps({"site": "https://news.example", "entities": [
        {"name": "Post", "fields": [{"name": "title", "type": "string"}, {"name": "points", "type": "int"}]}]}))
    (run / "records" / "Post.jsonl").write_text(
        json.dumps({"_key": "https://news.example/item?id=42", "title": "Hi", "points": "1,204"}) + "\n")
    dest = handoff.publish(run, root=tmp_path / "out", log=lambda *a: None)
    line = json.loads((dest / "records" / "Post.jsonl").read_text().splitlines()[0])
    assert line["legacy_id"] == "42" and line["data"] == {"title": "Hi", "points": 1204} and line["hash"]
    dm = json.loads((dest / "data_model.json").read_text())
    assert dm["entities"][0]["fields"][1]["type"] == "integer"
