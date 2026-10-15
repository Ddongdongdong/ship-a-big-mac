from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .git_release import GitAnalysisError, ReleaseContext, analyze_repository
from .mcp import MCPClient, MCPError
from .planner import (
    MenuItem,
    FeastPlan,
    PlanLine,
    apply_mcp_quote,
    format_yuan,
    plan_feasts,
    yuan_to_cents,
)
from .render import write_receipt


DEMO_MENU = Path(__file__).resolve().parent / "data" / "demo-menu.synthetic.json"
READ_ONLY_MCP_TOOLS = frozenset(
    {
        "now-time-info",
        "query-nearby-stores",
        "query-meals",
        "query-meal-detail",
        "query-store-coupons",
        "calculate-price",
    }
)


def _load_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_menu(path: str | Path) -> list[MenuItem]:
    raw = _load_json(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise ValueError("menu JSON must contain an items array")
    return [MenuItem.from_dict(item) for item in raw["items"] if isinstance(item, dict)]


def _context_from_dict(raw: dict[str, object]) -> ReleaseContext:
    return ReleaseContext(
        repository=str(raw["repository"]),
        branch=str(raw["branch"]),
        version=str(raw["version"]),
        commit_count=int(raw["commit_count"]),
        contributor_count=int(raw["contributor_count"]),
        contributors=tuple(str(value) for value in raw.get("contributors") or []),
        files_changed=int(raw["files_changed"]),
        insertions=int(raw["insertions"]),
        deletions=int(raw["deletions"]),
        intensity=str(raw["intensity"]),
        window_days=int(raw["window_days"]),
    )


def _print_plan(plan: FeastPlan) -> None:
    print(f"\n[{plan.strategy}] {plan.total_serves} 人份 · {format_yuan(plan.quote_total_cents)}")
    for line in plan.lines:
        print(f"  {line.name} × {line.quantity:<2} {format_yuan(line.subtotal_cents):>9}")
    print(f"  报价状态: {plan.quote_source}")


def cmd_demo(args: argparse.Namespace) -> int:
    context = ReleaseContext(
        repository="rocket-checkout",
        branch="main",
        version="v2.4.0",
        commit_count=24,
        contributor_count=5,
        contributors=tuple(f"Contributor {i}" for i in range(1, 6)),
        files_changed=37,
        insertions=1840,
        deletions=620,
        intensity="major",
        window_days=14,
    )
    plans = plan_feasts(_load_menu(DEMO_MENU), people=args.people, budget_cents=yuan_to_cents(args.budget))
    plan = plans[0]
    output = write_receipt(args.output, context, plan)
    print("SHIP A BIG MAC · SYNTHETIC DEMO")
    print(f"Release: {context.repository} {context.version} · {context.commit_count} commits")
    for candidate in plans:
        _print_plan(candidate)
    print(f"\nRelease 小票: {output}")
    print("注意：这是合成菜单和菜单价加总，不是官方实时报价。真实方案必须由 calculate-price 复核。")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    context = analyze_repository(args.repo, since_days=args.days, include_names=args.include_names)
    text = json.dumps(context.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(Path(args.output).resolve())
    else:
        print(text)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    menu = _load_menu(args.menu)
    plans = plan_feasts(menu, people=args.people, budget_cents=yuan_to_cents(args.budget))
    payload = {"plans": [plan.to_dict() for plan in plans]}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(Path(args.output).resolve())
    else:
        print(text)
    return 0


def _plan_from_dict(raw: dict[str, object]) -> FeastPlan:
    lines_raw = raw.get("lines") or []
    lines = tuple(
        PlanLine(
            code=str(line.get("code") or ""),
            name=str(line.get("name") or "未命名餐品"),
            quantity=int(line.get("quantity") or 0),
            unit_price_cents=int(line.get("unit_price_cents") or 0),
            serves=int(line.get("serves") or 1),
            role=str(line.get("role") or "meal"),
        )
        for line in lines_raw
        if isinstance(line, dict)
    )
    return FeastPlan(
        strategy=str(raw.get("strategy") or "均衡"),
        people=int(raw.get("people") or 1),
        budget_cents=int(raw.get("budget_cents") or 0),
        lines=lines,
        quote_total_cents=int(raw.get("quote_total_cents") or 0),
        quote_source=str(raw.get("quote_source") or "MENU_SUM_NOT_MCP_QUOTED"),
        quote_id=str(raw["quote_id"]) if raw.get("quote_id") else None,
    )


def cmd_receipt(args: argparse.Namespace) -> int:
    context_raw = _load_json(args.context)
    plan_raw = _load_json(args.plan)
    if not isinstance(context_raw, dict) or not isinstance(plan_raw, dict):
        raise ValueError("context and plan must be JSON objects")
    if "plans" in plan_raw:
        plans = plan_raw["plans"]
        if not isinstance(plans, list) or not plans:
            raise ValueError("plans array is empty")
        plan_raw = plans[args.index]
    if not isinstance(plan_raw, dict):
        raise ValueError("selected plan must be a JSON object")
    context = _context_from_dict(context_raw)
    plan = _plan_from_dict(plan_raw)
    if args.quoted_total is not None:
        plan = apply_mcp_quote(
            plan,
            total_cents=yuan_to_cents(args.quoted_total),
            quote_id=args.quote_id,
        )
    print(write_receipt(args.output, context, plan))
    return 0


def cmd_mcp_tools(args: argparse.Namespace) -> int:
    with MCPClient(url=args.url) as client:
        tools = client.list_tools()
    if args.json:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
    else:
        for tool in tools:
            print(f"{tool.get('name', '?')}: {tool.get('description', '')}")
        print(f"\n{len(tools)} tools available")
    return 0


def cmd_mcp_inspect(args: argparse.Namespace) -> int:
    with MCPClient(url=args.url) as client:
        tools = client.list_tools()
    selected = next((tool for tool in tools if tool.get("name") == args.tool), None)
    if selected is None:
        raise ValueError(f"MCP tool is not available: {args.tool}")
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    return 0


def cmd_mcp_call(args: argparse.Namespace) -> int:
    if args.tool not in READ_ONLY_MCP_TOOLS:
        allowed = ", ".join(sorted(READ_ONLY_MCP_TOOLS))
        raise ValueError(f"tool is not allowed in read-only mode: {args.tool}; allowed: {allowed}")
    raw_arguments = args.arguments
    if raw_arguments.startswith("@"):
        raw_arguments = Path(raw_arguments[1:]).read_text(encoding="utf-8")
    arguments = json.loads(raw_arguments)
    if not isinstance(arguments, dict):
        raise ValueError("MCP arguments must be a JSON object")
    with MCPClient(url=args.url) as client:
        result = client.call_tool(args.tool, arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ship-a-big-mac")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run the zero-token synthetic demo")
    demo.add_argument("--people", type=int, default=5)
    demo.add_argument("--budget", default="180")
    demo.add_argument("--output", default="release-receipt.svg")
    demo.set_defaults(func=cmd_demo)

    analyze = sub.add_parser("analyze", help="analyze local Git release activity")
    analyze.add_argument("--repo", default=".")
    analyze.add_argument("--days", type=int, default=14)
    analyze.add_argument("--include-names", action="store_true")
    analyze.add_argument("--output")
    analyze.set_defaults(func=cmd_analyze)

    plan = sub.add_parser("plan", help="plan from a normalized menu JSON file")
    plan.add_argument("--menu", required=True)
    plan.add_argument("--people", type=int, required=True)
    plan.add_argument("--budget", required=True, help="budget in yuan")
    plan.add_argument("--output")
    plan.set_defaults(func=cmd_plan)

    receipt = sub.add_parser("receipt", help="render a release receipt from context and plan JSON")
    receipt.add_argument("--context", required=True)
    receipt.add_argument("--plan", required=True)
    receipt.add_argument("--index", type=int, default=0)
    receipt.add_argument("--quoted-total", help="verified calculate-price total in yuan")
    receipt.add_argument("--quote-id")
    receipt.add_argument("--output", default="release-receipt.svg")
    receipt.set_defaults(func=cmd_receipt)

    tools = sub.add_parser("mcp-tools", help="verify the live MCP connection and list tools")
    tools.add_argument("--url", default="https://mcp.mcd.cn")
    tools.add_argument("--json", action="store_true")
    tools.set_defaults(func=cmd_mcp_tools)

    inspect_tool = sub.add_parser("mcp-inspect", help="show a live MCP tool schema")
    inspect_tool.add_argument("tool")
    inspect_tool.add_argument("--url", default="https://mcp.mcd.cn")
    inspect_tool.set_defaults(func=cmd_mcp_inspect)

    call = sub.add_parser("mcp-call", help="call an allowlisted read-only MCP tool")
    call.add_argument("tool", help="one of the six read-only tools used by this project")
    call.add_argument(
        "--arguments",
        default="{}",
        help="JSON object or @path/to/arguments.json; never include the MCP token",
    )
    call.add_argument("--url", default="https://mcp.mcd.cn")
    call.set_defaults(func=cmd_mcp_call)
    return parser


def main(argv: list[str] | None = None) -> None:
    try:
        args = build_parser().parse_args(argv)
        raise SystemExit(args.func(args))
    except (GitAnalysisError, MCPError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
