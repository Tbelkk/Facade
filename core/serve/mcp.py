"""MCP (Model Context Protocol) server: every read operation in operations.json becomes a tool.

Protocol: JSON-RPC 2.0 — initialize, tools/list, tools/call, ping (no SDK needed, works on Python 3.9).
Transports: Streamable HTTP (POST /mcp, JSON responses; see api.py) and stdio (serve/mcp_stdio.py).
The tool's name, description and parameters come straight from the Operator's design.
"""
import json

from operator_agent import query

PROTOCOL = "2025-06-18"
JSON_TYPE = {"integer": "integer", "number": "number", "float": "number", "int": "integer", "bool": "boolean",
             "boolean": "boolean"}


def tool_for(op, entities=None):
    """operations.json entry -> MCP tool definition."""
    props, required = {}, []
    for i in op.get("inputs", []):
        p = {"type": JSON_TYPE.get(i.get("type"), "string")}
        desc = {"gte": f"minimum {i.get('field')}", "lte": f"maximum {i.get('field')}",
                "contains": f"text contained in {i.get('field')}", "eq": f"exact {i.get('field')}",
                "search": f"words to search for in {', '.join(i.get('fields', []))}", "limit": "max results (default 50)",
                "offset": "skip this many results", "sort": "field to sort by; prefix with - for descending"}.get(i.get("match"))
        if i.get("in") == "path":
            desc = f"the {op.get('entity', 'record')}'s id"
        if desc:
            p["description"] = desc
        if i.get("values"):
            p["enum"] = i["values"]
        props[i["name"]] = p
        if i.get("required") or i.get("in") == "path":
            required.append(i["name"])
    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    desc = op.get("summary") or op["name"].replace("_", " ")
    e = (entities or {}).get(op.get("entity")) or {}
    if e.get("fields"):   # tell the calling agent what each record holds
        fields = ", ".join(f["name"] + (f" ({f['description']})" if f.get("description") else "") for f in e["fields"][:15])
        desc += f". Each {op.get('entity')}" + (f" ({e['description'].rstrip('.')})" if e.get("description") else "") + f" has: {fields}."
    return {"name": op["name"], "description": desc[:1000], "inputSchema": schema}


class MCPServer:
    def __init__(self, state, name="facade"):
        self.state = state          # dict from serve.data.load (ops, records, site); can be swapped on reload
        self.name = name

    @property
    def read_ops(self):
        return [o for o in self.state["ops"]["operations"] if o.get("source") == "database" and o.get("method") == "GET"]

    def tools(self):
        return [tool_for(o, self.state["ops"].get("entities")) for o in self.read_ops]

    def call(self, name, args):
        op = next((o for o in self.read_ops if o["name"] == name), None)
        if not op:
            return {"content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True}
        params = {k: v for k, v in (args or {}).items() if v not in (None, "")}
        result = query.run(op, params, self.state["records"])
        is_err = isinstance(result, dict) and result.get("error") is not None
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
                "structuredContent": result if isinstance(result, dict) else {"result": result}, "isError": is_err}

    def handle(self, msg):
        """One JSON-RPC message -> response dict, or None for notifications."""
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None:          # notification (e.g. notifications/initialized): no response
            return None
        try:
            if method == "initialize":
                result = {"protocolVersion": params.get("protocolVersion") or PROTOCOL,
                          "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": self.name, "version": "1.0"},
                          "instructions": f"Read-only tools over data extracted from {self.state.get('site')} by RESTore."}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": self.tools()}
            elif method == "tools/call":
                result = self.call(params.get("name"), params.get("arguments"))
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        except Exception as e:  # never crash the server on one bad call
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)[:300]}}
