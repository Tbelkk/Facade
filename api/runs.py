"""Start the whole Facade workflow from the Console and follow it live.

    POST /runs                 {"url": "https://...", "pause": 1, "pages": 200, "minutes": 30}  -> {"id": "...", "status": "running"}
    GET  /runs/{id}/events?after=N                      -> {"events": [...], "next": M, "status": "running|serving|failed"}
    GET  /runs/current                                  -> the run in progress, if any

The run is core/facade/run.py (explore -> design the API -> publish -> load into SpacetimeDB -> start the
API + MCP server), started in a background thread. Every agent reports through core/facade/events.py; this
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
    # the dashboard's Settings drawer (web/src/lib/settings.js); each maps to a flag of python -m facade.run
    pause: Optional[float] = None     # --pause    seconds between page loads
    pages: Optional[int] = None       # --pages    stop after this many pages
    minutes: Optional[float] = None   # --minutes  stop after this long
    full: bool = False                # --full     page through every list to the end
    headed: bool = False              # --headed   show the browser window
    live: bool = True                 # --no-live when off


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


@router.post("/runs")
def start_run(body: RunRequest) -> Dict[str, Any]:
    with _lock:
        busy = next((r for r in RUNS.values() if r["status"] == "running"), None)
        if busy:
            raise HTTPException(409, f"A run is already in progress for {busy['url']}.")
        run_id = uuid.uuid4().hex[:10]
        RUNS[run_id] = {"id": run_id, "url": body.url, "status": "running", "events": [], "started": time.time(),
                        "error": None, "server": None}
    threading.Thread(target=_worker, args=(run_id, body), daemon=True, name=f"facade-run-{run_id}").start()
    return {"id": run_id, "status": "running"}


def agent_models() -> Dict[str, Any]:
    """The model behind each agent, from core/.env (MODEL_EXPLORER / MODEL_OPERATOR / ...), for the dashboard."""
    from ingest import nemotron as N
    out = {}
    for agent, purpose in (("explorer", "extract_page"), ("split", "split_column"), ("operator", "operator_design")):
        model, base = N.route(purpose, N.MODEL_AGENT)
        out[agent] = {"model": model, "hosted": "integrate.api.nvidia.com" in base}
    out["parser"] = {"model": N.MODEL_PARSER, "hosted": "integrate.api.nvidia.com" in N.BASE_URL}
    return out


@router.get("/models")
def models() -> Dict[str, Any]:
    return agent_models()


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
