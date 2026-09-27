import copy
import json
import unittest
from pathlib import Path

from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class PublicSafetyNegativeTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = copy.deepcopy(SEED)

    def assert_rejected(self, mutate):
        mutate(self.snapshot)
        errors = validate(self.snapshot)
        self.assertTrue(errors, "mutation should violate public-safe contract")

    def test_rejects_private_repository_identifier(self):
        self.assert_rejected(
            lambda s: s["human_actions"].append("inspect academic-door/private-repo")
        )

    def test_rejects_issue_pointer(self):
        self.assert_rejected(
            lambda s: s["human_actions"].append("see owner #339")
        )

    def test_rejects_human_account_fact(self):
        self.assert_rejected(
            lambda s: s["human_actions"].append("Human Principal reports no payment")
        )

    def test_rejects_credential_logical_name(self):
        self.assert_rejected(
            lambda s: s["human_actions"].append("JINA_API_KEY configured")
        )

    def test_rejects_secret_bearing_field(self):
        self.snapshot["billing"]["github_actions"]["token"] = "must-not-survive"
        errors = validate(self.snapshot)
        self.assertTrue(any("forbidden public field" in item for item in errors), errors)


if __name__ == "__main__":
    unittest.main()
