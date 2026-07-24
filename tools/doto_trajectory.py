#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import math
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TrajectoryError(RuntimeError):
    """Raised when a Replay cannot support trajectory analysis."""


@dataclass(frozen=True)
class Human:
    number: int
    x: float
    y: float
    hp: float
    meteor_number: float
    meteor_time: float
    flash_number: float
    flash_time: float
    fireball_time: float
    death_time: float
    inv_time: float

    @property
    def alive(self) -> bool:
        return self.death_time == -1


@dataclass(frozen=True)
class Ball:
    x: float
    y: float
    belong: int
    number: int


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TrajectoryError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise TrajectoryError(f"{label} must be finite")
    return result


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TrajectoryError(f"{label} must be an integer")
    return value


def _literal_list(value: Any, label: str) -> list[Any]:
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise TrajectoryError(f"{label} is not a valid literal sequence") from exc
    if not isinstance(value, (list, tuple)):
        raise TrajectoryError(f"{label} must be a sequence")
    return list(value)


def load_frames(path: Path) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as archive:
            members = [
                name for name in archive.namelist() if name.lower().endswith(".json")
            ]
            if len(members) != 1:
                raise TrajectoryError("Replay must contain exactly one JSON member")
            with archive.open(members[0]) as source:
                payload = json.load(source)
    except TrajectoryError:
        raise
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrajectoryError(f"could not read Replay {path}: {exc}") from exc
    if not isinstance(payload, list) or not all(
        isinstance(frame, dict) for frame in payload
    ):
        raise TrajectoryError("Replay must contain a JSON array of frame objects")
    return payload


def parse_humans(frame: dict[str, Any]) -> list[Human]:
    records = _literal_list(frame.get("humans"), "humans")
    humans: list[Human] = []
    for index, raw in enumerate(records):
        record = _literal_list(raw, f"humans[{index}]")
        if len(record) != 11:
            raise TrajectoryError(f"humans[{index}] must contain 11 fields")
        humans.append(
            Human(
                number=_integer(record[0], f"humans[{index}].number"),
                x=_number(record[1], f"humans[{index}].x"),
                y=_number(record[2], f"humans[{index}].y"),
                hp=_number(record[3], f"humans[{index}].hp"),
                meteor_number=_number(record[4], f"humans[{index}].meteor_number"),
                meteor_time=_number(record[5], f"humans[{index}].meteor_time"),
                flash_number=_number(record[6], f"humans[{index}].flash_number"),
                flash_time=_number(record[7], f"humans[{index}].flash_time"),
                fireball_time=_number(record[8], f"humans[{index}].fireball_time"),
                death_time=_number(record[9], f"humans[{index}].death_time"),
                inv_time=_number(record[10], f"humans[{index}].inv_time"),
            )
        )
    return humans


def parse_balls(frame: dict[str, Any]) -> list[Ball]:
    records = _literal_list(frame.get("balls"), "balls")
    balls: list[Ball] = []
    for index, raw in enumerate(records):
        record = _literal_list(raw, f"balls[{index}]")
        if len(record) != 4:
            raise TrajectoryError(f"balls[{index}] must contain 4 fields")
        balls.append(
            Ball(
                x=_number(record[0], f"balls[{index}].x"),
                y=_number(record[1], f"balls[{index}].y"),
                belong=_integer(record[2], f"balls[{index}].belong"),
                number=_integer(record[3], f"balls[{index}].number"),
            )
        )
    return balls


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def _rounded(value: float) -> float:
    return round(value, 6)


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"samples": 0, "mean": None, "p50": None, "p90": None}
    ordered = sorted(values)

    def nearest_rank(quantile: float) -> float:
        index = max(0, math.ceil(quantile * len(ordered)) - 1)
        return _rounded(ordered[index])

    return {
        "samples": len(ordered),
        "mean": _rounded(sum(ordered) / len(ordered)),
        "p50": nearest_rank(0.5),
        "p90": nearest_rank(0.9),
    }


def _events(frame: dict[str, Any]) -> list[list[Any]]:
    events = _literal_list(frame.get("events", []), "events")
    parsed: list[list[Any]] = []
    for index, event in enumerate(events):
        parsed.append(_literal_list(event, f"events[{index}]"))
    return parsed


def _scores(value: Any) -> list[float]:
    scores = _literal_list(value, "scores")
    if len(scores) != 2:
        raise TrajectoryError("scores must contain exactly two values")
    return [_number(score, "score") for score in scores]


def analyze_replay(
    path: Path, candidate_faction: int, grid_size: float = 20.0
) -> dict[str, Any]:
    if candidate_faction not in (0, 1):
        raise ValueError("candidate_faction must be 0 or 1")
    if (
        isinstance(grid_size, bool)
        or not isinstance(grid_size, (int, float))
        or not math.isfinite(grid_size)
        or grid_size <= 0
    ):
        raise ValueError("grid_size must be a positive finite number")

    payload = load_frames(Path(path))
    if not payload or payload[-1].get("frame") != -1:
        raise TrajectoryError("Replay is missing the terminal frame")
    frames = [
        frame
        for frame in payload
        if isinstance(frame.get("frame"), int) and frame["frame"] > 0
    ]
    if not frames:
        raise TrajectoryError("Replay contains no positive frames")

    unit_data: dict[int, dict[str, Any]] = {}
    previous: dict[int, tuple[float, float] | None] = {}
    seen_cells: dict[int, set[tuple[int, int]]] = {}
    occupancy: Counter[tuple[int, int]] = Counter()
    death_heatmap: Counter[tuple[int, int]] = Counter()
    occupancy_frames = 0
    revisit_frames = 0
    nearest_enemy: list[float] = []
    nearest_ball: list[float] = []

    for frame in frames:
        humans = parse_humans(frame)
        balls = parse_balls(frame)
        by_number = {human.number: human for human in humans}
        candidates = sorted(
            (human for human in humans if human.number % 2 == candidate_faction),
            key=lambda human: human.number,
        )
        enemies = [
            human
            for human in humans
            if human.number % 2 != candidate_faction and human.alive
        ]
        carriers = {ball.belong for ball in balls if ball.belong >= 0}
        enemy_crystal = next(
            (ball for ball in balls if ball.number == 1 - candidate_faction), None
        )

        for human in candidates:
            data = unit_data.setdefault(
                human.number,
                {
                    "alive_frames": 0,
                    "transitions": 0,
                    "stationary_transitions": 0,
                    "distance_travelled": 0.0,
                    "ball_carry_frames": 0,
                    "deaths": 0,
                    "death_positions": [],
                    "enemy_crystal_min_distance": math.inf,
                    "enemy_crystal_closest_frame": None,
                    "enemy_crystal_closest_hp": None,
                },
            )
            seen_cells.setdefault(human.number, set())
            previous.setdefault(human.number, None)
            if not human.alive:
                previous[human.number] = None
                continue

            data["alive_frames"] += 1
            if human.number in carriers:
                data["ball_carry_frames"] += 1
            if enemy_crystal is not None:
                crystal_distance = _distance(
                    human.x, human.y, enemy_crystal.x, enemy_crystal.y
                )
                if crystal_distance < data["enemy_crystal_min_distance"]:
                    data["enemy_crystal_min_distance"] = crystal_distance
                    data["enemy_crystal_closest_frame"] = frame["frame"]
                    data["enemy_crystal_closest_hp"] = human.hp
            cell = (
                math.floor(human.x / grid_size),
                math.floor(human.y / grid_size),
            )
            occupancy[cell] += 1
            occupancy_frames += 1
            if cell in seen_cells[human.number]:
                revisit_frames += 1
            seen_cells[human.number].add(cell)

            prior = previous[human.number]
            if prior is not None:
                travelled = _distance(prior[0], prior[1], human.x, human.y)
                data["distance_travelled"] += travelled
                data["transitions"] += 1
                if travelled <= 1e-9:
                    data["stationary_transitions"] += 1
            previous[human.number] = (human.x, human.y)

            if enemies:
                nearest_enemy.append(
                    min(
                        _distance(human.x, human.y, enemy.x, enemy.y)
                        for enemy in enemies
                    )
                )
            if balls:
                nearest_ball.append(
                    min(
                        _distance(human.x, human.y, ball.x, ball.y)
                        for ball in balls
                    )
                )

        for event in _events(frame):
            if len(event) < 2 or event[0] != 3:
                continue
            actor = _integer(event[1], "death actor")
            if actor % 2 != candidate_faction or actor not in by_number:
                continue
            human = by_number[actor]
            data = unit_data[actor]
            data["deaths"] += 1
            data["death_positions"].append([human.x, human.y])
            death_heatmap[
                (
                    math.floor(human.x / grid_size),
                    math.floor(human.y / grid_size),
                )
            ] += 1

    units: list[dict[str, Any]] = []
    for number, data in sorted(unit_data.items()):
        transitions = data.pop("transitions")
        stationary = data.pop("stationary_transitions")
        units.append(
            {
                "number": number,
                "alive_frames": data["alive_frames"],
                "alive_ratio": _rounded(data["alive_frames"] / len(frames)),
                "distance_travelled": _rounded(data["distance_travelled"]),
                "stationary_ratio": (
                    _rounded(stationary / transitions) if transitions else 0.0
                ),
                "ball_carry_frames": data["ball_carry_frames"],
                "deaths": data["deaths"],
                "death_positions": data["death_positions"],
                "enemy_crystal_min_distance": (
                    _rounded(data["enemy_crystal_min_distance"])
                    if math.isfinite(data["enemy_crystal_min_distance"])
                    else None
                ),
                "enemy_crystal_closest_frame": data["enemy_crystal_closest_frame"],
                "enemy_crystal_closest_hp": data["enemy_crystal_closest_hp"],
            }
        )

    final_scores = _scores(payload[-1].get("scores"))
    return {
        "replay": str(Path(path)),
        "candidate_faction": candidate_faction,
        "grid_size": float(grid_size),
        "frames": len(frames),
        "final_scores": final_scores,
        "candidate_score": final_scores[candidate_faction],
        "opponent_score": final_scores[1 - candidate_faction],
        "units": units,
        "death_heatmap": [
            {"cell": list(cell), "count": count}
            for cell, count in sorted(
                death_heatmap.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "top_occupancy_cells": [
            {"cell": list(cell), "frames": count}
            for cell, count in sorted(
                occupancy.items(), key=lambda item: (-item[1], item[0])
            )[:5]
        ],
        "route_revisit_ratio": (
            _rounded(revisit_frames / occupancy_frames) if occupancy_frames else 0.0
        ),
        "nearest_enemy_distance": _distribution(nearest_enemy),
        "nearest_ball_distance": _distribution(nearest_ball),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a DOTO Replay trajectory")
    parser.add_argument("replay", type=Path)
    parser.add_argument("--candidate-faction", required=True, type=int, choices=(0, 1))
    parser.add_argument("--grid-size", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = analyze_replay(
            args.replay,
            candidate_faction=args.candidate_faction,
            grid_size=args.grid_size,
        )
    except (TrajectoryError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
