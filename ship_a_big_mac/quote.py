"""Bind a live MCP price calculation to the exact items in a feast plan."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .mcp import MCPClient, MCPError
from .planner import FeastPlan, apply_mcp_quote


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

    result = client.call_tool("calculate-price", arguments)
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
    if price > plan.budget_cents:
        raise MCPError("MCP calculate-price total exceeds the plan budget")
    return apply_mcp_quote(plan, total_cents=price)
