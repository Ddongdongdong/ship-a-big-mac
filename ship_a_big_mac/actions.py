"""Preview explicit account mutations and bind confirmation to their exact inputs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any

from .catalog import WRITE_MCP_TOOLS
from .mcp import MCPClient, MCPError


CONFIRMATION_TTL_SECONDS = 5 * 60
_USED_CONFIRMATIONS: set[str] = set()


def _confirmation_store() -> Path:
    configured = os.environ.get("SHIP_A_BIG_MAC_CONFIRMATION_STORE")
    return Path(configured).expanduser() if configured else Path(tempfile.gettempdir()) / "ship-a-big-mac-confirmations.json"


def _preview_store() -> Path:
    configured = os.environ.get("SHIP_A_BIG_MAC_CONFIRMATION_PREVIEWS")
    return Path(configured).expanduser() if configured else Path(tempfile.gettempdir()) / "ship-a-big-mac-confirmation-previews.json"


def _save_preview(preview: dict[str, Any]) -> None:
    """Keep the exact preview locally so a later CLI process can execute it.

    The file contains the user supplied operation, never the MCP bearer token.
    It is a convenience for the two-step CLI flow; server-side idempotency is
    still required for writes that can time out after reaching the server.
    """
    path = _preview_store()
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(current, dict):
            current = {}
    except (OSError, ValueError, TypeError):
        current = {}
    now = float(preview["issued_at"])
    current = {
        key: value for key, value in current.items()
        if isinstance(value, dict) and isinstance(value.get("expires_at"), (int, float)) and value["expires_at"] >= now
    }
    current[str(preview["confirmation_code"])] = preview
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except OSError:
        pass


def load_preview(confirmation: str, *, now: float | None = None) -> dict[str, Any] | None:
    """Load a previously printed preview for a cross-process CLI execution."""
    path = _preview_store()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    preview = raw.get(confirmation) if isinstance(raw, dict) else None
    if not isinstance(preview, dict):
        return None
    current = time.time() if now is None else now
    if not isinstance(preview.get("expires_at"), (int, float)) or current > preview["expires_at"]:
        return None
    return preview


def _load_used_confirmations(now: float) -> set[str]:
    values = set(_USED_CONFIRMATIONS)
    path = _confirmation_store()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            values.update(key for key, expiry in raw.items() if isinstance(key, str) and isinstance(expiry, (int, float)) and expiry >= now)
    except (OSError, ValueError, TypeError):
        pass
    return values


def _consume_confirmation(confirmation: str, expires_at: float, now: float, *, persist: bool = True) -> None:
    used = _USED_CONFIRMATIONS if not persist else _load_used_confirmations(now)
    if confirmation in used:
        raise ValueError("confirmation has already been used; review a new preview")
    _USED_CONFIRMATIONS.add(confirmation)
    if not persist:
        return
    path = _confirmation_store()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        current = _load_used_confirmations(now)
        current.add(confirmation)
        path.write_text(json.dumps({key: expires_at for key in current}, separators=(",", ":")), encoding="utf-8")
    except OSError:
        # The in-process set still prevents a second execution. The server-side
        # operation must provide idempotency if it supports one.
        pass


def validate_arguments(value: Any, schema: dict[str, Any], path: str = "arguments") -> None:
    """Validate the types, required fields and enums used by current MCP schemas."""
    kind = schema.get("type")
    matches = {
        "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "integer": type(value) is int,
        "number": type(value) in (int, float), "boolean": type(value) is bool,
        "null": value is None,
    }
    if isinstance(kind, str) and kind in matches and not matches[kind]:
        raise ValueError(f"{path} must be {kind}")
    if "enum" in schema and not any(type(value) is type(option) and value == option for option in schema["enum"]):
        raise ValueError(f"{path} is not an allowed enum value")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                validate_arguments(child, properties[key], f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                raise ValueError(f"{path} contains an unsupported field")
    elif isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, child in enumerate(value):
            validate_arguments(child, schema["items"], f"{path}[{index}]")


def require_success(result: dict[str, Any], tool: str) -> dict[str, Any]:
    if result.get("isError"):
        raise MCPError(f"MCP tool failed: {tool}")
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and (
        structured.get("success") is False
        or ("code" in structured and structured["code"] not in (0, 200, "0", "200"))
    ):
        raise MCPError(f"MCP business request failed: {tool}")
    return result


def _order_quote(client: MCPClient, arguments: dict[str, Any], schemas: dict[str, dict[str, Any]]) -> int:
    if not arguments.get("items"):
        raise ValueError("create-order requires a non-empty items list")
    quote_schema = schemas.get("calculate-price", {}).get("inputSchema", {})
    fields = quote_schema.get("properties", {})
    if not fields:
        raise MCPError("calculate-price schema is unavailable")
    quote_arguments = {key: value for key, value in arguments.items() if key in fields}
    validate_arguments(quote_arguments, quote_schema)
    result = require_success(client.call_tool("calculate-price", quote_arguments), "calculate-price")
    structured = result.get("structuredContent", {})
    data = structured.get("data", {})
    if structured.get("success") is not True or type(data.get("price")) is not int or data["price"] < 0:
        raise MCPError("order preview requires a successful live price calculation")
    from collections import Counter
    def signature(items):
        if not isinstance(items, list) or not items:
            raise MCPError("order quote is missing products")
        values = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("productCode"), str) or type(item.get("quantity")) is not int or item["quantity"] < 1:
                raise MCPError("order quote contains invalid products")
            values.append((item["productCode"], item["quantity"]))
        return Counter(values)
    if signature(arguments["items"]) != signature(data.get("productList")):
        raise MCPError("order quote products do not match the request")
    if arguments.get("orderType") == 1:
        valid_takeways = {item.get("code") for item in data.get("takeWayList", [])}
        if arguments.get("takeWayCode") not in valid_takeways:
            raise ValueError("select takeWayCode from the current calculate-price takeWayList before preparing the order")
    return data["price"]


def prepare_action(client: MCPClient, tool: str, arguments: dict[str, Any], url: str, *, now: float | None = None) -> dict[str, Any]:
    if tool not in WRITE_MCP_TOOLS:
        raise ValueError("unknown action; inspect the supported capability catalog")
    schemas = {item["name"]: item for item in client.list_tools()}
    if tool not in schemas:
        raise ValueError("action is not available on the live MCP server")
    validate_arguments(arguments, schemas[tool].get("inputSchema", {}))
    issued_at = time.time() if now is None else now
    expires_at = issued_at + CONFIRMATION_TTL_SECONDS
    preview: dict[str, Any] = {
        "tool": tool, "effect": WRITE_MCP_TOOLS[tool], "server": url,
        "arguments": arguments, "executed": False,
        "issued_at": issued_at, "expires_at": expires_at,
    }
    if tool == "create-order":
        preview["quote_total_cents"] = _order_quote(client, arguments, schemas)
        preview["quote_currency"] = "CNY"
    canonical = json.dumps(preview, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    preview["confirmation_code"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    _save_preview(preview)
    return preview


def execute_action(client: MCPClient, preview: dict[str, Any], confirmation: str, *, now: float | None = None) -> dict[str, Any]:
    current_time = time.time() if now is None else now
    expires_at = preview.get("expires_at")
    if type(expires_at) not in (int, float) or current_time > expires_at:
        raise ValueError("confirmation has expired; review a new preview")
    checked = {key: value for key, value in preview.items() if key != "confirmation_code"}
    canonical = json.dumps(checked, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if confirmation != actual or confirmation != preview["confirmation_code"]:
        raise ValueError("confirmation does not match this action, arguments, or current price; review a new preview")
    if preview.get("tool") == "create-order":
        schemas = {item["name"]: item for item in client.list_tools()}
        current_price = _order_quote(client, preview["arguments"], schemas)
        if current_price != preview.get("quote_total_cents"):
            raise ValueError("current price changed; review a new preview before creating the order")
    # Tests and callers that provide a synthetic clock must not collide with a
    # stale wall-clock confirmation persisted by another process. Real CLI
    # executions retain the file-backed replay protection.
    _consume_confirmation(confirmation, float(expires_at), current_time, persist=now is None)
    # Deliberately no retry: a timeout may mean a write already reached the server.
    return require_success(client.call_tool(preview["tool"], preview["arguments"]), preview["tool"])
