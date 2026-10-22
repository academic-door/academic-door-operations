import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/operations-probe.yml").read_text(encoding="utf-8")


class OptionalPagesPublishingTests(unittest.TestCase):
    def test_public_pages_export_happens_only_after_public_allowlist_manifest(self):
        validate = WORKFLOW.index("name: Validate public-safe snapshot")
        render = WORKFLOW.index("name: Render standalone public-safe dashboard")
        manifest = WORKFLOW.index("name: Build public artifact manifest")
        upload = WORKFLOW.index("name: Upload verified public dashboard for GitHub Pages")
        self.assertLess(validate, render)
        self.assertLess(render, manifest)
        self.assertLess(manifest, upload)
        self.assertIn("uses: actions/upload-pages-artifact@v4", WORKFLOW)
        self.assertIn("path: public", WORKFLOW)
        self.assertNotIn("path: $RUNNER_TEMP", WORKFLOW)

    def test_pages_requires_opt_in_and_is_not_a_new_collector_permission(self):
        self.assertEqual(WORKFLOW.count("if: vars.OPS_PAGES_PUBLISH_ENABLED == 'true'"), 2)
        probe = WORKFLOW.split("  deploy-pages:", 1)[0]
        deploy = WORKFLOW.split("  deploy-pages:", 1)[1]
        self.assertIn("permissions:\n  contents: read", probe)
        self.assertNotIn("pages: write", probe)
        self.assertNotIn("id-token: write", probe)
        self.assertIn("needs: probe", deploy)
        self.assertIn("pages: write", deploy)
        self.assertIn("id-token: write", deploy)
        self.assertIn("name: github-pages", deploy)
        self.assertIn("uses: actions/deploy-pages@v4", deploy)
        self.assertNotIn("OPS_APP_PRIVATE_KEY", deploy)
        self.assertNotIn("git push", deploy)


if __name__ == "__main__":
    unittest.main()
