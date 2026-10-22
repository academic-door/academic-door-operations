import copy
import json
import unittest
from pathlib import Path

from scripts.render_dashboard import render
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class DashboardContractTests(unittest.TestCase):
    def test_seed_renders_offline_standalone_dashboard(self):
        markup = render(SEED)
        self.assertIn("<!doctype html>", markup)
        self.assertIn("成本与额度总览", markup)
        self.assertIn('lang="zh-CN"', markup)
        self.assertIn("项目费用总计", markup)
        self.assertIn("估算运行分钟", markup)
        self.assertIn("账单覆盖情况", markup)
        self.assertIn("暂无法计算", markup)
        self.assertIn("GitHub Actions 资源占用", markup)
        self.assertNotIn("<script", markup)
        self.assertNotIn("<link ", markup)
        self.assertNotIn("https://", markup)
        self.assertNotIn("academic-door/", markup)

    def test_untrusted_public_text_is_html_escaped(self):
        snapshot = copy.deepcopy(SEED)
        snapshot["services"][0]["id"] = "<script>alert(1)</script>"
        self.assertEqual(validate(snapshot), [])
        markup = render(snapshot)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", markup)
        self.assertNotIn("<script", markup)

    def test_rejects_private_pointer_before_rendering(self):
        snapshot = copy.deepcopy(SEED)
        snapshot["human_actions"] = ["open academic-door/private-repo"]
        with self.assertRaisesRegex(ValueError, "rejected"):
            render(snapshot)

    def test_does_not_fabricate_total_from_partial_estimates(self):
        snapshot = copy.deepcopy(SEED)
        snapshot["costs"] = [{
            "service": "DeepSeek", "evidence_class": "ESTIMATED", "amount": 0.12,
            "currency": "USD", "period": "CURRENT_MONTH", "observed_at": "2026-10-20T00:00:00Z",
        }]
        markup = render(snapshot)
        self.assertIn("$0.1200", markup)
        self.assertIn("估算（ESTIMATED）", markup)
        self.assertIn("当前公开快照暂无权威数据（UNKNOWN）", markup)
        self.assertNotIn("Total cost $0.1200", markup)


if __name__ == "__main__":
    unittest.main()
