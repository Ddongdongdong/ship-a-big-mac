const syntheticMenu = [
  { name: "示例·双人发版桶", price: 4990, serves: 2, role: "meal" },
  { name: "示例·经典汉堡套餐", price: 3290, serves: 1, role: "combo" },
  { name: "示例·香辣鸡腿套餐", price: 2990, serves: 1, role: "combo" },
  { name: "示例·分享小食", price: 1850, serves: 0, role: "side" },
  { name: "示例·无糖饮料", price: 900, serves: 0, role: "drink" },
  { name: "示例·庆功甜品", price: 1250, serves: 0, role: "dessert" },
];

const intensityStats = {
  hotfix: { commits: 3, files: 4 },
  regular: { commits: 11, files: 18 },
  major: { commits: 24, files: 37 },
};

let intensity = "major";

function money(cents) {
  return `¥${(cents / 100).toFixed(2)}`;
}

function buildPlan(people, budget) {
  const mains = syntheticMenu.filter((item) => item.serves > 0);
  const lines = new Map();
  let covered = 0;
  let spent = 0;
  while (covered < people) {
    const options = mains.filter((item) => spent + item.price <= budget);
    if (!options.length) break;
    const chosen = options.sort((a, b) => (b.serves / b.price) - (a.serves / a.price))[0];
    lines.set(chosen.name, { ...chosen, quantity: (lines.get(chosen.name)?.quantity || 0) + 1 });
    spent += chosen.price;
    covered += chosen.serves;
  }
  for (const role of ["side", "drink"]) {
    const item = syntheticMenu.find((candidate) => candidate.role === role);
    if (covered >= people && item && spent + item.price <= budget) {
      lines.set(item.name, { ...item, quantity: 1 });
      spent += item.price;
    }
  }
  return { lines: [...lines.values()], covered, spent };
}

function render() {
  const people = Number(document.querySelector("#people").value);
  const budgetYuan = Number(document.querySelector("#budget").value);
  const budget = budgetYuan * 100;
  const stats = intensityStats[intensity];
  const plan = buildPlan(people, budget);

  document.querySelector("#people-value").value = `${people} 人`;
  document.querySelector("#budget-value").value = `¥${budgetYuan}`;
  document.querySelector("#commit-count").textContent = stats.commits;
  document.querySelector("#file-count").textContent = stats.files;
  document.querySelector("#maker-count").textContent = people;
  document.querySelector("#receipt-meta").textContent = `${stats.commits} commits · ${stats.files} files · ${people} makers`;
  document.querySelector("#coverage").textContent = `覆盖 ${Math.min(plan.covered, people)} / ${people} 人`;
  document.querySelector("#budget-state").textContent = plan.covered >= people ? `预算剩余 ${money(budget - plan.spent)}` : "预算不足";
  document.querySelector("#receipt-total").textContent = money(plan.spent);

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
  if (!plan.lines.length) {
    container.textContent = "当前预算无法覆盖任何一份示例正餐。";
  }
}

document.querySelectorAll("[data-intensity]").forEach((button) => {
  button.addEventListener("click", () => {
    intensity = button.dataset.intensity;
    document.querySelectorAll("[data-intensity]").forEach((item) => {
      const selected = item === button;
      item.classList.toggle("active", selected);
      item.setAttribute("aria-pressed", String(selected));
    });
    render();
  });
});

document.querySelector("#people").addEventListener("input", render);
document.querySelector("#budget").addEventListener("input", render);
document.querySelector("#planner-form").addEventListener("submit", (event) => {
  event.preventDefault();
  render();
});
document.querySelector("#copy-command").addEventListener("click", async (event) => {
  try {
    await navigator.clipboard.writeText("python -m ship_a_big_mac demo");
    event.currentTarget.textContent = "已复制";
  } catch {
    event.currentTarget.textContent = "请手动复制";
  }
});

render();
