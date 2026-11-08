"""Start the whole RESTore workflow from the Console and follow it live.

    POST /runs                 {"url": "https://...", "pause": 1, "pages": 200, "minutes": 30}  -> {"id": "...", "status": "running"}
                               {"url": ..., "reuse": false}  explores again even if the site is already saved
    GET  /runs/{id}/events?after=N                      -> {"events": [...], "next": M, "status": "running|serving|failed"}
    GET  /runs/current                                  -> the run in progress, if any

The run is core/facade/run.py (explore -> design the API -> publish -> load into SpacetimeDB -> start the
API + MCP server), started in a background thread. If the site already has a finished API saved in SpacetimeDB
(core/store/sites.py), the run skips straight to serving that saved API: no exploring, no Nemotron calls.
The response then says {"reused": true, "saved": {...}}. Send "reuse": false to explore it again anyway. Every agent reports through core/facade/events.py; this
module keeps those events per run so the Console can poll them. One run at a time.
"""
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

CORE = Path(__file__).resolve().parent.parent / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))   # the agents live in core/ (explore, operator_agent, store, serve, facade)

router = APIRouter()
RUNS: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()
SERVE_PORT = 8001   # this API is on 8000; the generated API + MCP server goes next to it


class RunRequest(BaseModel):
    url: str
    # optional run options; each maps to a flag of python -m facade.run (the dashboard sends only url)
    pause: Optional[float] = None     # --pause    seconds between page loads
    pages: Optional[int] = None       # --pages    stop after this many pages
    minutes: Optional[float] = None   # --minutes  stop after this long
    full: bool = False                # --full     page through every list to the end
    headed: bool = False              # --headed   show the browser window
    live: bool = True                 # --no-live when off
    reuse: bool = True                # serve the saved API if this site was already explored; false = explore again


def _worker(run_id, req):
    url = req.url
    from facade import events
    from facade import run as pipeline
    run = RUNS[run_id]

    def collect(evt):
        with _lock:
            run["events"].append(evt)
            if evt.get("stage") == "server" and evt.get("kind") == "live":
                run["status"] = "serving"
                run["server"] = {k: evt.get(k) for k in ("api", "docs", "mcp")}

    stop = events.listen(collect)
    try:
        pipeline.run(url, live=req.live, serve=True, port=SERVE_PORT, full=req.full, headed=req.headed,
                     pause=req.pause, minutes=req.minutes, pages=req.pages)   # blocks while the generated server runs
    except BaseException as exc:  # SystemExit from the agents too (e.g. no records): report it, don't crash
        with _lock:
            run["status"] = "failed"
            run["error"] = str(exc) or type(exc).__name__
            run["events"].append({"stage": "run", "kind": "error", "message": run["error"]})
        traceback.print_exc()
    finally:
        stop()


def _reuse_worker(run_id, req, saved):
    """The site is already saved: replay its saved state to the dashboard, then serve its API from SpacetimeDB."""
    import json
    from facade import events
    from facade.events import emit
    from serve.run import run as serve_run
    from store import spacetime as db
    run = RUNS[run_id]

    def collect(evt):
        with _lock:
            run["events"].append(evt)
            if evt.get("stage") == "server" and evt.get("kind") == "live":
                run["status"] = "serving"
                run["server"] = {k: evt.get(k) for k in ("api", "docs", "mcp")}

    stop = events.listen(collect)
    try:
        site = saved["site"]
        emit({"stage": "run", "kind": "start", "site": site, "reused": True, "saved_at": saved.get("saved_at")})
        rows = db.sql(f"SELECT * FROM site WHERE url = {db.quote(site)}") or []
        row = rows[0] if rows else {}
        try:
            model = json.loads(row.get("model_json") or "{}")
            ops = json.loads(row.get("ops_json") or "{}")
        except ValueError:
            model, ops = {}, {}
        counts = saved.get("records") or {}
        ents = [{"name": e.get("name"), "record_count": counts.get(e.get("name"), e.get("record_count", 0)),
                 "fields": [{"name": f.get("name"), "type": f.get("type")} for f in e.get("fields", [])]}
                for e in model.get("entities", []) if isinstance(e, dict)]
        emit({"stage": "model", "entities": ents})
        if ops.get("operations"):
            emit({"stage": "operator", "kind": "done", "operations": ops["operations"],
                  "designed_by": ops.get("designed_by") or {}, "reused": True})
        emit({"stage": "database", "target": "SpacetimeDB", "reused": True,
              "tables": [{"name": "record", "done": saved.get("total_records", 0), "total": saved.get("total_records", 0),
                          "note": f"saved {saved.get('saved_at') or ''}".strip()}]})
        serve_run(site=site, port=SERVE_PORT, live=req.live)   # blocks while the server runs
    except BaseException as exc:
        with _lock:
            run["status"] = "failed"
            run["error"] = str(exc) or type(exc).__name__
            run["events"].append({"stage": "run", "kind": "error", "message": run["error"]})
        traceback.print_exc()
    finally:
        stop()


@router.post("/runs")
def start_run(body: RunRequest) -> Dict[str, Any]:
    with _lock:
        busy = next((r for r in RUNS.values() if r["status"] == "running"), None)
        if busy:
            raise HTTPException(409, f"A run is already in progress for {busy['url']}.")
        run_id = uuid.uuid4().hex[:10]
        RUNS[run_id] = {"id": run_id, "url": body.url, "status": "running", "events": [], "started": time.time(),
                        "error": None, "server": None}
    saved = None
    if body.reuse:
        try:
            from store import sites
            saved = sites.lookup(body.url)   # None if not saved (or the database can't be reached): explore as usual
        except Exception:
            saved = None
    if saved:
        with _lock:
            RUNS[run_id]["reused"] = True
            RUNS[run_id]["saved"] = saved
        threading.Thread(target=_reuse_worker, args=(run_id, body, saved), daemon=True,
                         name=f"facade-reuse-{run_id}").start()
        return {"id": run_id, "status": "running", "reused": True, "saved": saved}
    threading.Thread(target=_worker, args=(run_id, body), daemon=True, name=f"facade-run-{run_id}").start()
    return {"id": run_id, "status": "running", "reused": False}


@router.get("/runs/current")
def current_run() -> Dict[str, Any]:
    with _lock:
        live = [r for r in RUNS.values() if r["status"] in ("running", "serving")]
        r = max(live, key=lambda x: x["started"]) if live else None
        return {"run": {k: r[k] for k in ("id", "url", "status", "server")} if r else None}


@router.get("/runs/{run_id}/events")
def run_events(run_id: str, after: int = 0) -> Dict[str, Any]:
    with _lock:
        run = RUNS.get(run_id)
        if not run:
            raise HTTPException(404, "No such run.")
        evs = run["events"][after:]
        return {"events": evs, "next": after + len(evs), "status": run["status"], "error": run["error"],
                "server": run["server"]}
