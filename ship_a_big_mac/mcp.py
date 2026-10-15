"""Small Streamable HTTP MCP client used for connection verification.

Business calls remain orchestrated by the Skill so the model can inspect every
tool schema returned by the live server instead of guessing request fields.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MCPError(RuntimeError):
    pass


class MCPClient(AbstractContextManager["MCPClient"]):
    def __init__(self, token: str | None = None, url: str = "https://mcp.mcd.cn") -> None:
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        if not self.token:
            raise MCPError("MCD_MCP_TOKEN is not set")
        self.url = url
        self.session_id: str | None = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    @staticmethod
    def _decode(body: bytes, content_type: str) -> dict[str, Any] | None:
        if not body:
            return None
        text = body.decode("utf-8", errors="replace")
        if "text/event-stream" in content_type:
            payloads = [
                line[5:].strip()
                for line in text.splitlines()
                if line.startswith("data:") and line[5:].strip()
            ]
            if not payloads:
                raise MCPError("MCP server returned an empty event stream")
            text = payloads[-1]
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPError("MCP server returned non-JSON data") from exc
        if not isinstance(parsed, dict):
            raise MCPError("MCP response must be a JSON object")
        return parsed

    def _post(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-03-26",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                received_session = response.headers.get("Mcp-Session-Id")
                if received_session:
                    self.session_id = received_session
                return self._decode(response.read(), response.headers.get("Content-Type", ""))
        except HTTPError as exc:
            if exc.code == 401:
                raise MCPError("MCP authentication failed (401); rotate or check the local token") from exc
            if exc.code == 429:
                raise MCPError("MCP rate limit reached (429); retry later") from exc
            raise MCPError(f"MCP HTTP error {exc.code}") from exc
        except URLError as exc:
            raise MCPError("Could not reach the MCP server") from exc

    def initialize(self) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "ship-a-big-mac", "version": "0.1.0"},
                },
            }
        )
        if not response or "error" in response:
            raise MCPError("MCP initialize failed")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return dict(response.get("result") or {})

    def list_tools(self) -> list[dict[str, Any]]:
        response = self._post(
            {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list", "params": {}}
        )
        if not response or "error" in response:
            raise MCPError("MCP tools/list failed")
        tools = (response.get("result") or {}).get("tools") or []
        return [tool for tool in tools if isinstance(tool, dict)]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if not response or "error" in response:
            raise MCPError(f"MCP tool call failed: {name}")
        return dict(response.get("result") or {})

    def __enter__(self) -> "MCPClient":
        self.initialize()
        return self

    def __exit__(self, *exc: object) -> None:
        self.session_id = None
