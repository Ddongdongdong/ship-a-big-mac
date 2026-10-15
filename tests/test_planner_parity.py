"""Run the real browser planner under Node against the Python planner and shared cases."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from ship_a_big_mac.planner import MenuItem, plan_feasts

ROOT = Path(__file__).resolve().parents[1]


class PlannerParityTests(unittest.TestCase):
    def test_generated_web_fixture_is_current(self):
        process = subprocess.run([sys.executable, str(ROOT / "scripts/sync_demo_data.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is needed for browser/Python parity; CI installs Node")
    def test_browser_and_python_match_for_grid_and_regressions(self):
        fixture = json.loads((ROOT / "ship_a_big_mac/data/demo-menu.synthetic.json").read_text(encoding="utf-8"))
        cases = [{"people": people, "budget": budget * 100, "menu": fixture} for people in range(1, 13) for budget in range(60, 501, 10)]
        cases.extend(json.loads((ROOT / "tests/fixtures/planner-cases.json").read_text(encoding="utf-8")))
        javascript = r'''
const fs = require('fs');
const {buildPlan} = require('./docs/planner.js');
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = cases.map(c => {
  const plans = [], seen = new Set();
  for (const strategy of ['均衡', '省预算', '多样性']) {
    const p = buildPlan(c.people, c.budget, strategy, c.menu);
    if (!p.feasible) continue;
    const lines = p.lines.map(l => [l.code, l.quantity]).sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:0);
    const signature = JSON.stringify(lines);
    if (seen.has(signature)) continue;
    seen.add(signature);
    plans.push({strategy, total:p.spent, serves:p.covered, lines});
  }
  return plans;
});
process.stdout.write(JSON.stringify(results));
'''
        process = subprocess.run([shutil.which("node"), "-e", javascript], input=json.dumps(cases), capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
        self.assertEqual(process.returncode, 0, process.stderr)
        actual = json.loads(process.stdout)
        self.assertEqual(len(actual), len(cases))
        for index, (case, web) in enumerate(zip(cases, actual)):
            menu = [MenuItem.from_dict(item) for item in case["menu"]["items"]]
            try:
                plans = plan_feasts(menu, people=case["people"], budget_cents=case["budget"])
                expected = [{"strategy": p.strategy, "total": p.quote_total_cents, "serves": p.total_serves, "lines": sorted([[l.code, l.quantity] for l in p.lines])} for p in plans]
            except ValueError:
                expected = []
            with self.subTest(case=index, people=case["people"], budget=case["budget"]):
                self.assertEqual(web, expected)
                if "expected" in case:
                    self.assertEqual(web, case["expected"])


if __name__ == "__main__":
    unittest.main()
