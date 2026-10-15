"use strict";
const projectUrl = "https://github.com/Ddongdongdong/ship-a-big-mac";
const playgroundUrl = "https://ddongdongdong.github.io/ship-a-big-mac/";
const stats = {commits: 24, files: 37, makers: 5};
let scene = "major";
let strategy = "均衡";
let currentReceipt = null;
const money = cents => `¥${(cents / 100).toFixed(2)}`;
const $ = selector => document.querySelector(selector);
const escapeXml = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"})[c]);

function achievementSvg(receipt) {
  const theme = window.CELEBRATION_THEMES[receipt.scene];
  const values = {repository:"rocket-checkout · 示例", version:receipt.version, versionSize:Math.min(81,Math.floor(900 / Math.max(1,[...receipt.version].length))), commits:stats.commits, files:stats.files, makers:stats.makers, people:receipt.people, strategy:receipt.strategy, amount:receipt.plan.feasible ? money(receipt.plan.spent) : "待规划", eyebrow:theme.eyebrow, themeName:theme.name, tagline:theme.tagline, color:theme.color};
  return window.CARD_TEMPLATE.replace(/\{\{(\w+)\}\}/g, (_, key) => escapeXml(values[key]));
}
function receiptSvg(receipt) {
  const {plan, people, budget} = receipt;
  const end = 220 + plan.lines.length * 38;
  const text = (x,y,value,attrs="") => `<text x="${x}" y="${y}" ${attrs}>${escapeXml(value)}</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="${end+215}" viewBox="0 0 720 ${end+215}"><rect width="720" height="${end+215}" fill="#fff7e7"/><g font-family="Arial,'Microsoft YaHei',sans-serif" fill="#292822" font-size="17">${text(40,57,"SHIP A BIG MAC",'font-size="30" font-weight="800" fill="#bc3529"')}${text(40,100,`${receipt.version} · ${window.CELEBRATION_THEMES[receipt.scene].name}`)}${text(40,136,"24 commits · 37 files · 5 makers（示例统计）")}${text(40,174,`${people} 人用餐 · ${receipt.strategy} · 示意金额`)}<path d="M40 192H680" stroke="#d1bfa0" stroke-dasharray="6 6"/>${plan.lines.map((line,i)=>text(40,220+i*38,`${line.name} × ${line.quantity}`)+text(680,220+i*38,money(line.price*line.quantity),'text-anchor="end"')).join("")}<path d="M40 ${end}H680" stroke="#d1bfa0" stroke-dasharray="6 6"/>${text(40,end+42,"示例合计",'font-weight="700"')}${text(680,end+42,money(plan.spent),'text-anchor="end" font-size="30" font-weight="800"')}${text(40,end+78,`预算 ${money(budget)} · 名义份数 ${plan.covered}`)}${text(40,end+116,"虚构餐品与金额 · 未实时核价 · 未下单",'font-size="15" fill="#bc3529"')}${text(40,end+146,"MENU_SUM_NOT_MCP_QUOTED · 非麦当劳官方产品",'font-size="12"')}${text(40,end+180,"github.com/Ddongdongdong/ship-a-big-mac",'font-size="15"')}</g></svg>`;
}
function render() {
  const people = Number($("#people").value), budget = Number($("#budget").value)*100;
  const version = $("#release-version").value.trim() || "MY RELEASE";
  const plan = window.FeastPlanner.buildPlan(people,budget,strategy);
  currentReceipt = {people,budget,version,scene,strategy,plan};
  $("#people-value").value = `${people} 人`;
  $("#budget-value").value = `¥${budget/100}`;
  $("#achievement-card").innerHTML = achievementSvg(currentReceipt);
  $("#plan-label").textContent = `${strategy}方案`;
  $("#receipt-total").textContent = plan.feasible ? money(plan.spent) : "—";
  $("#coverage").textContent = plan.feasible ? `${plan.covered} 名义人份 / ${people} 人用餐` : `尚未生成 ${people} 人方案`;
  $("#budget-state").textContent = plan.feasible ? `预算剩余 ${money(budget-plan.spent)}` : `还需 ${money(plan.minimum-budget)}`;
  $("#receipt-lines").replaceChildren();
  for(const line of plan.lines) {
    const row = document.createElement("div"), name = document.createElement("span"), price = document.createElement("span");
    row.className = "receipt-line"; name.textContent = `${line.name} × ${line.quantity}`; price.textContent = money(line.price*line.quantity); row.append(name,price); $("#receipt-lines").append(row);
  }
  if(!plan.feasible) $("#receipt-lines").textContent = `当前示例菜单至少需要 ${money(plan.minimum)}。请提高预算或减少人数，再生成成就卡。`;
  for(const selector of ["#download-png","#download-card","#download-receipt","#copy-share"]) $(selector).disabled = !plan.feasible;
  $("#share-status").textContent = "";
  $("#copy-fallback").hidden = true;
}
function shareText(receipt) {
  const theme = window.CELEBRATION_THEMES[receipt.scene];
  return [`${receipt.version} SHIPPED. 代码已上线，汉堡安排上。🍔`,`${theme.name} · ${receipt.people} 人 · 示例合计 ${money(receipt.plan.spent)}`,"我用 Ship a Big Mac 给这次交付做了一张成就卡。", "这是离线试玩：虚构菜单与金额，工程统计为示例，未实时核价，也没有下单。",`免费试玩：${playgroundUrl}`,`开源项目：${projectUrl}`,"觉得有用，欢迎在 GitHub 点一颗 Star。"].join("\n");
}
function downloadBlob(blob,name) {
  const url = URL.createObjectURL(blob), anchor = document.createElement("a");
  anchor.href=url; anchor.download=name; anchor.click(); setTimeout(()=>URL.revokeObjectURL(url),2000);
}
async function copyText(text, statusElement, success) {
  try { await navigator.clipboard.writeText(text); statusElement.textContent=success; }
  catch { $("#copy-text").value=text; $("#copy-fallback").hidden=false; $("#copy-text").focus(); $("#copy-text").select(); statusElement.textContent="浏览器未允许自动复制，请在下方文本框手动复制。"; }
}
for(const button of document.querySelectorAll("[data-scene]")) button.addEventListener("click",()=>{
  scene=button.dataset.scene;
  for(const other of document.querySelectorAll("[data-scene]")){const active=other===button;other.classList.toggle("active",active);other.setAttribute("aria-pressed",String(active));}
  render();
});
for(const button of document.querySelectorAll("[data-strategy]")) button.addEventListener("click",()=>{
  strategy=button.dataset.strategy;
  for(const other of document.querySelectorAll("[data-strategy]")){const active=other===button;other.classList.toggle("active",active);other.setAttribute("aria-pressed",String(active));}
  render();
});
for(const selector of ["#people","#budget","#release-version"]) $(selector).addEventListener("input",render);
$("#planner-form").addEventListener("submit",event=>{
  event.preventDefault();render();
  if(!currentReceipt.plan.feasible){$("#share-status").textContent="预算暂时不够，调整后再生成。";return;}
  const card=$("#achievement-card");card.classList.remove("celebrated");void card.offsetWidth;card.classList.add("celebrated");
  $("#share-status").textContent="成就卡已就绪，把这次交付的快乐分享出去吧。";
  if(window.innerWidth<761) $("#result").scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});
});
$("#download-card").addEventListener("click",()=>{if(!currentReceipt.plan.feasible)return;downloadBlob(new Blob([achievementSvg(currentReceipt)],{type:"image/svg+xml;charset=utf-8"}),"release-achievement.svg");$("#share-status").textContent="SVG 成就卡已保存。";});
$("#download-receipt").addEventListener("click",()=>{if(!currentReceipt.plan.feasible)return;downloadBlob(new Blob([receiptSvg(currentReceipt)],{type:"image/svg+xml;charset=utf-8"}),"release-receipt.svg");});
$("#download-png").addEventListener("click",async event=>{
  if(!currentReceipt.plan.feasible)return;
  const button=event.currentTarget, receipt=currentReceipt;
  button.disabled=true;
  const url=URL.createObjectURL(new Blob([achievementSvg(receipt)],{type:"image/svg+xml;charset=utf-8"}));
  try{
    await document.fonts.ready;
    const img=new Image();await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;img.src=url;});
    const canvas=document.createElement("canvas");canvas.width=1080;canvas.height=1350;canvas.getContext("2d").drawImage(img,0,0);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));if(!blob)throw new Error("PNG encoding failed");
    downloadBlob(blob,"release-achievement.png");$("#share-status").textContent="PNG 已保存。把这张成就卡发给队友吧。";
  }catch{$("#share-status").textContent="当前浏览器无法导出 PNG，可以保存 SVG，或使用 Chrome / Edge 重试。";}
  finally{URL.revokeObjectURL(url);button.disabled=!currentReceipt.plan.feasible;}
});
$("#copy-share").addEventListener("click",()=>{if(currentReceipt.plan.feasible)copyText(shareText(currentReceipt),$("#share-status"),"分享文案已复制，带上成就卡一起发给队友吧。");});
$("#copy-command").addEventListener("click",()=>copyText([`git clone ${projectUrl}.git`,"cd ship-a-big-mac","python -m pip install -e .","ship-a-big-mac celebrate --demo"].join("\n"),$("#command-status"),"安装和离线试玩步骤已复制。"));
render();
