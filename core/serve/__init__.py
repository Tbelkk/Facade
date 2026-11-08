"""RESTore Server: turns the Operator's API design (operations.json) into a running REST API and MCP server.

    python -m serve.run ../shared/output/hackernews            # start both, self-test them, keep serving
    python -m serve.mcp_stdio ../shared/output/hackernews      # MCP over stdio (for Claude Desktop & co.)

data.py      loads the design + records (SpacetimeDB first, the output folder as fallback)
api.py       REST API generated from operations.json (FastAPI), plus the MCP endpoint at /mcp
mcp.py       MCP protocol (JSON-RPC): tools generated from the same operations
run.py       start + self-test (every endpoint and every tool) + report events to the dashboard
"""
