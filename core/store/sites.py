"""Which sites already have a finished, saved API in SpacetimeDB, so a run doesn't have to start over.

    from store import sites
    sites.lookup("https://news.ycombinator.com/news?p=2")   # -> summary dict, or None
    sites.list_saved()                                      # -> [summary, ...]

    python -m store.sites                                   # print every saved site
    python -m store.sites https://news.ycombinator.com      # look one up

A site counts as saved only when its row in the `site` table has an API design (ops_json with at
least one operation), which store.load_run writes at the end of a successful run. Half-finished or
crashed runs never show up here.

Sites are matched by their base address (scheme + host + port), so any page of a site finds it:
    https://News.YCombinator.com/news?p=2  ->  https://news.ycombinator.com
Knows nothing about any specific website.
"""

import json
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from store import spacetime as db

_DEFAULT_PORTS = {"http": 80, "https": 443}


def base_address(url: str) -> str:
    """'https://News.example.com:443/a/b?x=1' -> 'https://news.example.com'. '' if it isn't a web address."""
    raw = (url or "").strip()
    if raw and "://" not in raw:
        raw = "https://" + raw
    try:
        u = urlsplit(raw)
        port = u.port
    except ValueError:
        return ""
    scheme = (u.scheme or "").lower()
    host = (u.hostname or "").lower()
    if scheme not in ("http", "https") or not host:
        return ""
    if not re.fullmatch(r"[a-z0-9.\-]+|[0-9a-f:.]*:[0-9a-f:.]*", host):
        return ""  # spaces or odd characters (e.g. "not a url"); single-word intranet names like http://clinicpro are fine
    if ":" in host:  # IPv6
        host = f"[{host}]"
    if port and port != _DEFAULT_PORTS.get(scheme):
        host = f"{host}:{port}"
    return f"{scheme}://{host}"


def _loads(text: str, default):
    try:
        return json.loads(text) if text else default
    except ValueError:
        return default


def _record_counts(site: str) -> Dict[str, int]:
    """{entity: number of records} for one site. Asks for one small column first; falls back to whole rows."""
    rows = db.sql(f"SELECT entity FROM record WHERE site = {db.quote(site)}")
    if rows is None:
        rows = db.sql(f"SELECT * FROM record WHERE site = {db.quote(site)}") or []
    counts: Dict[str, int] = {}
    for r in rows:
        e = r.get("entity")
        if e:
            counts[e] = counts.get(e, 0) + 1
    return counts


def _summary(row: Dict[str, Any], with_counts: bool = True) -> Optional[Dict[str, Any]]:
    """A `site` row -> what the API and dashboard need to show. None if it has no finished API."""
    ops = _loads(row.get("ops_json"), {})
    operations = ops.get("operations") if isinstance(ops, dict) else None
    if not operations:
        return None
    model = _loads(row.get("model_json"), {})
    entities = [e.get("name") for e in (model.get("entities") or []) if isinstance(e, dict) and e.get("name")]
    out = {
        "site": row.get("url"),
        "saved_at": row.get("updated_at"),
        "entities": entities,
        "endpoints": len(operations),
        "operations": [o.get("name") or f"{o.get('method', '')} {o.get('path', '')}".strip() for o in operations],
        "designed_by": (ops.get("designed_by") or {}).get("by") if isinstance(ops.get("designed_by"), dict)
        else ops.get("designed_by"),
        "has_docs": bool(row.get("docs_md")),
    }
    if with_counts:
        counts = _record_counts(out["site"])
        out["records"] = counts
        out["total_records"] = sum(counts.values())
    return out


def _site_rows() -> Optional[List[Dict[str, Any]]]:
    return db.sql("SELECT * FROM site")


def list_saved(with_counts: bool = True) -> Optional[List[Dict[str, Any]]]:
    """Every site with a finished API, newest first. None if SpacetimeDB can't be reached."""
    rows = _site_rows()
    if rows is None:
        return None
    saved = [s for s in (_summary(r, with_counts) for r in rows) if s]
    saved.sort(key=lambda s: str(s.get("saved_at") or ""), reverse=True)
    return saved


class Unreachable(RuntimeError):
    """SpacetimeDB couldn't be reached, so we can't tell whether the site is saved."""


def lookup(url: str, with_counts: bool = True, strict: bool = False) -> Optional[Dict[str, Any]]:
    """The saved API for the site this URL belongs to, or None (not saved, or not a web address).
    If SpacetimeDB can't be reached: None, or raises Unreachable when strict=True."""
    want = base_address(url)
    if not want:
        return None
    rows = _site_rows()
    if rows is None:
        if strict:
            raise Unreachable("Can't reach SpacetimeDB. Check SPACETIME_HOST / SPACETIME_DB in core/.env.")
        return None
    for r in rows:
        if base_address(r.get("url") or "") == want:
            s = _summary(r, with_counts)
            if s:
                return s
    return None


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args:
        for url in args:
            s = lookup(url)
            print(f"\n{url}  ->  {base_address(url) or '(not a web address)'}")
            if s:
                print(f"  SAVED  {s['site']}  saved {s['saved_at']}")
                print(f"  {s['endpoints']} endpoints, {s['total_records']:,} records {s['records']}")
            else:
                print("  not saved (a run would explore it from scratch)")
        return
    saved = list_saved()
    if saved is None:
        print("Can't reach SpacetimeDB (check SPACETIME_HOST / SPACETIME_DB in core/.env).")
        return
    print(f"{len(saved)} saved site(s) in {db.HOST} / {db.DB}:")
    for s in saved:
        print(f"  {s['site']:40}  {s['endpoints']:>2} endpoints  {s['total_records']:>6,} records  saved {s['saved_at']}")


if __name__ == "__main__":
    main()
