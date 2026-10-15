// Offline fixtures mirror ship_a_big_mac/data/demo-menu.synthetic.json.
const syntheticMenu = [
  { code: "DEMO-COMBO-01", name: "示例·经典汉堡套餐", price: 3290, serves: 1, role: "combo", tags: ["burger", "fries", "drink"] },
  { code: "DEMO-COMBO-02", name: "示例·香辣鸡腿套餐", price: 2990, serves: 1, role: "combo", tags: ["chicken", "fries", "drink"] },
  { code: "DEMO-SHARE-01", name: "示例·六块分享小食", price: 1850, serves: 2, role: "side", tags: ["share", "chicken"] },
  { code: "DEMO-SHARE-02", name: "示例·双人发版桶", price: 4990, serves: 2, role: "meal", tags: ["share", "chicken", "drink"] },
  { code: "DEMO-DRINK-01", name: "示例·无糖饮料", price: 900, serves: 1, role: "drink", tags: ["drink", "sugar-free"] },
  { code: "DEMO-DESSERT-01", name: "示例·庆功甜品", price: 1250, serves: 1, role: "dessert", tags: ["dessert"] },
];

const projectUrl = "https://github.com/Ddongdongdong/ship-a-big-mac";
const playgroundUrl = "https://ddongdongdong.github.io/ship-a-big-mac/";
const intensityStats = {
  hotfix: { commits: 3, files: 4 },
  regular: { commits: 11, files: 18 },
  major: { commits: 24, files: 37 },
};

let intensity = "major";
let strategy = "均衡";
let currentReceipt = null;

function money(cents) {
  return `¥${(cents / 100).toFixed(2)}`;
}

// Compare tuples as Python does, including deterministic Unicode name tie breaks.
function compareTuple(left, right) {
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] < right[index]) return -1;
    if (left[index] > right[index]) return 1;
  }
  return 0;
}

function minimumCover(mains, people) {
  const costs = [0];
  const choices = [null];
  for (let remaining = 1; remaining <= people; remaining += 1) {
    const costKey = (item) => [item.price + costs[Math.max(0, remaining - item.serves)], item.price, item.name, item.code];
    const chosen = [...mains].sort((a, b) => compareTuple(costKey(a), costKey(b)))[0];
    costs.push(chosen.price + costs[Math.max(0, remaining - chosen.serves)]);
    choices.push(chosen);
  }
  return { costs, choices };
}

function buildPlan(people, budget, selectedStrategy = "均衡") {
  const mains = syntheticMenu.filter((item) => ["meal", "combo"].includes(item.role));
  const minimum = minimumCover(mains, people);
  if (minimum.costs[people] > budget) {
    return { lines: [], covered: 0, spent: 0, minimum: minimum.costs[people], feasible: false };
  }
  const lines = new Map();
  const usedRoles = new Set();
  const usedNames = new Set();
  const usedTags = new Set();
  let covered = 0;
  let spent = 0;
  const add = (item) => {
    lines.set(item.code, { ...item, quantity: (lines.get(item.code)?.quantity || 0) + 1 });
    spent += item.price;
  };
  while (covered < people) {
    // Reserve the exact minimum cost of feeding everyone still uncovered.
    const options = mains.filter((item) => spent + item.price + minimum.costs[Math.max(0, people - covered - item.serves)] <= budget);
    const score = (item) => {
      const efficiency = item.serves / item.price;
      const novelty = Number(!usedRoles.has(item.role)) + Number(!usedNames.has(item.name));
      const newTags = item.tags.filter((tag) => !usedTags.has(tag)).length;
      const primary = selectedStrategy === "多样性"
        ? novelty * 100 + newTags * 10 + efficiency
        : efficiency * 50000 + novelty * 20 + 40;
      return [primary, -item.price, item.name];
    };
    const chosen = selectedStrategy === "省预算"
      ? minimum.choices[people - covered]
      : options.sort((a, b) => compareTuple(score(b), score(a)))[0];
    add(chosen);
    covered += chosen.serves;
    usedRoles.add(chosen.role);
    usedNames.add(chosen.name);
    chosen.tags.forEach((tag) => usedTags.add(tag));
  }
  const extras = { "均衡": ["side", "drink"], "省预算": [], "多样性": ["side", "drink", "dessert"] };
  for (const role of extras[selectedStrategy]) {
    const options = syntheticMenu.filter((item) => item.role === role && spent + item.price <= budget);
    const chosen = options.sort((a, b) => compareTuple([a.price, a.name], [b.price, b.name]))[0];
    if (chosen) add(chosen);
  }
  return {
    lines: [...lines.values()].sort((a, b) => compareTuple([a.name], [b.name])),
    covered, spent, minimum: minimum.costs[people], feasible: true,
  };
}

function render() {
  const people = Number(document.querySelector("#people").value);
  const budgetYuan = Number(document.querySelector("#budget").value);
  const budget = budgetYuan * 100;
  const stats = intensityStats[intensity];
  const plan = buildPlan(people, budget, strategy);
  currentReceipt = { people, budget, stats, plan, intensity, strategy };

  document.querySelector("#people-value").value = `${people} 人`;
  document.querySelector("#budget-value").value = `¥${budgetYuan}`;
  document.querySelector("#commit-count").textContent = stats.commits;
  document.querySelector("#file-count").textContent = stats.files;
  document.querySelector("#maker-count").textContent = people;
  document.querySelector("#receipt-meta").textContent = `${stats.commits} commits · ${stats.files} files · ${people} makers`;
  document.querySelector("#plan-label").textContent = `${strategy}方案`;
  document.querySelector("#coverage").textContent = plan.feasible ? `${plan.covered} 人份 / ${people} 人用餐` : `尚未生成 ${people} 人方案`;
  document.querySelector("#budget-state").textContent = plan.feasible ? `预算剩余 ${money(budget - plan.spent)}` : `还需 ${money(plan.minimum - budget)}`;
  document.querySelector("#receipt-total").textContent = plan.feasible ? money(plan.spent) : "—";
  document.querySelector("#download-receipt").disabled = !plan.feasible;
  document.querySelector("#copy-share").disabled = !plan.feasible;
  document.querySelector("#share-status").textContent = "";
  document.querySelector("#copy-fallback").hidden = true;

  const container = document.querySelector("#receipt-lines");
  container.replaceChildren();
  for (const line of plan.lines) {
    const row = document.createElement("div");
    row.className = "receipt-line";
    const label = document.createElement("span");
    label.textContent = `${line.name} × ${line.quantity}`;
    const price = document.createElement("span");
    price.textContent = money(line.price * line.quantity);
    row.append(label, price);
    container.append(row);
  }
  if (!plan.feasible) {
    container.textContent = `当前示例菜单至少需要 ${money(plan.minimum)} 才能覆盖 ${people} 人。请提高预算或减少人数。`;
  }
}

function shareText(receipt) {
  const { people, budget, stats, plan, strategy: selectedStrategy } = receipt;
  return [
    "代码已经 Ship，庆功餐也安排上了 🍔",
    `我用 Ship a Big Mac 试玩了一桌 ${people} 人的发版餐：${selectedStrategy}方案，示例合计 ${money(plan.spent)}，预算 ${money(budget)}。`,
    `示例 Release：${stats.commits} commits · ${stats.files} files。`,
    ...plan.lines.map((line) => `${line.name} × ${line.quantity} · ${money(line.price * line.quantity)}`),
    "这是离线虚构 Demo，餐品与价格均为示例，未经 MCP 核价，也没有下单。",
    `免费在线试玩：${playgroundUrl}`,
    `开源项目：${projectUrl}`,
    "如果这个创意对你有用，欢迎在 GitHub 点一颗 Star。",
  ].join("\n");
}

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[character]);
}

function receiptSvg(receipt) {
  const { people, budget, stats, plan, strategy: selectedStrategy } = receipt;
  const totalY = 274 + plan.lines.length * 38;
  const height = totalY + 244;
  const text = (x, y, content, attrs = "") => `<text x="${x}" y="${y}" ${attrs}>${escapeXml(content)}</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="${height}" viewBox="0 0 640 ${height}" role="img" aria-label="Ship a Big Mac 虚构演示小票">
<rect width="640" height="${height}" rx="18" fill="#fffaf0"/>
<g font-family="system-ui, -apple-system, 'Microsoft YaHei', sans-serif" fill="#1f2328" font-size="17">
${text(32, 55, "SHIP A BIG MAC", 'font-size="30" font-weight="800" fill="#c82820"')}
${text(32, 89, "发版就吃巨无霸 · SYNTHETIC DEMO", 'font-size="16"')}
<path d="M32 112H608" stroke="#7d8791" stroke-dasharray="5 5"/>
${text(32, 144, "rocket-checkout / v2.4.0（示例 Release）")}
${text(32, 177, `${stats.commits} commits · ${stats.files} files · ${people} makers`)}
<rect x="32" y="197" width="576" height="42" rx="7" fill="#ffdf59"/>
${text(46, 224, `${selectedStrategy}方案 · ${plan.covered} 人份 / ${people} 人用餐`)}
${plan.lines.map((line, index) => text(32, 274 + index * 38, `${line.name} × ${line.quantity}`) + text(608, 274 + index * 38, money(line.price * line.quantity), 'text-anchor="end"')).join("\n")}
<path d="M32 ${totalY - 12}H608" stroke="#7d8791" stroke-dasharray="5 5"/>
${text(32, totalY + 25, "示例合计", 'font-size="22" font-weight="700"')}
${text(608, totalY + 25, money(plan.spent), 'text-anchor="end" font-size="28" font-weight="800"')}
${text(32, totalY + 58, `预算 ${money(budget)} · 剩余 ${money(budget - plan.spent)}`, 'font-size="15"')}
${text(32, totalY + 96, "虚构餐品与价格 · 未经 MCP 核价 · 未下单", 'font-size="16" font-weight="700" fill="#c82820"')}
${text(32, totalY + 122, "MENU_SUM_NOT_MCP_QUOTED · 非麦当劳官方产品", 'font-size="13"')}
<a href="${playgroundUrl}">${text(32, totalY + 158, `在线试玩：${playgroundUrl}`, 'font-size="13" fill="#165db2"')}</a>
<a href="${projectUrl}">${text(32, totalY + 184, `GitHub：${projectUrl}`, 'font-size="13" fill="#165db2"')}</a>
${text(32, totalY + 216, "喜欢这个创意？欢迎在 GitHub 点一颗 Star。", 'font-size="15"')}
</g></svg>`;
}

async function copyText(button, content, statusSelector) {
  // Capture the element before awaiting: Event.currentTarget is then cleared.
  const status = document.querySelector(statusSelector);
  button.disabled = true;
  try {
    await navigator.clipboard.writeText(content);
    status.textContent = "已复制，可以粘贴分享。";
  } catch {
    const fallback = document.querySelector("#copy-fallback");
    const textarea = document.querySelector("#copy-text");
    textarea.value = content;
    fallback.hidden = false;
    textarea.focus();
    textarea.select();
    status.textContent = "浏览器未允许自动复制，请复制下方已选中的文字。";
  } finally {
    button.disabled = button.id === "copy-share" && !currentReceipt.plan.feasible;
  }
}

function bindSelection(attribute, update) {
  const buttons = document.querySelectorAll(`[${attribute}]`);
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      update(button.getAttribute(attribute));
      buttons.forEach((item) => {
        item.classList.toggle("active", item === button);
        item.setAttribute("aria-pressed", String(item === button));
      });
      render();
    });
  });
}

bindSelection("data-intensity", (value) => { intensity = value; });
bindSelection("data-strategy", (value) => { strategy = value; });
document.querySelector("#people").addEventListener("input", render);
document.querySelector("#budget").addEventListener("input", render);
document.querySelector("#planner-form").addEventListener("submit", (event) => {
  event.preventDefault();
  render();
});
document.querySelector("#copy-command").addEventListener("click", (event) => {
  copyText(event.currentTarget, `git clone ${projectUrl}.git\ncd ship-a-big-mac\npython -m ship_a_big_mac demo`, "#command-status");
});
document.querySelector("#copy-share").addEventListener("click", (event) => {
  if (currentReceipt.plan.feasible) copyText(event.currentTarget, shareText(currentReceipt), "#share-status");
});
document.querySelector("#download-receipt").addEventListener("click", () => {
  if (!currentReceipt.plan.feasible) return;
  const blob = new Blob([receiptSvg(currentReceipt)], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `release-receipt-${currentReceipt.people}p-synthetic.svg`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  document.querySelector("#share-status").textContent = "已生成 SVG 小票，可用浏览器打开后截图分享。";
});

render();
