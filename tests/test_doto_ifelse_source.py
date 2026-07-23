import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "agents" / "doto_ifelse_strength" / "playerAI.cpp"


class DotoIfElseSourceTest(unittest.TestCase):
    def test_policy_declares_all_tactical_states(self):
        source = SOURCE.read_text()
        for state in ("RECOVER", "ESCORT", "STEAL", "PRESSURE"):
            self.assertIn(state, source)
        self.assertIn("PRESSURE: four attackers", source)
        self.assertLess(
            source.index("bool openArea"), source.index("const int *d = bfsFrom")
        )
        self.assertNotIn("rand(", source)
        self.assertNotIn("srand(", source)


if __name__ == "__main__":
    unittest.main()
