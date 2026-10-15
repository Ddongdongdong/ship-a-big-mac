"""Render a privacy-conscious, self-contained SVG release receipt."""

from __future__ import annotations

from html import escape
from pathlib import Path
import base64
import json

from .git_release import ReleaseContext
from .planner import FeastPlan, format_yuan
from .themes import get_theme

PROJECT_URL = "https://github.com/Ddongdongdong/ship-a-big-mac"


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


def render_achievement_svg(context: ReleaseContext, plan: FeastPlan, scene: str = "major") -> str:
    """A self-contained, portable celebration card; no quote payload or identities."""
    theme = get_theme(scene)
    food = base64.b64encode((Path(__file__).parent / "data" / "feast.png").read_bytes()).decode("ascii")
    verified = plan.quote_source == "MCD_MCP_CALCULATE_PRICE"
    provenance = "本次官方核价 · 未下单" if verified else (
        "用户填写金额 · 未经官方核价" if plan.quote_source == "USER_REPORTED_TOTAL" else "示意金额 · 非实时报价"
    )
    status = "MCP VERIFIED" if verified else "USER REPORTED" if plan.quote_source == "USER_REPORTED_TOTAL" else "SYNTHETIC DEMO"
    # Bound display length without ever interpolating unescaped user content.
    version = context.version if len(context.version) <= 19 else context.version[:18] + "…"
    version_size = min(81, 900 // max(1, len(version)))
    repository = context.repository if len(context.repository) <= 45 else context.repository[:44] + "…"
    color = theme["color"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1080" height="1350" viewBox="0 0 1080 1350" role="img" aria-labelledby="title desc">
<title id="title">{escape(version)} · {escape(theme['name'])} · Ship a Big Mac</title>
<desc id="desc">{escape(provenance)}。{plan.people} 人庆功餐，{format_yuan(plan.quote_total_cents)}。餐品图为主题示意，实际组成见配餐小票。</desc>
<defs>
 <radialGradient id="glow"><stop stop-color="#fff7d8"/><stop offset="1" stop-color="#f1ddb3"/></radialGradient>
 <pattern id="grain" width="6" height="6" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".5" fill="#746048" opacity=".13"/></pattern>
</defs>
<rect width="1080" height="1350" fill="#f9f2e4"/>
<rect width="1080" height="1350" fill="url(#grain)"/>
<path d="M0 0H1080V14H0Z" fill="{color}"/>
<g font-family="Arial, 'Microsoft YaHei', 'PingFang SC', sans-serif" fill="#24221f">
 <rect x="62" y="60" width="52" height="52" rx="16" fill="{color}"/>
 <path d="M77 78H99M77 86H99M77 94H99" stroke="#fff6e5" stroke-width="4" stroke-linecap="round"/>
 <text x="132" y="95" font-size="25" font-weight="800" letter-spacing="1">SHIP A BIG MAC</text>
 <text x="1018" y="92" text-anchor="end" font-size="18" letter-spacing="2">CODE. SHIP. FEAST.</text>
 <path d="M62 142H1018" stroke="#d9cfbd"/>
 <text x="62" y="196" font-size="19" font-weight="700" fill="{color}" letter-spacing="4">{escape(theme['eyebrow'])}</text>
 <text x="57" y="290" font-size="{version_size}" font-weight="900" letter-spacing="-3">{escape(version)}</text>
 <text x="59" y="378" font-size="81" font-weight="900" letter-spacing="-3" fill="{color}">SHIPPED.</text>
 <text x="65" y="431" font-size="26">{escape(theme['tagline'])}</text>
 <circle cx="652" cy="663" r="236" fill="url(#glow)"/>
 <ellipse cx="637" cy="900" rx="310" ry="24" fill="#89704c" opacity=".12"/>
 <image x="357" y="410" width="642" height="560" preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,{food}"/>
 <text x="66" y="540" font-size="18" fill="#7c7060" letter-spacing="3">THE RELEASE</text>
 <text x="65" y="609" font-size="57" font-weight="800">{context.commit_count}</text>
 <text x="67" y="640" font-size="15" letter-spacing="2" fill="#7c7060">COMMITS</text>
 <path d="M65 666H244" stroke="#d9cfbd"/>
 <text x="65" y="732" font-size="57" font-weight="800">{context.files_changed}</text>
 <text x="67" y="763" font-size="15" letter-spacing="2" fill="#7c7060">FILES CHANGED</text>
 <path d="M65 789H244" stroke="#d9cfbd"/>
 <text x="65" y="855" font-size="57" font-weight="800">{context.contributor_count}</text>
 <text x="67" y="886" font-size="15" letter-spacing="2" fill="#7c7060">MAKERS</text>
 <text x="1018" y="951" text-anchor="end" font-size="15" fill="#7c7060">餐品图为主题示意 · 实际组成见配餐小票</text>
 <rect x="42" y="981" width="996" height="230" rx="24" fill="#262723"/>
 <text x="76" y="1030" font-size="16" fill="#dacfb4" letter-spacing="2">READY TO FEAST</text>
 <text x="76" y="1084" font-size="36" font-weight="800" fill="#fff7e7">{escape(theme['name'])}</text>
 <text x="76" y="1129" font-size="22" fill="#dacfb4">{plan.people} 人庆功餐 · {escape(plan.strategy)}方案</text>
 <text x="76" y="1172" font-size="16" fill="#dacfb4">{escape(repository)}</text>
 <text x="1000" y="1044" text-anchor="end" font-size="18" fill="#dacfb4">{provenance}</text>
 <text x="1000" y="1120" text-anchor="end" font-size="64" font-weight="800" fill="#f8c649">{format_yuan(plan.quote_total_cents)}</text>
 <text x="1000" y="1170" text-anchor="end" font-size="16" letter-spacing="1" fill="#dacfb4">{status}</text>
 <a xlink:href="{PROJECT_URL}"><text x="62" y="1260" font-size="20" font-weight="700">github.com/Ddongdongdong/ship-a-big-mac ↗</text></a>
 <text x="62" y="1301" font-size="16" fill="#7c7060">每一次交付，都值得被好好庆祝。</text>
 <text x="1018" y="1301" text-anchor="end" font-size="15" fill="#7c7060">非麦当劳官方产品</text>
</g></svg>'''


def write_achievement(path: str | Path, context: ReleaseContext, plan: FeastPlan, scene: str = "major") -> Path:
    output = Path(path).expanduser()
    output.write_text(render_achievement_svg(context, plan, scene), encoding="utf-8")
    return output.resolve()


def write_celebration_html(path: str | Path, context: ReleaseContext, plan: FeastPlan, scene: str = "major") -> Path:
    """Portable local preview with browser PNG export, requiring no Python imaging dependency."""
    svg = render_achievement_svg(context, plan, scene)
    # JSON in a script must not allow an embedded closing script tag.
    encoded = json.dumps(svg, ensure_ascii=True).replace("<", "\\u003c")
    receipt = render_receipt_svg(context, plan)
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>你的发版成就卡 · Ship a Big Mac</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4ecdc;color:#272723;font-family:Arial,'Microsoft YaHei',sans-serif}main{max-width:1100px;margin:40px auto;padding:0 22px}header{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:26px}h1{font-size:25px;margin:8px 0}p{line-height:1.7;color:#736650}.grid{display:grid;grid-template-columns:1.15fr 1fr;gap:30px;align-items:start}.card{box-shadow:0 20px 60px #51371922;border-radius:12px;overflow:hidden}.card svg,.receipt svg{display:block;width:100%;height:auto}button,a.button{background:#bd3329;color:#fff8e7;border:0;border-radius:100px;padding:14px 23px;font:700 15px Arial,'Microsoft YaHei',sans-serif;cursor:pointer;text-decoration:none}button:disabled{opacity:.6}a{color:#a42c25}.actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}footer{font-size:13px;margin-top:30px}@media(max-width:720px){.grid{grid-template-columns:1fr}header{display:block}main{margin-top:24px}}
</style><main><header><div><p>SHIP A BIG MAC · RELEASE UNLOCKED</p><h1>这次交付，值得一顿庆功餐。</h1></div><a href="https://github.com/Ddongdongdong/ship-a-big-mac">查看开源项目 ↗</a></header><div class="grid"><div class="card">CARD_SVG</div><div><div class="receipt">RECEIPT_SVG</div><div class="actions"><button id="png">保存成就卡 PNG</button><button id="svg">保存 SVG</button></div><p id="status" role="status">成就卡带仓库名和聚合统计，分享前可以预览检查。</p><p>餐品图为主题示意，餐品组成见小票。核价金额仅代表本次查询；再次点餐需重新核价。</p></div></div><footer>非麦当劳官方产品 · 代码已上线，汉堡安排上。</footer></main>
<script>const source=CARD_JSON;
function save(blob,name){const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),2000)}
document.querySelector('#svg').onclick=()=>save(new Blob([source],{type:'image/svg+xml;charset=utf-8'}),'release-achievement.svg');
document.querySelector('#png').onclick=async()=>{const button=document.querySelector('#png'),status=document.querySelector('#status');button.disabled=true;const url=URL.createObjectURL(new Blob([source],{type:'image/svg+xml;charset=utf-8'}));try{await document.fonts.ready;const img=new Image();await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;img.src=url});const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1350;canvas.getContext('2d').drawImage(img,0,0);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw Error();save(blob,'release-achievement.png');status.textContent='成就卡已保存，可以分享给队友了。'}catch(error){status.textContent='当前浏览器无法导出 PNG，请保存 SVG，或用 Chrome / Edge 打开此文件。'}finally{URL.revokeObjectURL(url);button.disabled=false}};
</script></html>'''
    page = page.replace("CARD_JSON", encoded).replace("RECEIPT_SVG", receipt).replace("CARD_SVG", svg)
    output = Path(path).expanduser()
    output.write_text(page, encoding="utf-8")
    return output.resolve()
