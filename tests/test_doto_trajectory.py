import ast
import json
import math
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.doto_trajectory import (
    TrajectoryError,
    analyze_replay,
    load_frames,
    parse_balls,
    parse_humans,
)


def human(
    number: int,
    x: float,
    y: float,
    *,
    hp: float = 100,
    death_time: int = -1,
) -> list[float | int]:
    return [number, x, y, hp, 1000, 0, 1000, 0, 0, death_time, 0]


def replay_frames() -> list[dict]:
    return [
        {"frame": 0, "map": 0},
        {
            "frame": 1,
            "humans": str(
                [
                    human(0, 0, 0),
                    human(1, 10, 0),
                    human(2, 0, 10),
                    human(3, 10, 10),
                ]
            ),
            "balls": str([[1, 0, -1, 0], [9, 10, -1, 1]]),
            "events": "[]",
            "scores": "[0.0, 0.0]",
        },
        {
            "frame": 2,
            "humans": str(
                [
                    human(0, 3, 4),
                    human(1, 9, 0),
                    human(2, 0, 10),
                    human(3, 10, 10),
                ]
            ),
            "balls": str([[3, 4, 0, 0], [9, 10, -1, 1]]),
            "events": "[[5, 0]]",
            "scores": "[1.0, 0.0]",
        },
        {
            "frame": 3,
            "humans": str(
                [
                    human(0, 6, 8, hp=0, death_time=39),
                    human(1, 8, 0),
                    human(2, 0, 10),
                    human(3, 10, 10),
                ]
            ),
            "balls": str([[6, 8, -1, 0], [9, 10, -1, 1]]),
            "events": "[[3, 0]]",
            "scores": "[1.0, 2.0]",
        },
        {"frame": -1, "scores": "[1.0, 2.0]"},
    ]


def write_replay(path: Path, frames: list[dict], *, extra_json: bool = False) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("replay.json", json.dumps(frames))
        archive.writestr("player0_debug.txt", "")
        if extra_json:
            archive.writestr("other.json", "[]")


class ReplayDecodingTest(unittest.TestCase):
    def test_decodes_typed_humans_and_balls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.zip"
            write_replay(path, replay_frames())

            frames = load_frames(path)
            humans = parse_humans(frames[1])
            balls = parse_balls(frames[1])

            self.assertEqual((humans[0].number, humans[0].x, humans[0].y), (0, 0.0, 0.0))
            self.assertTrue(humans[0].alive)
            self.assertEqual((balls[0].x, balls[0].y, balls[0].belong), (1.0, 0.0, -1))

    def test_rejects_ambiguous_zip_and_unsafe_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.zip"
            write_replay(path, replay_frames(), extra_json=True)
            with self.assertRaisesRegex(TrajectoryError, "exactly one JSON"):
                load_frames(path)

            frames = replay_frames()
            frames[1]["humans"] = "__import__('os').system('false')"
            write_replay(path, frames)
            with self.assertRaisesRegex(TrajectoryError, "humans"):
                parse_humans(load_frames(path)[1])

    def test_rejects_non_finite_coordinates(self):
        frame = replay_frames()[1]
        records = ast.literal_eval(frame["humans"])
        records[0][1] = math.inf
        frame["humans"] = records
        with self.assertRaisesRegex(TrajectoryError, "finite"):
            parse_humans(frame)

    def test_accepts_finite_float_cooldowns_from_historical_referee(self):
        frame = replay_frames()[1]
        records = ast.literal_eval(frame["humans"])
        records[0][8] = 0.5
        frame["humans"] = records

        parsed = parse_humans(frame)

        self.assertEqual(parsed[0].fireball_time, 0.5)


class TrajectoryMetricsTest(unittest.TestCase):
    def test_reports_candidate_spatial_and_behavior_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.zip"
            write_replay(path, replay_frames())

            report = analyze_replay(path, candidate_faction=0, grid_size=5.0)

            self.assertEqual(report["frames"], 3)
            self.assertEqual(report["final_scores"], [1.0, 2.0])
            self.assertEqual(report["candidate_faction"], 0)
            units = {unit["number"]: unit for unit in report["units"]}
            self.assertEqual(units[0]["alive_frames"], 2)
            self.assertEqual(units[0]["distance_travelled"], 5.0)
            self.assertEqual(units[0]["ball_carry_frames"], 1)
            self.assertEqual(units[0]["deaths"], 1)
            self.assertEqual(units[0]["death_positions"], [[6.0, 8.0]])
            self.assertEqual(units[0]["enemy_crystal_min_distance"], 8.485281)
            self.assertEqual(units[0]["enemy_crystal_closest_frame"], 2)
            self.assertEqual(units[0]["enemy_crystal_closest_hp"], 100.0)
            self.assertEqual(units[2]["stationary_ratio"], 1.0)
            self.assertEqual(report["death_heatmap"], [{"cell": [1, 1], "count": 1}])
            self.assertEqual(
                report["top_occupancy_cells"][:2],
                [
                    {"cell": [0, 2], "frames": 3},
                    {"cell": [0, 0], "frames": 2},
                ],
            )
            self.assertEqual(report["route_revisit_ratio"], 0.6)
            self.assertEqual(report["nearest_enemy_distance"]["samples"], 5)
            self.assertEqual(report["nearest_ball_distance"]["samples"], 5)

    def test_maps_faction_one_units(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.zip"
            write_replay(path, replay_frames())

            report = analyze_replay(path, candidate_faction=1)

            self.assertEqual([unit["number"] for unit in report["units"]], [1, 3])

    def test_rejects_invalid_analysis_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.zip"
            write_replay(path, replay_frames())
            with self.assertRaisesRegex(ValueError, "candidate_faction"):
                analyze_replay(path, candidate_faction=2)
            with self.assertRaisesRegex(ValueError, "grid_size"):
                analyze_replay(path, candidate_faction=0, grid_size=0)


class TrajectoryCliTest(unittest.TestCase):
    def test_cli_emits_json_and_reports_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.zip"
            write_replay(path, replay_frames())
            command = [
                sys.executable,
                str(ROOT / "tools" / "doto_trajectory.py"),
                str(path),
                "--candidate-faction",
                "0",
                "--grid-size",
                "5",
            ]

            completed = subprocess.run(command, text=True, capture_output=True, check=False)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["candidate_faction"], 0)

            path.write_text("not a zip")
            failed = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(failed.returncode, 2)
            self.assertRegex(failed.stderr, r"^error: ")


if __name__ == "__main__":
    unittest.main()
