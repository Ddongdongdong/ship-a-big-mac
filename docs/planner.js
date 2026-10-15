(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./demo-menu.synthetic.json"));
  } else {
    root.FeastPlanner = factory(root.DEMO_MENU);
    root.buildPlan = root.FeastPlanner.buildPlan;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (defaultFixture) {
  "use strict";

  function compareTuple(left, right) {
    for (let index = 0; index < left.length; index += 1) {
      if (left[index] < right[index]) return -1;
      if (left[index] > right[index]) return 1;
    }
    return 0;
  }

  function normalizeMenu(fixture) {
    const source = Array.isArray(fixture) ? fixture : fixture?.items;
    if (!source) throw new Error("The synthetic menu fixture has not loaded.");
    return source.filter((item) => item.available !== false && item.price_cents > 0).map((item) => ({
      code: String(item.code || ""), name: String(item.name || "未命名餐品"),
      price: Number(item.price_cents), serves: Math.max(1, Number(item.serves) || 1),
      role: item.role || "meal", tags: item.tags || [],
    }));
  }

  function minimumCover(mains, people) {
    const costs = [0];
    const choices = [null];
    for (let remaining = 1; remaining <= people; remaining += 1) {
      const key = (item) => [item.price + costs[Math.max(0, remaining - item.serves)], item.price, item.name, item.code];
      const chosen = [...mains].sort((a, b) => compareTuple(key(a), key(b)))[0];
      costs.push(chosen.price + costs[Math.max(0, remaining - chosen.serves)]);
      choices.push(chosen);
    }
    return { costs, choices };
  }

  // Pure planner. Money is in integer cents; themes never enter this function.
  function buildPlan(people, budget, strategy = "均衡", fixture = defaultFixture) {
    if (!Number.isInteger(people) || people < 1 || people > 50) throw new RangeError("people must be between 1 and 50");
    if (!Number.isInteger(budget) || budget <= 0) throw new RangeError("budget must be positive integer cents");
    if (!["均衡", "省预算", "多样性"].includes(strategy)) throw new RangeError("Unknown strategy");
    const menu = normalizeMenu(fixture);
    const mains = menu.filter((item) => ["meal", "combo"].includes(item.role));
    if (!mains.length) throw new Error("menu has no meal or combo items that can cover a person");
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
      const affordable = mains.filter((item) => spent + item.price + minimum.costs[Math.max(0, people - covered - item.serves)] <= budget);
      const score = (item) => {
        const efficiency = item.serves / item.price;
        const novelty = Number(!usedRoles.has(item.role)) + Number(!usedNames.has(item.name));
        const newTags = item.tags.filter((tag) => !usedTags.has(tag)).length;
        const primary = strategy === "多样性" ? novelty * 100 + newTags * 10 + efficiency : efficiency * 50000 + novelty * 20 + 40;
        return [primary, -item.price, item.name];
      };
      const chosen = strategy === "省预算" ? minimum.choices[people - covered] : affordable.sort((a, b) => compareTuple(score(b), score(a)))[0];
      add(chosen);
      covered += chosen.serves;
      usedRoles.add(chosen.role);
      usedNames.add(chosen.name);
      chosen.tags.forEach((tag) => usedTags.add(tag));
    }
    const extras = { "均衡": ["side", "drink"], "省预算": [], "多样性": ["side", "drink", "dessert"] };
    for (const role of extras[strategy]) {
      const options = menu.filter((item) => item.role === role && spent + item.price <= budget);
      const chosen = options.sort((a, b) => compareTuple([a.price, a.name], [b.price, b.name]))[0];
      if (chosen) add(chosen);
    }
    return { lines: [...lines.values()].sort((a, b) => compareTuple([a.name], [b.name])), covered, spent, minimum: minimum.costs[people], feasible: true };
  }

  return { buildPlan };
});
