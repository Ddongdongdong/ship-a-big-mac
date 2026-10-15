import unittest

from ship_a_big_mac.git_release import ReleaseContext
from ship_a_big_mac.planner import FeastPlan, PlanLine, apply_mcp_quote
from ship_a_big_mac.render import render_receipt_svg


class RenderTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
