import unittest
from dataclasses import replace
from pathlib import Path
import tempfile
import subprocess
import sys
import xml.etree.ElementTree as ET

from ship_a_big_mac.git_release import ReleaseContext
from ship_a_big_mac.planner import FeastPlan, PlanLine, apply_mcp_quote
from ship_a_big_mac.render import render_receipt_svg, render_achievement_svg, write_celebration_html


class RenderTests(unittest.TestCase):
    def test_browser_card_template_is_in_sync(self):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/sync_card_template.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_svg_escapes_content_and_omits_contributors(self) -> None:
        context = ReleaseContext(
            repository="repo<script>",
            branch="main",
            version="v1.0",
            commit_count=4,
            contributor_count=1,
            contributors=("Sensitive Name",),
            files_changed=8,
            insertions=20,
            deletions=3,
            intensity="regular",
            window_days=14,
        )
        base = FeastPlan(
            strategy="均衡",
            people=1,
            budget_cents=5000,
            lines=(PlanLine("A", "餐品 & 饮料", 1, 3000, 1, "combo"),),
            quote_total_cents=3000,
            quote_source="MENU_SUM_NOT_MCP_QUOTED",
        )
        svg = render_receipt_svg(context, apply_mcp_quote(base, total_cents=2880))
        self.assertIn("MCP VERIFIED", svg)
        self.assertIn("repo&lt;script&gt;", svg)
        self.assertIn("餐品 &amp; 饮料", svg)
        self.assertNotIn("Sensitive Name", svg)

    def test_achievement_is_portable_escapes_content_and_preserves_provenance(self):
        context = ReleaseContext("repo<script>", "private-branch", "v3.0.0", 24, 5, ("Private Person",), 37, 10, 2, "major", 14)
        plan = FeastPlan("均衡", 5, 18000, (PlanLine("A", "Test", 5, 3000, 1, "combo"),), 15000, "MENU_SUM_NOT_MCP_QUOTED")
        for scene, heading in (("major", "RELEASE UNLOCKED"), ("hotfix", "HOTFIX HERO"), ("sprint", "SPRINT COMPLETE"), ("comeback", "BACK TO GREEN")):
            with self.subTest(scene=scene):
                svg = render_achievement_svg(context, plan, scene)
                ET.fromstring(svg)
                self.assertIn(heading, svg)
                self.assertIn("SYNTHETIC DEMO", svg)
                self.assertIn("data:image/png;base64,", svg)
                self.assertIn("repo&lt;script&gt;", svg)
                self.assertNotIn("Private Person", svg)
                self.assertNotIn("private-branch", svg)
                self.assertNotIn("MCP VERIFIED", svg)
        self.assertIn("MCP VERIFIED", render_achievement_svg(context, apply_mcp_quote(plan, total_cents=14900)))
        self.assertIn("USER REPORTED", render_achievement_svg(context, replace(plan, quote_source="USER_REPORTED_TOTAL")))
        with tempfile.TemporaryDirectory() as folder:
            output = write_celebration_html(Path(folder) / "card.html", replace(context, repository="</script><script>alert(1)</script>"), plan)
            content = output.read_text(encoding="utf-8")
            self.assertEqual(content.count("<script>"), 1)
            self.assertNotIn("<script>alert", content)


if __name__ == "__main__":
    unittest.main()
