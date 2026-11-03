"""A scoped MCP client: actual JSON-RPC handshake + tool call over stdio."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
from .documents import MCP_MODEL_TOOL_DEFS

MCP_TOOL_NAMES = {t["name"] for t in MCP_MODEL_TOOL_DEFS}


class MCPClient:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def call(self, tool_name: str, args: dict, session_id: str) -> dict:
        if tool_name not in MCP_TOOL_NAMES:
            return {"error": "Tool not on MCP allowlist"}
        # Never accept a session_id from the language model; the host always overrides.
        clean_args = {k: v for k, v in args.items() if k != "session_id"}
        clean_args["session_id"] = session_id
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "docpilot-agent", "version": "0.1.0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool_name, "arguments": clean_args}}
        ]
        request_data = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in requests)
        env = dict(os.environ)
        env["DOCPILOT_DB"] = self.db_path
        root = str(Path(__file__).resolve().parents[1])
        try:
            proc = subprocess.run([sys.executable, "-m", "docpilot.mcp_server"],
                                  input=request_data, capture_output=True, text=True, timeout=12,
                                  cwd=root, env=env, check=False)
            if proc.returncode != 0:
                return {"error": "MCP server subprocess failed"}
            responses = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
            initialized = next((r for r in responses if r.get("id") == 1), None)
            reply = next((r for r in responses if r.get("id") == 2), None)
            if not initialized or initialized.get("result", {}).get("serverInfo", {}).get("name") != "docpilot-docs":
                return {"error": "MCP handshake did not complete"}
            if reply is None or "error" in reply:
                return {"error": "MCP call returned a protocol error"}
            content = reply.get("result", {}).get("content", [])
            if not content:
                return {"error": "MCP call returned no result"}
            return json.loads(content[0]["text"])
        except (OSError, ValueError, subprocess.TimeoutExpired, KeyError):
            return {"error": "MCP transport failed"}