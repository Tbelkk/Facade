"""Server agent: start the REST API + MCP server from the Operator's design, prove every route and tool works, keep serving.

    python -m serve.run ../shared/output/hackernews              # http://127.0.0.1:8000  (docs at /docs, MCP at /mcp)
    python -m serve.run ../shared/output/hackernews --port 8010
    python -m serve.run ../shared/output/hackernews --check-only # self-test and exit (no server)

Steps (each one is reported live to SpacetimeDB for the dashboard, and saved to <folder>/server.json):
  1. load the design + records (SpacetimeDB first, the folder's files as fallback)
  2. build the API: one route per operation, plus /docs (OpenAPI) and /mcp
  3. self-test every route with the Operator's own example request; the answer must match its example
  4. self-test the MCP server like an AI client would: initialize, tools/list, then call every tool
  5. go live
"""
import argparse
import json
import socket
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from ingest import nemotron  # noqa: F401  (loads core/.env)

from facade.events import emit

from .api import build_app
from .data import load


def _free_port(port):
    for p in range(port, port + 20):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return port


def _example_args(op):
    """The Operator's example request -> {param: value} (query string + path params)."""
    req = (op.get("example") or {}).get("request") or ""
    u = urlsplit(req)
    args = dict(parse_qsl(u.query))
    tpl, got = op["path"].strip("/").split("/"), u.path.strip("/").split("/")
    for t, g in zip(tpl, got):
        if t.startswith("{") and t.endswith("}"):
            args[t[1:-1]] = g
    return req, args


def self_test(app, state, report):
    from fastapi.testclient import TestClient
    client = TestClient(app)
    results = {"routes": [], "tools": []}
    for op in state["ops"]["operations"]:
        req, args = _example_args(op)
        row = {"method": op["method"], "path": op["path"], "name": op["name"], "request": req or op["path"]}
        if op.get("source") != "database" or op["method"] != "GET":
            row.update(ok=None, note="write endpoint: waits for the Writer")
            report("server_route", f"{op['method']} {op['path']} registered (write: waits for the Writer)", row)
            results["routes"].append(row)
            continue
        t0 = time.time()
        r = client.get(req or op["path"])
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        want = ((op.get("example") or {}).get("response") or {})
        got_total = body.get("total") if isinstance(body, dict) else None
        want_total = want.get("total") if isinstance(want, dict) else None
        ok = r.status_code == 200 and (want_total is None or got_total == want_total)
        row.update(ok=ok, status=r.status_code, total=got_total, expected=want_total, ms=round((time.time() - t0) * 1000, 1),
                   first=(body.get("items") or [{}])[0].get("title") if isinstance(body, dict) and body.get("items") else body.get("title") if isinstance(body, dict) else None)
        msg = f"{op['method']} {req or op['path']} → {r.status_code}" + (f", {got_total} results" if got_total is not None else "") + \
              ("" if ok else f" (expected {want_total})")
        report("server_route", msg, row, "info" if ok else "warn")
        results["routes"].append(row)

    def rpc(i, method, params=None):
        return client.post("/mcp", json={"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}).json()

    init = rpc(1, "initialize", {"protocolVersion": "2025-06-18", "clientInfo": {"name": "facade-selftest", "version": "1"}, "capabilities": {}})
    client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools = rpc(2, "tools/list").get("result", {}).get("tools", [])
    report("server_mcp", f"MCP server answered initialize ({init.get('result', {}).get('serverInfo', {}).get('name')}) and listed {len(tools)} tools",
           {"tools": [t["name"] for t in tools]})
    by_name = {o["name"]: o for o in state["ops"]["operations"]}
    for k, t in enumerate(tools):
        _, args = _example_args(by_name.get(t["name"], {"path": "", "name": t["name"]}))
        res = rpc(10 + k, "tools/call", {"name": t["name"], "arguments": args}).get("result", {})
        sc = res.get("structuredContent") or {}
        ok = not res.get("isError")
        row = {"name": t["name"], "args": args, "ok": ok, "total": sc.get("total"), "description": t["description"]}
        report("server_tool", f"MCP tool {t['name']}({', '.join(f'{a}={v}' for a, v in args.items())}) → " +
               (f"{sc.get('total')} results" if sc.get("total") is not None else "ok" if ok else "error"), row, "info" if ok else "warn")
        results["tools"].append(row)
    return results


def run(folder=None, port=8000, host="127.0.0.1", check_only=False, live=True, log=print, site=None):
    """Serve from an output folder (SpacetimeDB preferred, files as fallback), or, with site= and no folder,
    straight from SpacetimeDB: a saved API comes back without its folder or a new run (see store.sites)."""
    folder = Path(folder) if folder else None
    t0 = time.time()
    if folder is not None:
        state = load(folder)
    else:
        from .data import from_spacetime
        state = from_spacetime(site) if site else None
        if not state:
            raise SystemExit(f"No saved API for {site} in SpacetimeDB. Run the full workflow for it first.")
    site = state["site"]
    lw = None
    if live:
        try:
            from store.live import Live
            lw = Live(site, actor="server")
            lw.job_start("serve")
        except Exception:
            lw = None

    def report(kind, message, data=None, level="info"):
        log(f"  {message}")
        if lw:
            lw.event(kind, message, data or {}, level)
        d = data or {}
        if kind == "server_start":
            emit({"stage": "server", "kind": "start", "source": d.get("source"), "records": d.get("records")})
        elif kind == "server_built":
            emit({"stage": "server", "kind": "built", "routes": [r.split(" ", 1) for r in d.get("routes", [])], "tools": d.get("tools", [])})
        elif kind == "server_route":
            emit({"stage": "server", "kind": "route", **d})
        elif kind == "server_tool":
            emit({"stage": "server", "kind": "tool", **d})
        elif kind in ("server_live", "server_checked"):
            emit({"stage": "server", "kind": "live", **d})

    n_rec = sum(len(v) for v in state["records"].values())
    ops = state["ops"]["operations"]
    report("server_start", f"Loaded the API design ({len(ops)} endpoints) and {n_rec:,} records from {state['source']}",
           {"source": state["source"], "endpoints": len(ops), "records": n_rec})
    app = build_app(state)
    report("server_built", f"Built the REST API ({len(ops)} routes + /docs) and the MCP server ({len(app.state.mcp.tools())} tools)",
           {"routes": [f"{o['method']} {o['path']}" for o in ops], "tools": [t["name"] for t in app.state.mcp.tools()]})
    results = self_test(app, state, report)
    port = _free_port(port)
    base = f"http://{host}:{port}"
    passed = sum(1 for r in results["routes"] if r["ok"]) + sum(1 for r in results["tools"] if r["ok"])
    tested = sum(1 for r in results["routes"] if r["ok"] is not None) + len(results["tools"])
    summary = {"site": site, "api": base, "docs": base + "/docs", "mcp": base + "/mcp", "source": state["source"],
               "records": n_rec, "passed": passed, "tested": tested, "seconds": round(time.time() - t0, 1), **results}
    if folder is not None:
        (folder / "server.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    report("server_live" if not check_only else "server_checked",
           f"{'Live' if not check_only else 'Checked'}: API {base}  ·  docs {base}/docs  ·  MCP {base}/mcp  ·  self-test {passed}/{tested} passed",
           {k: summary[k] for k in ("api", "docs", "mcp", "passed", "tested")})
    if lw:
        lw.job_update(tested, tested, "done")
        lw.close()
    if folder is not None:
        log(f"\nClaude Desktop / Cursor (stdio):  python -m serve.mcp_stdio {folder}")
    if check_only:
        return summary
    import uvicorn
    log(f"Serving {base}  (Ctrl+C to stop)\n")
    uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning")).run()   # also works in a thread
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="RESTore Server: run the generated API + MCP server")
    ap.add_argument("folder", nargs="?", help="shared/output/<site> (or a run folder with operations.json)")
    ap.add_argument("--site", help="serve a saved API straight from SpacetimeDB by its site URL (no folder needed)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--check-only", action="store_true", help="self-test and exit without serving")
    ap.add_argument("--no-live", action="store_true", help="don't report events to SpacetimeDB")
    a = ap.parse_args(argv)
    if not a.folder and not a.site:
        ap.error("give an output folder, or --site <url> to serve a saved API from SpacetimeDB")
    print(f"RESTore Server → {a.folder or a.site}")
    run(a.folder, port=a.port, host=a.host, check_only=a.check_only, live=not a.no_live, site=a.site)


if __name__ == "__main__":
    main()
