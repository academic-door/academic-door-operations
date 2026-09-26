import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_public_manifest import build_manifest


class PublicManifestTests(unittest.TestCase):
    def test_manifest_allows_only_latest_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "latest.json").write_text("{}", encoding="utf-8")
            (root / "latest.md").write_text("# ok", encoding="utf-8")
            manifest = build_manifest(root)
            self.assertEqual(
                [item["name"] for item in manifest["files"]],
                ["latest.json", "latest.md"],
            )
            self.assertNotIn("github", json.dumps(manifest).lower())
            self.assertNotIn("owner", json.dumps(manifest).lower())

    def test_manifest_rejects_any_extra_raw_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "latest.json").write_text("{}", encoding="utf-8")
            (root / "latest.md").write_text("# ok", encoding="utf-8")
            (root / "raw.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_manifest(root)


if __name__ == "__main__":
    unittest.main()
