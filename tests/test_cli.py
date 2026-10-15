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

from ship_a_big_mac.cli import cmd_mcp_call, cmd_mcp_inspect


class CLITests(unittest.TestCase):
    def test_demo_generates_svg_without_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.svg"
            env = {"PATH": os.environ.get("PATH", "")}
            process = subprocess.run(
                [sys.executable, "-m", "ship_a_big_mac", "demo", "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
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
