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
        self.assertIn("mt = pickMeteorTarget(i, enc);", source)
        self.assertNotIn("(i <= 1) ? pickMeteorTarget", source)
        self.assertNotIn("Public-b fires continuous volleys", source)
        self.assertIn("TRANSPORT OVERRIDE: possession outranks recovery", source)
        self.assertLess(
            source.index("TRANSPORT OVERRIDE: possession outranks recovery"),
            source.index("RECOVER: carrier cannot flash"),
        )

    def test_dropped_crystal_uses_teamwide_relay_and_counter_steal(self):
        source = SOURCE.read_text()
        self.assertIn("bool relayAvailable", source)
        self.assertIn("int relayLeader = -1;", source)
        self.assertIn("RELAY PICKUP", source)
        self.assertIn("COUNTER-STEAL COMMITMENT", source)
        self.assertIn("(logic->frame <= 1200 || my == 0 ||", source)
        self.assertIn("D0(EU(enc).position, enTarget) > 90.0", source)
        self.assertIn("D0(MU(i).position, ec.position) < 65.0", source)
        self.assertIn("static Point scheduledBonusMeteor", source)
        self.assertIn("429, 609, 847, 1008, 1222", source)
        self.assertIn("377, 545, 753, 978, 1143, 1338", source)
        self.assertIn("349, 517, 725, 950, 1115, 1310", source)
        self.assertIn("425, 605, 843, 1004, 1218", source)
        self.assertIn("5601, 5803", source)
        self.assertIn("5711, 5887", source)
        self.assertIn("5683, 5859", source)
        self.assertIn("5560, 5762", source)
        self.assertIn("if (mt.x < 0 && i >= 2)", source)
        self.assertNotIn("g_lastBonusEnd", source)
        self.assertIn("static bool dodgeFireballToward", source)
        self.assertIn("static bool dodgeOpeningShotToward", source)
        self.assertIn("if (myFac() != 1 || logic->frame > 1200) return false", source)
        self.assertIn("if (i == carrier &&", source)
        self.assertIn("dodgeFireballToward(i, myTarget, safe)", source)
        self.assertIn("i >= 2 && dodgeFireballToward", source)
        self.assertNotIn("SINGLE ESCORT", source)
        self.assertIn("i < 2 && dodgeFireballToward", source)
        self.assertIn("meteor_delay * human_velocity", source)
        self.assertNotIn("BONUS DUEL STAGING", source)
        self.assertNotIn("BONUS FIRE SUPPORT", source)
        self.assertLess(source.index("RELAY PICKUP"), source.index("BONUS CONTROL"))


if __name__ == "__main__":
    unittest.main()
