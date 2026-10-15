from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock

from ship_a_big_mac.mcp import MCPError
from ship_a_big_mac.planner import FeastPlan, PlanLine
from ship_a_big_mac.quote import quote_plan, bind_quote_context


class QuotePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = FeastPlan(
            strategy="balanced", people=2, budget_cents=6000,
            lines=(
                PlanLine("meal", "Meal", 2, 2000, 1, "meal"),
                PlanLine("drink", "Drink", 1, 1000, 0, "drink"),
            ),
            quote_total_cents=5000, quote_source="MENU_SUM_NOT_MCP_QUOTED",
        )
        self.arguments = {
            "storeCode": "test-store",
            "items": [{"productCode": "drink", "quantity": 1}, {"productCode": "meal", "quantity": 2}],
        }
        self.result = {"structuredContent": {
            "success": True, "code": 200,
            "data": {"price": 4500, "productList": [
                {"productCode": "meal", "quantity": 2, "subtotal": 4000},
                {"productCode": "drink", "quantity": 1, "subtotal": 1000},
            ]},
        }}
        self.client = Mock()
        self.client.call_tool.return_value = self.result

    def test_live_discount_is_applied_without_requiring_subtotal_sum(self) -> None:
        quoted = quote_plan(self.client, self.plan, self.arguments)
        self.client.call_tool.assert_called_once_with("calculate-price", self.arguments)
        self.assertEqual(quoted.quote_total_cents, 4500)
        self.assertEqual(quoted.quote_source, "MCD_MCP_CALCULATE_PRICE")
        self.assertEqual(quoted.lines, self.plan.lines)
        self.assertEqual(self.plan.quote_total_cents, 5000)

    def test_valid_free_quote_is_accepted(self) -> None:
        self.result["structuredContent"]["data"]["price"] = 0
        self.assertEqual(quote_plan(self.client, self.plan, self.arguments).quote_total_cents, 0)

    def test_context_changes_cannot_reuse_bound_candidate(self):
        original = deepcopy(self.arguments)
        original.update(beType=1, orderType=1, reservationDate="2026-10-15 19:00")
        original["items"][1].update(roundList=[{"round":"1", "comboItemList":[{"code":"default", "quantity":1}]}], couponId="test-coupon")
        bound = bind_quote_context(self.plan, original)
        variants = []
        for key, value in (("storeCode", "new-store"), ("beType", 2), ("orderType", 2), ("reservationDate", "2026-10-16 19:00")):
            changed = deepcopy(original)
            changed[key] = value
            variants.append(changed)
        changed = deepcopy(original)
        changed["items"][1]["couponId"] = "other-coupon"
        variants.append(changed)
        changed = deepcopy(original)
        changed["items"][1]["roundList"][0]["comboItemList"][0]["code"] = "other-choice"
        variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "context changed"):
                quote_plan(self.client, bound, changed)
        self.client.call_tool.assert_not_called()
        quoted = quote_plan(self.client, bound, original)
        self.assertEqual(quoted.quote_context_digest, bound.quote_context_digest)
        self.client.url = "https://different.example"
        with self.assertRaisesRegex(ValueError, "context changed"):
            quote_plan(self.client, quoted, original)

    def test_echoed_context_and_combo_options_are_checked(self):
        self.result["structuredContent"]["data"]["storeCode"] = "different"
        with self.assertRaisesRegex(MCPError, "context"):
            quote_plan(self.client, self.plan, self.arguments)
        del self.result["structuredContent"]["data"]["storeCode"]
        self.arguments["items"][1]["roundList"] = [{"round":"1", "comboItemList":[{"code":"A","quantity":1}]}]
        self.result["structuredContent"]["data"]["productList"][0]["roundList"] = [{"round":"1", "comboItemList":[{"code":"B","quantity":1}]}]
        with self.assertRaisesRegex(MCPError, "options"):
            quote_plan(self.client, self.plan, self.arguments)

    def test_request_mismatch_is_rejected_before_network_call(self) -> None:
        invalid_items = [
            [],
            [{"productCode": "meal", "quantity": 2}],
            self.arguments["items"] + [{"productCode": "drink", "quantity": 1}],
            [{"productCode": "meal", "quantity": 1}, {"productCode": "meal", "quantity": 1},
             {"productCode": "drink", "quantity": 1}],
        ]
        for items in invalid_items:
            with self.subTest(items=items), self.assertRaises(ValueError):
                quote_plan(self.client, self.plan, {"items": items})
        self.client.call_tool.assert_not_called()

    def test_invalid_request_quantity_is_rejected_before_network_call(self) -> None:
        for quantity in (True, False, 0, -1, 2.0, "2", None):
            arguments = deepcopy(self.arguments)
            arguments["items"][1]["quantity"] = quantity
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                quote_plan(self.client, self.plan, arguments)
        self.client.call_tool.assert_not_called()

    def test_invalid_plan_quantity_is_rejected_before_network_call(self) -> None:
        plan = replace(self.plan, lines=(replace(self.plan.lines[0], quantity=True),))
        with self.assertRaises(ValueError):
            quote_plan(self.client, plan, {"items": [{"productCode": "meal", "quantity": True}]})
        self.client.call_tool.assert_not_called()

    def test_text_only_response_cannot_create_verified_quote(self) -> None:
        self.client.call_tool.return_value = {"content": [{"type": "text", "text": "private-customer-data"}]}
        with self.assertRaisesRegex(MCPError, "structuredContent") as error:
            quote_plan(self.client, self.plan, self.arguments)
        self.assertNotIn("private-customer-data", str(error.exception))

    def test_business_failure_is_rejected_even_with_plausible_price(self) -> None:
        for success, code in ((False, 200), (1, 200), (True, 500), (True, "200")):
            self.result["structuredContent"].update(success=success, code=code)
            with self.subTest(success=success, code=code), self.assertRaisesRegex(MCPError, "business"):
                quote_plan(self.client, self.plan, self.arguments)

    def test_invalid_total_is_rejected(self) -> None:
        for price in (True, False, -1, 4500.0, "4500", None):
            self.result["structuredContent"]["data"]["price"] = price
            with self.subTest(price=price), self.assertRaisesRegex(MCPError, "integer cents"):
                quote_plan(self.client, self.plan, self.arguments)

    def test_response_products_must_match_including_duplicate_lines(self) -> None:
        for products in (
            [{"productCode": "meal", "quantity": 2}],
            self.result["structuredContent"]["data"]["productList"] * 2,
            [{"productCode": "other", "quantity": 2}, {"productCode": "drink", "quantity": 1}],
        ):
            self.result["structuredContent"]["data"]["productList"] = products
            with self.subTest(products=products), self.assertRaisesRegex(MCPError, "did not match"):
                quote_plan(self.client, self.plan, self.arguments)

    def test_malformed_response_products_are_rejected(self) -> None:
        for products in (None, {}, [], [{"productCode": "meal", "quantity": True}]):
            self.result["structuredContent"]["data"]["productList"] = products
            with self.subTest(products=products), self.assertRaisesRegex(MCPError, "invalid product list"):
                quote_plan(self.client, self.plan, self.arguments)

    def test_over_budget_quote_is_rejected(self) -> None:
        self.result["structuredContent"]["data"]["price"] = 6001
        with self.assertRaisesRegex(MCPError, "budget"):
            quote_plan(self.client, self.plan, self.arguments)

    def test_transport_tool_error_propagates(self) -> None:
        self.client.call_tool.side_effect = MCPError("MCP tool reported an error: calculate-price")
        with self.assertRaisesRegex(MCPError, "tool reported an error"):
            quote_plan(self.client, self.plan, self.arguments)


if __name__ == "__main__":
    unittest.main()
