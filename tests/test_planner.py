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

    def test_feasible_budget_survives_greedy_dead_end(self) -> None:
        menu = [
            MenuItem("A", "Three-person meal", 4000, serves=3, tags=("share",)),
            MenuItem("B", "Two-person meal", 3000, serves=2),
        ]
        # A has the best cost per person and a variety bonus, but leaves too
        # little money for a fourth person. Two B meals exactly fit the budget.
        plans = plan_feasts(menu, people=4, budget_cents=6000)
        self.assertTrue(plans)
        for plan in plans:
            self.assertEqual(plan.total_serves, 4)
            self.assertEqual(plan.quote_total_cents, 6000)
            self.assertEqual([(line.code, line.quantity) for line in plan.lines], [("B", 2)])

    def test_savings_plan_uses_exact_total_instead_of_price_per_person(self) -> None:
        plans = plan_feasts(self.menu, people=3, budget_cents=7000)
        savings = next(plan for plan in plans if plan.strategy == "省预算")
        self.assertEqual(savings.quote_total_cents, 4800)
        self.assertEqual(savings.total_serves, 3)
        self.assertEqual({line.code: line.quantity for line in savings.lines}, {"A": 1, "B": 1})
        self.assertGreater(len(plans), 1)

    def test_minimum_budget_counts_whole_meals_and_excludes_sides(self) -> None:
        menu = [
            MenuItem("A", "Two-person meal", 3000, serves=2),
            MenuItem("B", "Cheap side", 1, serves=10, role="side"),
            MenuItem("C", "Unavailable meal", 100, serves=3, available=False),
        ]
        with self.assertRaisesRegex(ValueError, "minimum menu total is .*60.00"):
            plan_feasts(menu, people=3, budget_cents=5000)
        plans = plan_feasts(menu, people=3, budget_cents=6000)
        self.assertEqual(plans[0].quote_total_cents, 6000)
        self.assertEqual(plans[0].total_serves, 4)

    def test_no_meal_or_combo_cannot_cover_people(self) -> None:
        with self.assertRaisesRegex(ValueError, "no meal or combo"):
            plan_feasts([MenuItem("A", "Side", 100, serves=5, role="side")], people=1, budget_cents=1000)

    def test_apply_quote_changes_provenance(self) -> None:
        plan = plan_feasts(self.menu, people=2, budget_cents=4000)[0]
        quoted = apply_mcp_quote(plan, total_cents=2875, quote_id="quote-demo")
        self.assertEqual(quoted.quote_total_cents, 2875)
        self.assertEqual(quoted.quote_source, "MCD_MCP_CALCULATE_PRICE")
        self.assertEqual(quoted.quote_id, "quote-demo")

    def test_quote_above_budget_is_rejected_without_changing_plan(self) -> None:
        plan = plan_feasts(self.menu, people=2, budget_cents=4000)[0]
        with self.assertRaisesRegex(ValueError, "exceeds budget"):
            apply_mcp_quote(plan, total_cents=4001)
        self.assertEqual(plan.quote_source, "MENU_SUM_NOT_MCP_QUOTED")

    def test_quote_equal_to_budget_is_allowed(self) -> None:
        plan = plan_feasts(self.menu, people=2, budget_cents=4000)[0]
        quoted = apply_mcp_quote(plan, total_cents=4000)
        self.assertEqual(quoted.remaining_cents, 0)

    def test_yuan_rounding(self) -> None:
        self.assertEqual(yuan_to_cents("33.55"), 3355)


if __name__ == "__main__":
    unittest.main()
