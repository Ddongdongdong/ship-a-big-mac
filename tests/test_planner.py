import unittest

from ship_a_big_mac.planner import MenuItem, apply_mcp_quote, plan_feasts, yuan_to_cents


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.menu = [
            MenuItem("A", "双人组合", 3000, serves=2, role="meal", tags=("share",)),
            MenuItem("B", "单人套餐", 1800, serves=1, role="combo", tags=("burger",)),
            MenuItem("C", "分享小食", 1000, serves=1, role="side", tags=("share",)),
        ]

    def test_plans_cover_people_and_budget(self) -> None:
        plans = plan_feasts(self.menu, people=3, budget_cents=5000)
        self.assertTrue(plans)
        for plan in plans:
            self.assertGreaterEqual(plan.total_serves, 3)
            self.assertLessEqual(plan.quote_total_cents, 5000)
            self.assertEqual(plan.quote_source, "MENU_SUM_NOT_MCP_QUOTED")

    def test_impossible_budget_is_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "budget cannot cover"):
            plan_feasts(self.menu, people=10, budget_cents=500)

    def test_apply_quote_changes_provenance(self) -> None:
        plan = plan_feasts(self.menu, people=2, budget_cents=4000)[0]
        quoted = apply_mcp_quote(plan, total_cents=2875, quote_id="quote-demo")
        self.assertEqual(quoted.quote_total_cents, 2875)
        self.assertEqual(quoted.quote_source, "MCD_MCP_CALCULATE_PRICE")
        self.assertEqual(quoted.quote_id, "quote-demo")

    def test_yuan_rounding(self) -> None:
        self.assertEqual(yuan_to_cents("33.55"), 3355)


if __name__ == "__main__":
    unittest.main()
