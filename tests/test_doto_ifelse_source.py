import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "agents" / "doto_ifelse_strength" / "playerAI.cpp"


class DotoIfElseSourceTest(unittest.TestCase):
    def test_policy_declares_all_tactical_states(self):
        source = SOURCE.read_text()
        for state in ("RECOVER", "ESCORT", "GUARD", "STEAL", "PRESSURE"):
            self.assertIn(state, source)
        self.assertIn("RUNE: opportunistic pickup", source)
        self.assertIn("PRESSURE: four attackers", source)
        self.assertIn("attackWaypoint", source)
        self.assertIn("if (myFac() == 0) return enemyCrystal;", source)
        self.assertLess(
            source.index("bool openArea"), source.index("const int *d = bfsFrom")
        )
        self.assertIn("D0(pos, target) <= 20.0", source)
        self.assertIn("Point(82.5, 70.0)", source)
        self.assertNotIn("rand(", source)
        self.assertNotIn("srand(", source)


if __name__ == "__main__":
    unittest.main()
