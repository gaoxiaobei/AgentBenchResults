import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "agents" / "doto_ifelse_strength" / "playerAI.cpp"


class DotoIfElseSourceTest(unittest.TestCase):
    def test_policy_declares_all_tactical_states(self):
        source = SOURCE.read_text()
        for state in ("RECOVER", "ESCORT", "BONUS CONTROL", "ATTACK"):
            self.assertIn(state, source)
        self.assertLess(
            source.index("bool openArea"), source.index("const int *d = bfsFrom")
        )
        self.assertIn("if (openArea && D0(pos, target) > 0.01)", source)
        self.assertNotIn("rand(", source)
        self.assertNotIn("srand(", source)

    def test_normal_roles_control_bonuses_and_keep_attackers_armed(self):
        source = SOURCE.read_text()
        self.assertIn("BONUS CONTROL: mirror the strong opponent", source)
        self.assertIn("logic->map.bonus_places[i]", source)
        self.assertIn("ATTACK: three armed crystal runners", source)
        self.assertIn("int attackLeader = -1;", source)
        self.assertIn("static Point crystalRunnerTarget", source)
        self.assertIn("Point center = Point(170.0, 150.0);", source)
        self.assertIn("Point(82.5, 70.0)", source)
        self.assertIn("Point(237.5, 262.0)", source)
        self.assertIn("D0(MU(i).position, ec.position) - MU(i).hp * 0.8", source)
        self.assertIn("ATTACK SUPPORT: screen the leader", source)
        self.assertIn("nearestEnemy(MU(attackLeader).position)", source)
        self.assertIn("Point mt = pickMeteorTarget(i, enc);", source)
        self.assertNotIn("(i <= 1) ? pickMeteorTarget", source)
        self.assertNotIn("Public-b fires continuous volleys", source)
        self.assertIn("TRANSPORT OVERRIDE: possession outranks recovery", source)
        self.assertLess(
            source.index("TRANSPORT OVERRIDE: possession outranks recovery"),
            source.index("RECOVER: carrier cannot flash"),
        )


if __name__ == "__main__":
    unittest.main()
