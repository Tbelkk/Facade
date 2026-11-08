"""Saved sites: what's already been explored, so the Console can open it instead of running the agents again.

    GET /sites                 -> {"sites": [summary, ...]}            every site with a finished API, newest first
    GET /sites/lookup?url=...  -> {"found": true,  "site": summary}     any page of a saved site finds it
                               -> {"found": false, "base": "https://..."}

summary = {"site", "saved_at", "entities", "endpoints", "operations", "designed_by", "has_docs",
           "records": {Entity: n}, "total_records"}

POST /runs uses the same lookup: a saved site is served from SpacetimeDB right away (no exploring)
unless the request says {"reuse": false}. See core/store/sites.py.
"""
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

CORE = Path(__file__).resolve().parent.parent / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

router = APIRouter()


@router.get("/sites")
def saved_sites() -> Dict[str, Any]:
    """Every site with a finished, saved API."""
    from store import sites
    found = sites.list_saved()
    if found is None:
        raise HTTPException(503, "Can't reach SpacetimeDB. Check SPACETIME_HOST / SPACETIME_DB in core/.env.")
    return {"sites": found}


@router.get("/sites/lookup")
def lookup_site(url: str) -> Dict[str, Any]:
    """Is this site already saved? Matches on the base address, so any page of the site works."""
    from store import sites
    base = sites.base_address(url)
    if not base:
        raise HTTPException(400, "That isn't a web address. It should start with http:// or https://")
    try:
        s = sites.lookup(url, strict=True)
    except sites.Unreachable as exc:
        raise HTTPException(503, str(exc))
    return {"found": True, "site": s} if s else {"found": False, "base": base}
