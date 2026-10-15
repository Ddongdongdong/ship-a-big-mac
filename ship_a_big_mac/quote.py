"""Bind a live MCP price calculation to the exact items in a feast plan."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from typing import Any

from .mcp import MCPClient, MCPError
from .planner import FeastPlan, apply_mcp_quote


def quote_context_digest(arguments: dict[str, Any], server_url: str = "https://mcp.mcd.cn") -> str:
    """Bind the complete request, including combo options, coupons and fulfillment."""
    payload = {"server": server_url.rstrip("/"), "arguments": arguments}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def bind_quote_context(plan: FeastPlan, arguments: dict[str, Any], server_url: str = "https://mcp.mcd.cn") -> FeastPlan:
    digest = quote_context_digest(arguments, server_url)
    if plan.quote_context_digest and plan.quote_context_digest != digest:
        raise ValueError("quote context changed; build and quote a new candidate")
    return replace(plan, quote_context_digest=digest)


def _item_signature(items: object) -> Counter[tuple[str, int]]:
    if not isinstance(items, list) or not items:
        raise ValueError("quote items must be a non-empty list")
    signature: Counter[tuple[str, int]] = Counter()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("quote items must be objects")
        code, quantity = item.get("productCode"), item.get("quantity")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("quote product codes must be non-empty strings")
        if type(quantity) is not int or quantity <= 0:
            raise ValueError("quote quantities must be positive integers")
        signature[(code, quantity)] += 1
    return signature


def quote_plan(client: MCPClient, plan: FeastPlan, arguments: dict[str, Any]) -> FeastPlan:
    """Quote matching items once, accepting only a successful structured result.

    Product subtotals can differ from the final price because of discounts;
    the official ``data.price`` is the authoritative total in integer cents.
    """
    if not isinstance(arguments, dict):
        raise ValueError("quote arguments must be an object")
    expected = _item_signature([
        {"productCode": line.code, "quantity": line.quantity} for line in plan.lines
    ])
    requested = _item_signature(arguments.get("items"))
    if requested != expected:
        raise ValueError("quote items must exactly match the selected plan")

    server_url = getattr(client, "url", None)
    if not isinstance(server_url, str):
        server_url = "https://mcp.mcd.cn"
    # Capture a private snapshot; the caller cannot change the checked request
    # while the network request is in flight.
    snapshot = deepcopy(arguments)
    bound = bind_quote_context(plan, snapshot, server_url)
    result = client.call_tool("calculate-price", snapshot)
    if quote_context_digest(snapshot, server_url) != bound.quote_context_digest:
        raise MCPError("MCP calculate-price request context changed during the call")
    if not isinstance(result, dict) or result.get("isError"):
        raise MCPError("MCP calculate-price failed")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise MCPError("MCP calculate-price requires an object in structuredContent")
    code = structured.get("code")
    if structured.get("success") is not True or type(code) is not int or code != 200:
        raise MCPError("MCP calculate-price business request failed")
    data = structured.get("data")
    if not isinstance(data, dict):
        raise MCPError("MCP calculate-price returned invalid price data")
    price = data.get("price")
    if type(price) is not int or price < 0:
        raise MCPError("MCP calculate-price total must be non-negative integer cents")
    try:
        quoted_items = _item_signature(data.get("productList"))
    except ValueError:
        raise MCPError("MCP calculate-price returned an invalid product list") from None
    if quoted_items != requested:
        raise MCPError("MCP calculate-price products did not match the requested items")
    # The official service does not always echo context. Validate it if present;
    # the request digest records what was submitted, not an invented server proof.
    for key, expected_value in snapshot.items():
        if key != "items" and key in data and data[key] != expected_value:
            raise MCPError("MCP calculate-price response context did not match the request")
    for item in data["productList"]:
        matches = [entry for entry in snapshot["items"] if entry["productCode"] == item["productCode"] and entry["quantity"] == item["quantity"]]
        echoed = {key for entry in matches for key in entry if key not in {"productCode", "quantity"} and key in item}
        if echoed and not any(all(item[key] == entry.get(key) for key in echoed) for entry in matches):
            raise MCPError("MCP calculate-price response options did not match the request")
    if price > plan.budget_cents:
        raise MCPError("MCP calculate-price total exceeds the plan budget")
    return replace(apply_mcp_quote(bound, total_cents=price), quote_context_digest=bound.quote_context_digest)
