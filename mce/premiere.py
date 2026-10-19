"""Minimal stdio MCP client for the premiere-pro-mcp server, so scripts (and
sessions where the MCP tools aren't loaded) can drive Premiere.

  uv run python -m mce.premiere list [filter]
  uv run python -m mce.premiere call <tool> '<json args>'
"""
import json
import os
import subprocess
import sys

from .config import premiere_server


class Client:
    def __init__(self):
        env = {**os.environ, "PREMIERE_MCP_TOOL_PACKS": os.environ.get("PREMIERE_MCP_TOOL_PACKS", "full")}
        self.p = subprocess.Popen(premiere_server(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, env=env)
        self.n = 0
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "mce", "version": "0.1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, msg):
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def request(self, method, params):
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("server exited")
            msg = json.loads(line)
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    def tools(self):
        out, cursor = [], None
        while True:
            r = self.request("tools/list", {"cursor": cursor} if cursor else {})
            out += r["tools"]
            cursor = r.get("nextCursor")
            if not cursor:
                return out

    def call(self, name, args=None, retry=True):
        r = self.request("tools/call", {"name": name, "arguments": args or {}})
        text = "\n".join(c.get("text", "") for c in r.get("content", []))
        # An uncertain or refused edit locks further edits until the state is
        # acknowledged. Our callers re-read state after every step, so
        # acknowledge and retry once.
        if retry and "HOST_RECOVERY_REQUIRED" in text and self.recover():
            return self.call(name, args, retry=False)
        return text

    def recover(self) -> bool:
        state = json.loads(self.call("inspect_operation_recovery", {"backend": "cep"}, retry=False))
        if not state.get("recoveryRequired"):
            return False
        res = self.call("acknowledge_operation_recovery", {
            "backend": "cep", "expected_recovery_revision": state["recoveryRevision"],
            "expected_host_state_revision": state["hostStateRevision"], "reviewed": True}, retry=False)
        return '"acknowledged": true' in res

    def close(self):
        self.p.terminate()


def main():
    c = Client()
    try:
        if sys.argv[1] == "list":
            flt = sys.argv[2].lower() if len(sys.argv) > 2 else ""
            for t in c.tools():
                if flt in t["name"].lower() or flt in t.get("description", "").lower():
                    print(f"{t['name']}: {t.get('description', '')[:140]}")
        elif sys.argv[1] == "schema":
            t = next(t for t in c.tools() if t["name"] == sys.argv[2])
            print(json.dumps(t["inputSchema"], indent=1))
        else:
            print(c.call(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}))
    finally:
        c.close()


if __name__ == "__main__":
    main()
