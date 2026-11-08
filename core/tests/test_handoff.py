"""The fixed handoff folder: replaced as a whole on each publish, never mixing runs."""
import json
import shutil
from pathlib import Path

from extract import handoff

EX = Path(__file__).resolve().parent.parent / "operator_agent" / "examples"


def test_publish_replaces_whole_folder(tmp_path):
    dest = tmp_path / "latest"
    handoff.publish(EX / "clinic", dest=dest, log=lambda *a: None)
    m = json.loads((dest / "manifest.json").read_text())
    assert m["records"] == {"Appointment": 27, "Patient": 35}
    assert (dest / "records" / "Patient.jsonl").exists() and (dest / "data_model.json").exists()

    news = tmp_path / "news"
    shutil.copytree(EX / "news", news)
    (news / "operations.json").unlink(missing_ok=True)
    handoff.publish(news, dest=dest, log=lambda *a: None)
    m = json.loads((dest / "manifest.json").read_text())
    assert set(m["records"]) == {"Post", "User"} and m["operations"] is None
    assert not (dest / "records" / "Patient.jsonl").exists()      # nothing left over from the clinic run
    assert not (dest / "operations.json").exists()                 # no stale API design from another run
    assert not (tmp_path / "latest.tmp").exists() and not (tmp_path / "latest.old").exists()
