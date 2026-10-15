"""Preview explicit account mutations and bind confirmation to their exact inputs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .catalog import WRITE_MCP_TOOLS
from .mcp import MCPClient, MCPError


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


def prepare_action(client: MCPClient, tool: str, arguments: dict[str, Any], url: str) -> dict[str, Any]:
    if tool not in WRITE_MCP_TOOLS:
        raise ValueError("unknown action; inspect the supported capability catalog")
    schemas = {item["name"]: item for item in client.list_tools()}
    if tool not in schemas:
        raise ValueError("action is not available on the live MCP server")
    validate_arguments(arguments, schemas[tool].get("inputSchema", {}))
    preview: dict[str, Any] = {
        "tool": tool, "effect": WRITE_MCP_TOOLS[tool], "server": url,
        "arguments": arguments, "executed": False,
    }
    if tool == "create-order":
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
        preview["quote_total_cents"] = data["price"]
        preview["quote_currency"] = "CNY"
    canonical = json.dumps(preview, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    preview["confirmation_code"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return preview


def execute_action(client: MCPClient, preview: dict[str, Any], confirmation: str) -> dict[str, Any]:
    checked = {key: value for key, value in preview.items() if key != "confirmation_code"}
    canonical = json.dumps(checked, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if confirmation != actual or confirmation != preview["confirmation_code"]:
        raise ValueError("confirmation does not match this action, arguments, or current price; review a new preview")
    # Deliberately no retry: a timeout may mean a write already reached the server.
    return require_success(client.call_tool(preview["tool"], preview["arguments"]), preview["tool"])
