"""MCP over stdio, for AI apps that launch servers as a command (Claude Desktop, Cursor, ...).

    python -m serve.mcp_stdio ../shared/output/hackernews

Claude Desktop config (claude_desktop_config.json):
    {"mcpServers": {"facade": {"command": "<repo>/core/.venv/bin/python",
                               "args": ["-m", "serve.mcp_stdio", "<repo>/shared/output/hackernews"],
                               "cwd": "<repo>/core"}}}
"""
import json
import sys

from .data import load
from .mcp import MCPServer


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        raise SystemExit("usage: python -m serve.mcp_stdio <output folder>")
    state = load(argv[0])
    server = MCPServer(state, name="facade")
    print(f"facade MCP: {len(server.tools())} tools over {sum(len(v) for v in state['records'].values())} records ({state['source']})",
          file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        msgs = msg if isinstance(msg, list) else [msg]
        for m in msgs:
            res = server.handle(m)
            if res is not None:
                sys.stdout.write(json.dumps(res, ensure_ascii=False, default=str) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    main()
