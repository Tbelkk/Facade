"""Where the Explorer's results go.

JsonSink       always on: writes the run folder (site_map.json, pages/*.json, shots/, events.jsonl)
SpacetimeSink  optional: also calls SpacetimeDB reducers over HTTP (format 7.5). Short timeouts;
               failures are counted and logged, never raised. The agent never blocks on the database.

Reducer argument order below is our best reading of plan section 7.5. If the SpacetimeDB module
uses different arguments, change only `_REDUCER_ARGS`.
"""
import json
import os
import time
from pathlib import Path


class JsonSink:
    def __init__(self, run_dir):
        self.run_dir = Path(run_dir)
        (self.run_dir / "pages").mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"
        self.events = []

    def log_event(self, message, level="info", **data):
        ev = {"ts": time.time(), "actor": "explorer", "level": level, "message": message, "data": data}
        self.events.append(ev)
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev

    def save_page(self, page_id, model):
        (self.run_dir / "pages" / f"{page_id}.json").write_text(
            json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")

    def save_site(self, site_map):
        p = self.run_dir / "site_map.json"
        p.write_text(json.dumps(site_map, indent=2, ensure_ascii=False), encoding="utf-8")
        return p

    def job(self, status, done, total):
        self.log_event(f"job {status}: {done}/{total}", kind="job", status=status, done=done, total=total)


_REDUCER_ARGS = {
    "log_event": lambda ev: [ev["actor"], ev["level"], ev["message"], json.dumps(ev["data"])],
    "save_site": lambda sm: [sm["site"], json.dumps(sm), "", "", ""],
}


class SpacetimeSink(JsonSink):
    """JsonSink + mirror to SpacetimeDB. Configure with SPACETIME_HOST / SPACETIME_DB / SPACETIME_TOKEN."""

    def __init__(self, run_dir, host=None, db=None, token=None, timeout=2.0):
        super().__init__(run_dir)
        self.host = (host or os.getenv("SPACETIME_HOST", "https://maincloud.spacetimedb.com")).rstrip("/")
        self.db = db or os.getenv("SPACETIME_DB", "facade")
        self.token = token or os.getenv("SPACETIME_TOKEN", "")
        self.timeout = timeout
        self.failures = 0
        self.job_id = None

    def _call(self, reducer, args):
        import requests

        if self.failures >= 5:  # database looks down: stop trying, keep exploring
            return False
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            r = requests.post(f"{self.host}/v1/database/{self.db}/call/{reducer}", data=json.dumps(args),
                              headers=headers, timeout=self.timeout)
            if r.status_code >= 300:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
            return True
        except Exception as e:
            self.failures += 1
            super().log_event(f"SpacetimeDB {reducer} failed: {e}", level="warn", reducer=reducer)
            return False

    def log_event(self, message, level="info", **data):
        ev = super().log_event(message, level, **data)
        self._call("log_event", _REDUCER_ARGS["log_event"](ev))
        return ev

    def save_site(self, site_map):
        p = super().save_site(site_map)
        self._call("save_site", _REDUCER_ARGS["save_site"](site_map))
        return p


def make(kind, run_dir):
    return SpacetimeSink(run_dir) if kind == "spacetime" else JsonSink(run_dir)
