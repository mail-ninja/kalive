"""MCP stdio for Grok/Claude mcp_servers.json. PYTHONPATH=cockpit/backend."""
from __future__ import annotations

import json
import sys

from app.mcp_routes import handle_rpc


def main() -> int:
    allow = False
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = str(msg.get("method") or "")
        if method.startswith("notifications/"):
            continue
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        out = handle_rpc(method, params, allow_mutate=allow, rid=msg.get("id"))
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
