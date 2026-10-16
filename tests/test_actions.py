import unittest
from unittest.mock import Mock

from ship_a_big_mac.actions import execute_action, prepare_action, require_success, validate_arguments
from ship_a_big_mac.catalog import READ_ONLY_MCP_TOOLS, WRITE_MCP_TOOLS
from ship_a_big_mac.mcp import MCPError


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.list_tools.return_value = [
            {"name": "auto-bind-coupons", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "cancel-order", "inputSchema": {"type": "object", "properties": {"orderId": {"type": "string"}, "cancelReasonCode": {"type": "string"}}, "required": ["orderId", "cancelReasonCode"]}},
        ]
        self.client.call_tool.return_value = {"structuredContent": {"success": True, "code": 200, "data": {}}}

    def preview(self, arguments=None):
        return prepare_action(self.client, "cancel-order", arguments or {"orderId": "test-order", "cancelReasonCode": "1"}, "https://mcp.mcd.cn")

    def test_preview_does_not_mutate_account(self):
        preview = self.preview()
        self.assertFalse(preview["executed"])
        self.client.call_tool.assert_not_called()

    def test_matching_confirmation_executes_once(self):
        preview = self.preview()
        execute_action(self.client, preview, preview["confirmation_code"])
        self.client.call_tool.assert_called_once_with("cancel-order", preview["arguments"])

    def test_changed_order_requires_new_confirmation(self):
        old = self.preview()
        new = self.preview({"orderId": "different-order", "cancelReasonCode": "1"})
        with self.assertRaisesRegex(ValueError, "confirmation"):
            execute_action(self.client, new, old["confirmation_code"])
        self.client.call_tool.assert_not_called()

    def test_mutated_preview_does_not_reuse_confirmation(self):
        preview = self.preview()
        preview["arguments"]["orderId"] = "tampered"
        with self.assertRaisesRegex(ValueError, "confirmation"):
            execute_action(self.client, preview, preview["confirmation_code"])
        self.client.call_tool.assert_not_called()

    def test_missing_required_argument_stops_before_write(self):
        with self.assertRaisesRegex(ValueError, "orderId"):
            prepare_action(self.client, "cancel-order", {}, "https://mcp.mcd.cn")
        self.client.call_tool.assert_not_called()

    def test_unknown_action_is_rejected_before_connection(self):
        with self.assertRaises(ValueError):
            prepare_action(self.client, "unknown-write", {}, "https://mcp.mcd.cn")
        self.client.list_tools.assert_not_called()

    def test_schema_rejects_bool_for_integer_and_nested_bad_type(self):
        with self.assertRaises(ValueError):
            validate_arguments(True, {"type": "integer"})
        with self.assertRaises(ValueError):
            validate_arguments({"items": ["bad"]}, {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object"}}}})

    def test_write_timeout_is_not_retried(self):
        preview = self.preview()
        self.client.call_tool.side_effect = MCPError("timeout")
        with self.assertRaises(MCPError):
            execute_action(self.client, preview, preview["confirmation_code"])
        self.assertEqual(self.client.call_tool.call_count, 1)

    def test_confirmation_expires(self):
        preview = prepare_action(self.client, "cancel-order", {"orderId": "expiring", "cancelReasonCode": "1"}, "https://mcp.mcd.cn", now=1000)
        with self.assertRaisesRegex(ValueError, "expired"):
            execute_action(self.client, preview, preview["confirmation_code"], now=1000 + 301)
        self.client.call_tool.assert_not_called()

    def test_confirmation_is_one_time(self):
        preview = prepare_action(self.client, "cancel-order", {"orderId": "once", "cancelReasonCode": "1"}, "https://mcp.mcd.cn", now=2000)
        execute_action(self.client, preview, preview["confirmation_code"], now=2001)
        with self.assertRaisesRegex(ValueError, "already been used"):
            execute_action(self.client, preview, preview["confirmation_code"], now=2002)
        self.assertEqual(self.client.call_tool.call_count, 1)

    def test_business_failure_not_presented_as_success(self):
        with self.assertRaises(MCPError):
            require_success({"isError": False, "structuredContent": {"success": False, "code": 500}}, "mall-create-order")

    def test_read_catalog_excludes_every_account_mutation(self):
        self.assertFalse(READ_ONLY_MCP_TOOLS.intersection(WRITE_MCP_TOOLS))

    def order_preview(self, price):
        fields = {"storeCode": {"type": "string"}, "orderType": {"type": "integer"}, "beType": {"type": "integer"}, "items": {"type": "array"}}
        self.client.list_tools.return_value = [
            {"name": "create-order", "inputSchema": {"type": "object", "properties": {**fields, "takeWayCode": {"type": "string"}}, "required": ["storeCode", "orderType", "beType"]}},
            {"name": "calculate-price", "inputSchema": {"type": "object", "properties": fields}},
        ]
        products = [{"productCode": "A", "quantity": 1}]
        self.client.call_tool.return_value = {"structuredContent": {"success": True, "code": 200, "data": {"price": price, "productList": products, "takeWayList": [{"code": "pickup"}]}}}
        arguments = {"storeCode": "test-store", "orderType": 1, "beType": 1, "takeWayCode": "pickup", "items": products}
        return prepare_action(self.client, "create-order", arguments, "https://mcp.mcd.cn")

    def test_order_preview_quotes_without_creating_order(self):
        preview = self.order_preview(3000)
        self.assertEqual(preview["quote_total_cents"], 3000)
        self.assertEqual(self.client.call_tool.call_args.args[0], "calculate-price")
        self.assertNotIn("takeWayCode", self.client.call_tool.call_args.args[1])

    def test_changed_price_invalidates_order_confirmation(self):
        before = self.order_preview(3000)
        after = self.order_preview(3500)
        self.client.call_tool.reset_mock()
        with self.assertRaises(ValueError):
            execute_action(self.client, after, before["confirmation_code"])
        self.client.call_tool.assert_not_called()

    def test_order_execution_requotes_and_rejects_price_change(self):
        preview = self.order_preview(3000)
        # The preview quote was 3000; the execution-time quote changes to 3500.
        self.client.call_tool.reset_mock()
        self.client.call_tool.return_value = {"structuredContent": {"success": True, "code": 200, "data": {"price": 3500, "productList": [{"productCode": "A", "quantity": 1}], "takeWayList": [{"code": "pickup"}]}}}
        with self.assertRaisesRegex(ValueError, "price changed"):
            execute_action(self.client, preview, preview["confirmation_code"])
        self.assertEqual(self.client.call_tool.call_count, 1)
        self.assertEqual(self.client.call_tool.call_args.args[0], "calculate-price")


if __name__ == "__main__":
    unittest.main()
