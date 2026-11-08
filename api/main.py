"""Facade API.

Run from the repo root (the Facade folder):
    uvicorn api.main:app --reload --port 8000

Then open http://localhost:8000/docs to try the endpoints.

Endpoints so far:
    GET  /health   -> {"ok": true}           (is the API up?)
    POST /check    -> URL fit check           (used by the Console's start panel)

Settings (environment variables):
    CONSOLE_ORIGINS  comma-separated web addresses allowed to call this API from a browser
                     (default: the Vite dev server, http://localhost:5173 and http://127.0.0.1:5173)
"""

import logging
import os
from typing import Any, Dict, List, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.fitcheck import check_url

log = logging.getLogger("facade.api")

app = FastAPI(title="Facade API", version="0.1.0",
              description="Legacy website -> database + API + MCP, built by Nemotron agents.")

origins = [o.strip() for o in os.getenv(
    "CONSOLE_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CheckRequest(BaseModel):
    url: str


class CheckResponse(BaseModel):
    verdict: Literal["good_fit", "probably_not", "blocked"]
    reasons: List[str]
    checked_url: str
    signals: Dict[str, Any] = {}


@app.get("/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


# A plain `def` (not async) so FastAPI runs the network fetch in a worker thread
# and the server stays responsive while a slow site is being checked.
@app.post("/check", response_model=CheckResponse)
def check(body: CheckRequest) -> Dict[str, Any]:
    """Is this URL a good fit for Facade? Opens the first page only, never logs in, never submits forms."""
    try:
        return check_url(body.url)
    except Exception as exc:  # never hand the Console a 500: always a verdict it can show
        log.exception("fit check crashed for %s", body.url)
        return {"verdict": "probably_not",
                "reasons": [f"Couldn't analyze this page ({type(exc).__name__}). You can try again or continue "
                            "anyway."],
                "checked_url": body.url, "signals": {}}
