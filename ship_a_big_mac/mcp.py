"""Small Streamable HTTP MCP client used for connection verification.

Business calls remain orchestrated by the Skill so the model can inspect every
tool schema returned by the live server instead of guessing request fields.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from io import BytesIO
import json
import os
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from . import __version__


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
    def _decode_json(text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            raise MCPError("MCP server returned non-JSON data") from None
        if not isinstance(parsed, dict):
            raise MCPError("MCP response must be a JSON object")
        return parsed

    @staticmethod
    def _matches_response(response: dict[str, Any], request_id: int) -> bool:
        return (
            type(response.get("id")) is type(request_id)
            and response.get("id") == request_id
            and ("result" in response or "error" in response)
        )

    @classmethod
    def _read_sse(
        cls, lines: Iterable[bytes], request_id: int | None = None
    ) -> dict[str, Any]:
        data: list[str] = []

        def event_response() -> dict[str, Any] | None:
            if not data:
                return None
            parsed = cls._decode_json("\n".join(data))
            data.clear()
            if request_id is None or cls._matches_response(parsed, request_id):
                return parsed
            return None

        for raw_line in lines:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                parsed = event_response()
                if parsed is not None:
                    return parsed
            elif line == "data" or line.startswith("data:"):
                value = line.partition(":")[2]
                data.append(value[1:] if value.startswith(" ") else value)
        parsed = event_response()
        if parsed is not None:
            return parsed
        raise MCPError("MCP event stream ended without a matching response")

    @classmethod
    def _decode(
        cls, body: bytes, content_type: str, request_id: int | None = None
    ) -> dict[str, Any] | None:
        if not body:
            return None
        if "text/event-stream" in content_type.lower():
            return cls._read_sse(BytesIO(body), request_id)
        parsed = cls._decode_json(body.decode("utf-8", errors="replace"))
        if request_id is not None and not cls._matches_response(parsed, request_id):
            raise MCPError("MCP response id did not match the request")
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
                if "id" not in payload:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "text/event-stream" in content_type.lower():
                    return self._read_sse(response, payload["id"])
                return self._decode(response.read(), content_type, payload["id"])
        except HTTPError as exc:
            if exc.code == 401:
                raise MCPError("MCP authentication failed (401); rotate or check the local token") from exc
            if exc.code == 429:
                raise MCPError("MCP rate limit reached (429); retry later") from exc
            raise MCPError(f"MCP HTTP error {exc.code}") from exc
        except URLError as exc:
            raise MCPError("Could not reach the MCP server") from exc
        except TimeoutError:
            raise MCPError("MCP server response timed out") from None

    @staticmethod
    def _result(response: dict[str, Any] | None, operation: str) -> dict[str, Any]:
        if not response or "error" in response:
            raise MCPError(f"MCP {operation} failed")
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPError(f"MCP {operation} returned an invalid result")
        return result

    def initialize(self) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "ship-a-big-mac", "version": __version__},
                },
            }
        )
        result = self._result(response, "initialize")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        params: dict[str, Any] = {}
        seen_cursors: set[str] = set()
        while True:
            response = self._post(
                {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list", "params": params}
            )
            result = self._result(response, "tools/list")
            page = result.get("tools")
            if not isinstance(page, list):
                raise MCPError("MCP tools/list returned an invalid tool list")
            tools.extend(tool for tool in page if isinstance(tool, dict))
            cursor = result.get("nextCursor")
            if cursor is None:
                return tools
            if not isinstance(cursor, str) or cursor in seen_cursors:
                raise MCPError("MCP tools/list returned an invalid or repeated cursor")
            seen_cursors.add(cursor)
            params = {"cursor": cursor}

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        result = self._result(response, f"tool call ({name})")
        if result.get("isError"):
            raise MCPError(f"MCP tool reported an error: {name}")
        return result

    def __enter__(self) -> "MCPClient":
        self.initialize()
        return self

    def __exit__(self, *exc: object) -> None:
        self.session_id = None
