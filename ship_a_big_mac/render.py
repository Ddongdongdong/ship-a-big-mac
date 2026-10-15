"""Render a privacy-conscious, self-contained SVG release receipt."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .git_release import ReleaseContext
from .planner import FeastPlan, format_yuan


def render_receipt_svg(context: ReleaseContext, plan: FeastPlan) -> str:
    width = 720
    row_height = 34
    height = 410 + row_height * len(plan.lines)
    status = {
        "MCD_MCP_CALCULATE_PRICE": "MCP VERIFIED",
        "USER_REPORTED_TOTAL": "USER REPORTED",
    }.get(plan.quote_source, "DEMO · NOT QUOTED")
    status_color = "#16803a" if status == "MCP VERIFIED" else "#9a6700"
    line_note = "各项为菜单参考价 · 实时核价见 TOTAL" if status == "MCP VERIFIED" else "各项为菜单参考价 · 总额尚未实时核验"
    rows: list[str] = []
    y = 250
    for line in plan.lines:
        rows.append(
            f'<text x="66" y="{y}" class="item">{escape(line.name)} × {line.quantity}</text>'
            f'<text x="654" y="{y}" class="money" text-anchor="end">{format_yuan(line.subtotal_cents)}</text>'
        )
        y += row_height
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Ship a Big Mac Release Receipt</title>
  <desc id="desc">A shareable release celebration meal receipt without personal data.</desc>
  <style>
    .bg {{ fill: #fff8e7; }} .paper {{ fill: #fffdf7; stroke: #1f2328; stroke-width: 2; }}
    .brand {{ font: 700 30px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #da291c; }}
    .meta {{ font: 16px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #343a40; }}
    .item {{ font: 17px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #1f2328; }}
    .money {{ font: 700 17px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #1f2328; }}
    .total {{ font: 700 23px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #1f2328; }}
    .small {{ font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #57606a; }}
  </style>
  <rect class="bg" width="100%" height="100%"/>
  <rect class="paper" x="30" y="24" width="660" height="{height - 48}" rx="16"/>
  <text x="60" y="72" class="brand">SHIP A BIG MAC</text>
  <text x="60" y="103" class="meta">RELEASE  {escape(context.repository)} / {escape(context.version)}</text>
  <text x="60" y="132" class="meta">{context.commit_count} commits · {context.files_changed} files · {context.contributor_count} makers</text>
  <rect x="60" y="154" width="600" height="38" rx="8" fill="#ffdf59"/>
  <text x="78" y="179" class="meta">{escape(plan.strategy)} · {plan.people} 人 · {escape(status)}</text>
  <line x1="60" y1="213" x2="660" y2="213" stroke="#8c959f" stroke-dasharray="7 7"/>
  <text x="654" y="208" class="small" text-anchor="end">{line_note}</text>
  {''.join(rows)}
  <line x1="60" y1="{y + 5}" x2="660" y2="{y + 5}" stroke="#8c959f" stroke-dasharray="7 7"/>
  <text x="60" y="{y + 48}" class="total">TOTAL</text>
  <text x="660" y="{y + 48}" class="total" text-anchor="end">{format_yuan(plan.quote_total_cents)}</text>
  <text x="60" y="{y + 82}" class="small">报价状态：</text>
  <text x="148" y="{y + 82}" class="small" fill="{status_color}">{escape(status)}</text>
  <text x="60" y="{y + 108}" class="small">不含姓名、邮箱、提交信息、门店、地址或订单号 · 非麦当劳官方产品</text>
</svg>'''


def write_receipt(path: str | Path, context: ReleaseContext, plan: FeastPlan) -> Path:
    output = Path(path).expanduser()
    output.write_bytes(render_receipt_svg(context, plan).encode("utf-8"))
    return output.resolve()
