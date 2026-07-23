#!/usr/bin/env python3
"""
Backfill Elo ratings into summary.json for all runs.

Reads matches.jsonl from each run, uses the framework's EloTracker
to compute Elo, and writes best_elo, final_elo, elo_history back to summary.json.

Usage:
    cd /home/six/Documents/THU/activities/SAST/AgentBenchResults
    uv run --no-project python scripts/backfill_elo.py
"""
import json
import sys
from pathlib import Path

# Add framework to path so we can import EloTracker
FRAMEWORK = Path(__file__).resolve().parent.parent.parent / "AgentBenchFramework"
sys.path.insert(0, str(FRAMEWORK / "src"))

from agentbench_frame.arena.rating import EloTracker


def main():
    data_dir = Path(__file__).resolve().parent.parent  # AgentBenchResults
    runs_dir = data_dir / "runs"

    tracker = EloTracker(initial_rating=1500.0, k_factor=32.0)

    # Phase 1: collect all valid matches across all runs, sorted by time
    # Each entry: (timestamp, agent, opponent, winner_flag)
    all_matches = []

    for game_dir in sorted(runs_dir.iterdir()):
        if not game_dir.is_dir():
            continue
        for agent_dir in sorted(game_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            for run_dir in sorted(agent_dir.iterdir()):
                if not run_dir.is_dir():
                    continue

                summary_path = run_dir / "summary.json"
                if not summary_path.exists():
                    continue

                matches_path = run_dir / "matches.jsonl"
                if not matches_path.exists():
                    continue

                # Read agent name from summary.json
                try:
                    summary = json.loads(summary_path.read_text())
                except (json.JSONDecodeError, Exception):
                    continue

                agent_name = summary.get("agent", agent_dir.name)
                created = summary.get("created", "")
                start_ts = summary.get("started_at", 0)

                # Parse matches
                valid_matches = []
                for line in matches_path.read_text().strip().splitlines():
                    if not line.strip():
                        continue
                    try:
                        m = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if m.get("status") != "valid":
                        continue

                    opponent = m.get("opponent", "unknown")
                    result = m.get("candidate_result")
                    if result == "win":
                        winner = 0  # agent (player1) wins
                    elif result == "loss":
                        winner = 1  # opponent (player2) wins
                    else:
                        continue  # draw or unknown, skip

                    seconds = m.get("seconds", 0)
                    # Use started_at + seconds as a proxy for match ordering
                    timestamp = start_ts + seconds if start_ts else 0
                    all_matches.append((timestamp, agent_name, opponent, winner))

    # Sort by timestamp
    all_matches.sort(key=lambda x: x[0])

    # Phase 2: replay matches into tracker, tracking per-agent state
    agent_state = {}  # agent_name -> {best_elo, history, last_elo}
    # Also track per-run (use the same tracker but record history per agent)
    # Actually, we need per-RUN elo, not per-agent.
    # Let's do this differently: for each run, reset a fresh tracker,
    # feed only matches involving that run's agent.

    # Better approach: group matches by (game, agent) and compute per-(game,agent)
    # This matches how summary.json works - one summary per agent per run.
    # Actually we should do per RUN.

    # Let's redo: for each run, create a fresh EloTracker, feed all valid matches
    # for that run's agent (cross-run), and record what that run contributed.

    # But that's not right either - Elo should accumulate across runs.
    # The correct approach: global ELO per (game, agent) across all runs.
    # Because the same agent accumulates rating across runs.

    # Let's rebuild per (game, agent):
    print(f"Found {len(all_matches)} valid matches across all runs", file=sys.stderr)

    # Group matches by (game, agent) pair
    from collections import defaultdict

    agent_matches = defaultdict(list)  # (game, agent) -> list of (ts, opponent, winner)
    for ts, agent_name, opponent, winner in all_matches:
        # We need game too. Let's re-scan.
        pass

    # Re-scan with game context
    agent_matches = defaultdict(list)
    for game_dir in sorted(runs_dir.iterdir()):
        if not game_dir.is_dir():
            continue
        for agent_dir in sorted(game_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            for run_dir in sorted(agent_dir.iterdir()):
                if not run_dir.is_dir():
                    continue

                summary_path = run_dir / "summary.json"
                if not summary_path.exists():
                    continue
                try:
                    summary = json.loads(summary_path.read_text())
                except Exception:
                    continue

                game = summary.get("game", game_dir.name)
                agent = summary.get("agent", agent_dir.name)
                start_ts = summary.get("started_at", 0)

                matches_path = run_dir / "matches.jsonl"
                if not matches_path.exists():
                    continue

                for line in matches_path.read_text().strip().splitlines():
                    if not line.strip():
                        continue
                    try:
                        m = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if m.get("status") != "valid":
                        continue

                    opponent = m.get("opponent", "unknown")
                    result = m.get("candidate_result")
                    if result == "win":
                        winner = 0
                    elif result == "loss":
                        winner = 1
                    else:
                        continue

                    seconds = m.get("seconds", 0)
                    timestamp = start_ts + seconds if start_ts else 0
                    agent_matches[(game, agent)].append((timestamp, opponent, winner))

    # Phase 3: for each (game, agent), compute Elo and write back
    updated_count = 0
    for (game, agent), matches in agent_matches.items():
        matches.sort(key=lambda x: x[0])
        tracker = EloTracker(initial_rating=1500.0, k_factor=32.0)
        tracker.add_player(agent)

        elo_history = []
        for ts, opponent, winner in matches:
            # Ensure opponent is registered
            tracker.add_player(opponent)
            tracker.update(agent, opponent, winner)
            elo_history.append({
                "step": len(elo_history) + 1,
                "elo": round(tracker.get_rating(agent), 1),
                "opponent": opponent,
            })

        if not elo_history:
            continue

        best_elo = max(e["elo"] for e in elo_history)
        final_elo = elo_history[-1]["elo"]

        # Write to all summary.json for this (game, agent) — only update runs
        # that have valid matches (otherwise they stay null)
        for game_dir in sorted(runs_dir.iterdir()):
            if not game_dir.is_dir() or game_dir.name != game:
                continue
            for agent_dir in sorted(game_dir.iterdir()):
                if not agent_dir.is_dir() or agent_dir.name != agent:
                    continue
                for run_dir in sorted(agent_dir.iterdir()):
                    if not run_dir.is_dir():
                        continue
                    summary_path = run_dir / "summary.json"
                    if not summary_path.exists():
                        continue
                    try:
                        summary = json.loads(summary_path.read_text())
                    except Exception:
                        continue

                    # Only update if this run had no elo data before,
                    # or if we're explicitly backfilling
                    summary["best_elo"] = best_elo
                    summary["final_elo"] = final_elo
                    summary["elo_history"] = elo_history
                    summary_path.write_text(
                        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
                    )
                    updated_count += 1

    print(f"Updated {updated_count} summary.json files with Elo data", file=sys.stderr)


if __name__ == "__main__":
    main()
