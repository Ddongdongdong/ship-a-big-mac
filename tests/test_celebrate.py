import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ship_a_big_mac.celebrate import LivePickup
from ship_a_big_mac.cli import build_parser
from ship_a_big_mac.git_release import ReleaseContext


class CelebrateTests(unittest.TestCase):
    def setUp(self):
        self.context = ReleaseContext("test-repo", "main", "v1", 2, 1, ("Private Person",), 3, 4, 1, "hotfix", 14)

    def test_offline_flow_never_connects_and_writes_shareable_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            args = build_parser().parse_args(["celebrate", "--demo", "--non-interactive", "--scene", "hotfix", "--people", "5", "--budget", "180", "--output-dir", folder])
            with patch("ship_a_big_mac.celebrate.MCPClient") as client, patch("ship_a_big_mac.celebrate.analyze_repository", return_value=self.context), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(args.func(args), 0)
            client.assert_not_called()
            for name in ("release-achievement.svg", "release-receipt.svg", "celebration.html", "celebration.json"):
                content = (Path(folder) / name).read_text(encoding="utf-8")
                self.assertNotIn("Private Person", content)
                self.assertNotIn("MCP VERIFIED", content)
            self.assertIn("HOTFIX HERO", (Path(folder) / "release-achievement.svg").read_text(encoding="utf-8"))

    def _live_client(self, price=3500):
        client = Mock(url="https://mcp.mcd.cn")
        names = ["query-meals", "query-meal-detail", "query-store-coupons", "calculate-price", "query-nearby-stores"]
        client.list_tools.return_value = [{"name": name, "inputSchema": {"type":"object"}} for name in names]
        def call(name, arguments):
            if name == "query-meals":
                data = {"meals": {"A": {"name":"巨无霸三件套", "currentPrice":"30.00"}}}
            elif name == "query-meal-detail":
                data = {"code":"A", "rounds":[{"id":"1", "choices":[{"isDefault":1,"code":"main","quantity":1},{"isDefault":0,"code":"not-default","quantity":1}]}]}
            elif name == "query-store-coupons":
                data = {"privateCoupon":"must-not-appear"}
            elif name == "calculate-price":
                self.assertEqual(arguments["items"][0]["roundList"], [{"round":"1","comboItemList":[{"code":"main","quantity":1}]}])
                data = {"price":price,"productList":[{"productCode":"A","quantity":1}]}
            elif name == "query-nearby-stores":
                data = [{"storeCode":"S","storeName":"Test store","businessStatus":True}]
            else:
                raise AssertionError("unexpected or mutating tool: " + name)
            return {"structuredContent":{"success":True,"code":200,"data":data}}
        client.call_tool.side_effect = call
        return client

    def test_live_flow_reads_menu_defaults_and_quotes_before_writing(self):
        client = self._live_client()
        with tempfile.TemporaryDirectory() as folder:
            args = build_parser().parse_args(["celebrate", "--non-interactive", "--scene", "comeback", "--people", "1", "--budget", "40", "--city", "Test", "--keyword", "Landmark", "--store-code", "S", "--output-dir", folder])
            with patch("ship_a_big_mac.celebrate.MCPClient") as cls, patch("ship_a_big_mac.celebrate.analyze_repository", return_value=self.context), contextlib.redirect_stdout(io.StringIO()):
                cls.return_value.__enter__.return_value = client
                self.assertEqual(args.func(args), 0)
            output = (Path(folder) / "celebration.json").read_text(encoding="utf-8")
            plan = json.loads(output)["plan"]
            self.assertEqual(plan["quote_total_cents"],3500)
            self.assertEqual(len(plan["quote_context_digest"]),64)
            self.assertNotIn("must-not-appear", output)
            self.assertNotIn("Test store",output)
            card = (Path(folder) / "release-achievement.svg").read_text(encoding="utf-8")
            self.assertIn("MCP VERIFIED",card)
            self.assertIn("BACK TO GREEN",card)

    def test_no_verified_candidate_means_no_artifacts(self):
        client = self._live_client(price=4001)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError,"没有候选"):
            LivePickup(client).candidates({"storeCode":"S","beType":1,"orderType":1},1,4000)

    def test_ambiguous_defaults_cannot_be_invented(self):
        for detail in ({}, {"rounds":[]}, {"rounds":[{"id":"1","choices":[{"isDefault":0,"code":"a","quantity":1}]}]}, {"rounds":[{"id":"1","choices":[{"isDefault":1,"code":"a","quantity":True}]}]}):
            with self.subTest(detail=detail), self.assertRaises(ValueError):
                LivePickup.default_rounds(detail)


if __name__ == "__main__":
    unittest.main()
