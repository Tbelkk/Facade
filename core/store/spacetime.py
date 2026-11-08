"""Facade store client: the one way Python code talks to SpacetimeDB.

Used by the Explorer (Daniel), the Operator (Tyler), the API, and the mock loader.
Knows nothing about any specific website: it just calls reducers and runs SQL.

Usage:
    from store import spacetime as db

    db.call("log_event", "http://example.com", "explorer", "info", "Opened home page", {"ms": 812})
    rows = db.sql("SELECT * FROM record WHERE site = 'http://example.com'")

Settings (environment variables or core/.env):
    SPACETIME_HOST   default https://maincloud.spacetimedb.com
    SPACETIME_DB     default facade
    SPACETIME_TOKEN  optional; get it with `spacetime login show --token`

Rule from the plan: agents never block on the database. Every call has a short
timeout, and failures are logged and returned as False / None instead of raising
(pass strict=True if you want an exception).
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

try:  # optional: load core/.env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

log = logging.getLogger("facade.store")

HOST = os.getenv("SPACETIME_HOST", "https://maincloud.spacetimedb.com").rstrip("/")
DB = os.getenv("SPACETIME_DB", "facade")
TOKEN = os.getenv("SPACETIME_TOKEN", "").strip()
TIMEOUT = float(os.getenv("SPACETIME_TIMEOUT", "5"))

_session = requests.Session()


class SpacetimeError(RuntimeError):
    pass


def _headers(content_type: str) -> Dict[str, str]:
    headers = {"Content-Type": content_type}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    return headers


def _to_arg(value: Any) -> Any:
    """Dicts and lists become JSON strings (the tables store JSON as text); None becomes ""."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def call(reducer: str, *args: Any, strict: bool = False) -> bool:
    """Call a reducer with positional args, in the order the reducer declares them.

    Returns True on success, False on failure (or raises SpacetimeError if strict=True).
    """
    url = f"{HOST}/v1/database/{DB}/call/{reducer}"
    body = json.dumps([_to_arg(a) for a in args], ensure_ascii=False)
    try:
        resp = _session.post(url, data=body.encode("utf-8"), headers=_headers("application/json"), timeout=TIMEOUT)
    except requests.RequestException as exc:
        return _fail(f"{reducer}: could not reach SpacetimeDB ({exc})", strict)
    if resp.status_code >= 300:
        return _fail(f"{reducer}: HTTP {resp.status_code}: {resp.text.strip()[:300]}", strict)
    return True


def sql(query: str, strict: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Run one SQL query and return its rows as dicts (column name -> value).

    Returns None on failure (or raises SpacetimeError if strict=True).
    For several statements separated by ';', use sql_many().
    """
    results = sql_many(query, strict=strict)
    if results is None:
        return None
    return results[-1] if results else []


def sql_many(query: str, strict: bool = False) -> Optional[List[List[Dict[str, Any]]]]:
    url = f"{HOST}/v1/database/{DB}/sql"
    try:
        resp = _session.post(url, data=query.encode("utf-8"), headers=_headers("text/plain"), timeout=TIMEOUT)
    except requests.RequestException as exc:
        _fail(f"sql: could not reach SpacetimeDB ({exc})", strict)
        return None
    if resp.status_code >= 300:
        _fail(f"sql: HTTP {resp.status_code}: {resp.text.strip()[:300]}", strict)
        return None
    try:
        statements = resp.json()
    except ValueError:
        _fail("sql: response was not JSON", strict)
        return None
    return [_rows_to_dicts(stmt) for stmt in statements]


def quote(value: str) -> str:
    """Quote a string for use inside SQL: quote("O'Brien") -> 'O''Brien'."""
    return "'" + str(value).replace("'", "''") + "'"


def record_hash(data: Dict[str, Any]) -> str:
    """Content hash for a record's data. Same data -> same hash, so unchanged records are skipped."""
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ---------- Convenience wrappers (same argument order as the reducers) ----------

def save_site(url: str, site_map: Any, model: Any, operations: Any, docs_md: str = "") -> bool:
    return call("save_site", url, site_map, model, operations, docs_md)


def upsert_schema(site: str, name: str, fields: Any, rules: Any) -> bool:
    return call("upsert_schema", site, name, fields, rules)


def upsert_record(site: str, entity: str, legacy_id: str, data: Dict[str, Any]) -> bool:
    return call("upsert_record", site, entity, str(legacy_id), data, record_hash(data))


def request_op(request_key: str, site: str, operation: str, inputs: Dict[str, Any]) -> bool:
    return call("request_op", request_key, site, operation, inputs)


def claim_op(op_id: int) -> bool:
    return call("claim_op", int(op_id))


def finish_op(op_id: int, ok: bool, result: Any = None, error: str = "") -> bool:
    return call("finish_op", int(op_id), bool(ok), result, error)


def start_job(job_key: str, site: str, kind: str, entity: str = "", total: int = 0) -> bool:
    return call("start_job", job_key, site, kind, entity, int(total))


def update_job(job_key: str, done: int, total: int, status: str = "running") -> bool:
    return call("update_job", job_key, int(done), int(total), status)


def log_event(site: str, actor: str, message: str, data: Any = None, level: str = "info") -> bool:
    return call("log_event", site, actor, level, message, data or {})


def clear_site(site: str) -> bool:
    return call("clear_site", site)


# ---------- Internals ----------

def _fail(message: str, strict: bool) -> bool:
    if strict:
        raise SpacetimeError(message)
    log.warning(message)
    return False


def _rows_to_dicts(statement: Dict[str, Any]) -> List[Dict[str, Any]]:
    elements = statement.get("schema", {}).get("elements", [])
    names = []
    for i, el in enumerate(elements):
        name = el.get("name")
        if isinstance(name, dict):
            name = name.get("some")
        names.append(name or f"col{i}")
    return [
        {names[i]: _plain(row[i], elements[i].get("algebraic_type")) for i in range(min(len(names), len(row)))}
        for row in statement.get("rows", [])
    ]


_TIMESTAMP_FIELD = "__timestamp_micros_since_unix_epoch__"


def _plain(value: Any, algebraic_type: Any) -> Any:
    """Turn SpacetimeDB's JSON encoding into plain Python values (timestamps -> ISO strings)."""
    micros = None
    if isinstance(value, dict) and _TIMESTAMP_FIELD in value:
        micros = value[_TIMESTAMP_FIELD]
    elif _is_timestamp_type(algebraic_type) and isinstance(value, list) and len(value) == 1:
        micros = value[0]
    if micros is not None:
        return datetime.fromtimestamp(int(micros) / 1_000_000, tz=timezone.utc).isoformat()
    return value


def _is_timestamp_type(algebraic_type: Any) -> bool:
    try:
        elements = algebraic_type["Product"]["elements"]
        name = elements[0]["name"]
        name = name.get("some") if isinstance(name, dict) else name
        return len(elements) == 1 and name == _TIMESTAMP_FIELD
    except (KeyError, IndexError, TypeError):
        return False
