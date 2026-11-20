"""Tiny MCP stdio fixture server used by tests (not a test module itself)."""
import json
import sys


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        method, rid = msg.get("method"), msg.get("id")
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {},
                      "serverInfo": {"name": "fixture", "version": "0.0.1"}}
        elif method == "tools/list":
            result = {"tools": [{"name": "echo", "description": "Echo args",
                                 "inputSchema": {"type": "object"}}]}
        elif method == "tools/call":
            args = (msg.get("params") or {}).get("arguments", {})
            result = {"content": [{"type": "text", "text": f"echo:{args}"}]}
        else:
            result = {}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
