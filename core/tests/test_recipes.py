"""recipes.json: what the Operator needs to read lists/details and fill forms without Nemotron."""
import json

from explore import recipes
from explore.explorer import ExploreConfig, Explorer


def test_recipes_written_and_correct(site, tmp_path, creds):
    cfg = ExploreConfig(start_url=site.url + "/", out_dir=str(tmp_path / "run"), screenshots=False,
                        login="env", **creds)
    res = Explorer(cfg).run()
    path = tmp_path / "run" / "recipes.json"
    assert path.exists() and res["recipes_path"] == str(path)
    rec = json.loads(path.read_text())
    assert recipes.validate(rec) == []
    by = {r["page_id"]: r for r in rec["recipes"]}

    lst = by["patient_list"]
    cols = {c["header"]: c for c in lst["table"]["columns"]}
    assert lst["table"]["index"] >= 0
    assert cols["Name"]["split"]["into"] == ["last_name", "first_name"]
    assert cols["Name"]["split"]["separator"] == ", "
    assert cols["DOB"]["type"] == "date" and cols["DOB"]["format"] == "MM/DD/YYYY"
    dl = lst["detail_link"]
    assert dl["url_pattern"] == "/patients/{id}" and dl["goes_to"] == "patient_detail" and dl["id_param"] == "id"
    assert dl["column_header"] == "Name"
    assert lst["next_page"]["link"]["name"].startswith("Next") and lst["next_page"]["page_param"] == "page"

    labels = [l["label"] for l in by["patient_detail"]["labels"]]
    assert "Last Name" in labels and by["patient_detail"]["id_param"] == "id"

    form = by["patient_edit"]["form"]
    last = next(f for f in form["fields"] if f["label"] == "Last Name")
    assert last["required"] and last["locator"]["label"] == "Last Name"

    # rebuilding from the run folder gives the same recipes
    _, again = recipes.from_run_dir(tmp_path / "run")
    assert [r["page_id"] for r in again["recipes"]] == [r["page_id"] for r in rec["recipes"]]
    assert again["recipes"][0] == {**rec["recipes"][0]}


def test_split_and_format_detection():
    assert recipes.detect_split("Name", ["Smith, John", "Lee, Ana"])["into"] == ["last_name", "first_name"]
    assert recipes.detect_split("Name", ["Smith, John", "Cher"]) is None
    assert recipes.detect_format(["9:00", "13:30"])["type"] == "time"
    assert recipes.detect_format(["abc"]) is None
