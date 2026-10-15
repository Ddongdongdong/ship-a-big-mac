from pathlib import Path
from argparse import Namespace
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ship_a_big_mac.cli import build_parser, cmd_mcp_action, cmd_mcp_call, cmd_mcp_inspect, cmd_receipt


class CLITests(unittest.TestCase):
    @patch("ship_a_big_mac.cli.MCPClient")
    def test_action_cli_previews_then_executes_only_confirmed_request(self, client_type):
        client = client_type.return_value.__enter__.return_value
        client.list_tools.return_value = [{"name": "auto-bind-coupons", "inputSchema": {"type": "object", "properties": {}}}]
        client.call_tool.return_value = {"structuredContent": {"success": True, "code": 200, "data": {}}}
        args = build_parser().parse_args(["mcp-action", "auto-bind-coupons"])
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(cmd_mcp_action(args), 0)
        preview, _ = json.JSONDecoder().raw_decode(output.getvalue())
        self.assertFalse(preview["executed"])
        client.call_tool.assert_not_called()
        args.confirm = preview["confirmation_code"]
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(cmd_mcp_action(args), 0)
        client.call_tool.assert_called_once_with("auto-bind-coupons", {})

    @patch("ship_a_big_mac.cli.MCPClient")
    def test_nutrition_shortcut_calls_official_tool(self, client_type):
        client = client_type.return_value.__enter__.return_value
        client.call_tool.return_value = {"structuredContent": {"success": True, "code": 200, "data": []}}
        args = build_parser().parse_args(["nutrition"])
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(args.func(args), 0)
        client.call_tool.assert_called_once_with("list-nutrition-foods", {})

    def _receipt_inputs(self, directory):
        context = Path(directory) / "context.json"
        plan = Path(directory) / "plan.json"
        context.write_text(json.dumps({"repository": "test", "branch": "main", "version": "v1", "commit_count": 1, "contributor_count": 1, "files_changed": 1, "insertions": 1, "deletions": 0, "intensity": "hotfix", "window_days": 14}), encoding="utf-8")
        plan.write_text(json.dumps({"people": 1, "budget_cents": 4000, "quote_source": "MCD_MCP_CALCULATE_PRICE", "quote_total_cents": 1, "lines": [{"code": "A", "name": "Test combo", "quantity": 1, "unit_price_cents": 3000, "serves": 1, "role": "combo"}]}), encoding="utf-8")
        return Namespace(context=str(context), plan=str(plan), index=0, quoted_total=None, quote_id=None, quote_arguments=None, output=str(Path(directory) / "receipt.svg"))

    def test_saved_verification_badge_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._receipt_inputs(directory)
            with patch("sys.stdout", new_callable=io.StringIO):
                cmd_receipt(args)
            svg = Path(args.output).read_text(encoding="utf-8")
            self.assertNotIn("MCP VERIFIED", svg)
            self.assertIn("¥30.00", svg)

    def test_manual_total_is_labeled_user_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._receipt_inputs(directory)
            args.quoted_total = "28.50"
            with patch("sys.stdout", new_callable=io.StringIO):
                cmd_receipt(args)
            svg = Path(args.output).read_text(encoding="utf-8")
            self.assertIn("USER REPORTED", svg)
            self.assertNotIn("MCP VERIFIED", svg)

    @patch("ship_a_big_mac.cli.MCPClient")
    def test_receipt_verifies_live_quote_before_rendering(self, client_type):
        client = client_type.return_value.__enter__.return_value
        client.call_tool.return_value = {"structuredContent": {"success": True, "code": 200, "data": {"price": 2850, "productList": [{"productCode": "A", "quantity": 1}]}}}
        with tempfile.TemporaryDirectory() as directory:
            args = self._receipt_inputs(directory)
            arguments = {"storeCode": "test", "beType": 1, "orderType": 1, "items": [{"productCode": "A", "quantity": 1}]}
            path = Path(directory) / "arguments.json"
            path.write_text(json.dumps(arguments), encoding="utf-8")
            args.quote_arguments = str(path)
            with patch("sys.stdout", new_callable=io.StringIO):
                cmd_receipt(args)
            client.call_tool.assert_called_once_with("calculate-price", arguments)
            svg = Path(args.output).read_text(encoding="utf-8")
            self.assertIn("MCP VERIFIED", svg)
            self.assertIn("¥28.50", svg)

    def test_demo_generates_svg_without_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.svg"
            env = dict(os.environ)
            env.pop("MCD_MCP_TOKEN", None)
            process = subprocess.run(
                [sys.executable, "-m", "ship_a_big_mac", "demo", "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(output.exists())
            self.assertIn("SYNTHETIC DEMO", process.stdout)
            self.assertIn("DEMO · NOT QUOTED", output.read_text(encoding="utf-8"))

    @patch("ship_a_big_mac.cli.MCPClient")
    def test_mcp_inspect_prints_live_schema(self, client_type) -> None:
        client = client_type.return_value.__enter__.return_value
        client.list_tools.return_value = [
            {"name": "query-meals", "inputSchema": {"type": "object"}}
        ]
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            result = cmd_mcp_inspect(Namespace(tool="query-meals", url="https://example.test"))
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["name"], "query-meals")

    @patch("ship_a_big_mac.cli.MCPClient")
    def test_mcp_call_allows_price_calculation(self, client_type) -> None:
        client = client_type.return_value.__enter__.return_value
        client.call_tool.return_value = {"content": [{"type": "text", "text": "quoted"}]}
        with patch("sys.stdout", new_callable=io.StringIO):
            result = cmd_mcp_call(
                Namespace(
                    tool="calculate-price",
                    arguments='{"storeCode":"demo"}',
                    url="https://example.test",
                )
            )
        self.assertEqual(result, 0)
        client.call_tool.assert_called_once_with("calculate-price", {"storeCode": "demo"})

    def test_mcp_call_rejects_write_tools(self) -> None:
        with self.assertRaisesRegex(ValueError, "not allowed in read-only mode"):
            cmd_mcp_call(
                Namespace(tool="create-order", arguments="{}", url="https://example.test")
            )


if __name__ == "__main__":
    unittest.main()
