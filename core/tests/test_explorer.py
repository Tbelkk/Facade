"""End-to-end Explorer tests against the local legacy test site. No API key needed:
the heuristic reader/planner run for real, and Nemotron is simulated where a test needs it."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from explore import policy
from explore.explorer import ExploreConfig, Explorer, validate_site_map


def run(site, tmp_path, creds=None, **kw):
    kw.setdefault("page_budget", 25)
    cfg = ExploreConfig(start_url=site.url + "/", out_dir=str(tmp_path / "run"), screenshots=False,
                        login="env" if creds else "none", **(creds or {}), **kw)
    return Explorer(cfg).run()


def by_id(sm):
    return {p["id"]: p for p in sm["pages"]}


def test_maps_the_whole_site_offline(site, tmp_path, creds):
    res = run(site, tmp_path, creds)
    sm = res["site_map"]
    assert validate_site_map(sm) == []
    pages = by_id(sm)

    # every page type, once
    for pid, kind in {"login": "login", "patient_list": "list", "patient_detail": "detail",
                      "patient_edit": "form", "patient_new": "form", "appointment_new": "form",
                      "appointment_detail": "detail"}.items():
        assert pages[pid]["kind"] == kind, pid
    patterns = [p["url_pattern"] for p in sm["pages"]]
    assert len(patterns) == len(set(patterns))
    assert "/patients/{id}" in patterns and "/appointments/new?patient_id={patient_id}" in patterns

    # list structure (format 7.2)
    pl = pages["patient_list"]
    assert pl["pagination"]["next"] == {"role": "link", "name": "Next >>"}
    assert pl["pagination"]["page_size"] == 10
    assert pl["row_link"] == {"column": "Name", "goes_to": "patient_detail"}
    assert {"from": "patient_list", "to": "patient_detail", "via": "row link"} in sm["edges"]

    # outputs for the Understand step
    run_dir = Path(res["run_dir"])
    assert (run_dir / "pages" / "patient_edit.json").is_file()
    assert (run_dir / "events.jsonl").read_text().count("\n") > 5
    assert sm["stats"]["stop_reason"] == "nothing_left"


def test_never_writes(site, tmp_path, creds):
    res = run(site, tmp_path, creds)
    posts = [path for method, path in site.hits if method != "GET"]
    assert posts == ["/login"], posts                     # the single login submit only
    assert site.writes == []                              # no delete / logout / cancel / save
    assert not any("autosave" in path for _, path in site.hits)
    notes = " ".join(res["site_map"]["notes"])
    assert "Log Out" in notes and "Delete patient" in notes


def test_respects_page_budget(site, tmp_path, creds):
    sm = run(site, tmp_path, creds, page_budget=4)["site_map"]
    assert len(sm["pages"]) == 4
    assert sm["stats"]["stop_reason"] == "budget"
    assert sm["unexplored"]


def test_login_required_is_reported_not_crashed(site, tmp_path):
    sm = run(site, tmp_path)["site_map"]
    assert sm["stats"]["stop_reason"] == "login_required"
    assert [p["kind"] for p in sm["pages"]] == ["login"]
    assert "--login" in " ".join(sm["notes"])


def test_relogs_in_when_the_session_expires(site, tmp_path, creds):
    class ExpiringPlanner(policy.HeuristicPlanner):
        steps = 0

        def choose(self, *a):
            ExpiringPlanner.steps += 1
            if ExpiringPlanner.steps == 3:
                site.sessions.clear()  # server forgets everyone, like a 10-minute timeout
            return super().choose(*a)

    cfg = ExploreConfig(start_url=site.url + "/", out_dir=str(tmp_path / "run"), screenshots=False, login="env", **creds)
    sm = Explorer(cfg, planner=ExpiringPlanner()).run()["site_map"]
    logins = [path for method, path in site.hits if method == "POST"]
    assert logins == ["/login", "/login"]
    assert "patient_detail" in by_id(sm)
    assert not any(p["id"].startswith("login_") for p in sm["pages"])


def test_nemotron_roles_with_simulated_model(site, tmp_path, creds, monkeypatch):
    """Reader + planner prompts, validation and fallbacks, with a scripted fake Nemotron."""
    from ingest import nemotron

    calls = []

    def fake_chat(messages, purpose="call", model=None, **kw):
        calls.append((purpose, model))
        user = messages[1]["content"]
        text = user[0]["text"] if isinstance(user, list) else user
        if purpose == "explore_read":
            if "Pattern: /patients/{id}\n" in text:
                ans = {"page_id": "patient_42", "purpose": "One patient's chart", "entity": "patient",
                       "kind": "detail", "confidence": 0.9}         # bad id -> must be rejected
            elif "Pattern: /schedule" in text:
                ans = {"page_id": "appt_list", "purpose": "Day schedule of appointments",
                       "entity": "Appointment", "kind": "list", "confidence": 0.8}
            else:
                return {"text": "not json at all", "ms": 5}           # parse failure -> heuristic
            return {"text": json.dumps(ans), "ms": 10}
        # planner: first answer is invalid, then pick the first listed candidate, stop after 6 calls
        n = sum(1 for p, _ in calls if p == "explore_plan")
        if n == 1:
            return {"text": '{"action": "c999", "reason": "made up"}', "ms": 7}
        if n > 6:
            return {"text": '{"action": "stop", "reason": "enough"}', "ms": 7}
        first = text.split("CANDIDATES")[1].splitlines()[1].split(" | ")[0]
        return {"text": json.dumps({"action": first, "reason": "next unseen section"}), "ms": 7}

    monkeypatch.setattr(nemotron, "chat", fake_chat)
    sm = run(site, tmp_path, creds, reader="nemotron", planner="nemotron")["site_map"]
    assert validate_site_map(sm) == []
    pages = by_id(sm)
    assert sm["stats"]["stop_reason"] == "planner_stop"
    assert sm["stats"]["nemotron_fallbacks"] >= 2
    assert pages["appt_list"]["entity"] == "Appointment" and pages["appt_list"]["read_by"] == "nemotron"
    detail = next(p for p in sm["pages"] if p["url_pattern"] == "/patients/{id}")
    assert detail["id"] == "patient_detail" and detail["entity"] == "Patient"
    assert {m for p, m in calls if p == "explore_plan"} == {policy.NemotronPlanner().model}
    assert {m for p, m in calls if p == "explore_read"} == {"nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"}


@pytest.mark.skipif(shutil.which("nat", path=os.path.dirname(sys.executable)) is None,
                    reason="NeMo Agent Toolkit not installed")
def test_runs_as_nemo_agent_toolkit_workflow(site, tmp_path, creds):
    cfg = tmp_path / "wf.yml"
    cfg.write_text("workflow:\n  _type: facade_explorer\n  reader: heuristic\n  planner: heuristic\n"
                   "  login: env\n  screenshots: false\n  page_budget: 10\n")
    env = dict(os.environ, FACADE_LOGIN_USER=creds["username"], FACADE_LOGIN_PASS=creds["password"])
    nat = os.path.join(os.path.dirname(sys.executable), "nat")
    out = subprocess.run([nat, "run", "--config_file", str(cfg), "--input", site.url + "/"],
                         capture_output=True, text=True, timeout=180, env=env,
                         cwd=Path(__file__).resolve().parent.parent)
    assert out.returncode == 0, out.stderr[-2000:]
    assert "patient_list" in out.stdout + out.stderr
