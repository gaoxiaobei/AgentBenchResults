# DOTO Trajectory Analysis Design

## Purpose

Build a deterministic offline analyzer for DOTO Replay ZIP files. Its output
must turn long replays into evidence that can directly guide pure if-else
policy changes, without modifying the referee, score calculation, or benchmark
result format.

## Scope

The first version analyzes one completed replay for one candidate faction and
emits JSON. It reports:

- match duration and final scores;
- per-candidate-unit distance travelled, stationary-frame ratio, alive-frame
  ratio, ball-carry frames, deaths, and death coordinates;
- candidate-wide distance to the nearest enemy and nearest ball, summarized by
  mean and selected percentiles;
- a fixed-size death heatmap using map-space grid cells;
- repeated-route evidence based on revisiting the same grid cell;
- the five grid cells with the most candidate occupancy.

The analyzer accepts the historical Replay representation in which structured
fields are Python-literal strings. It uses `ast.literal_eval`, rejects malformed
or non-finite coordinates, and never executes Replay content.

The first version does not render graphics, infer map connectivity, parse
player debug logs, or make policy changes automatically. Those features do not
improve the first decision loop enough to justify their complexity.

## Architecture

`tools/doto_trajectory.py` owns Replay decoding, typed frame extraction,
metric calculation, and a JSON CLI. It reuses no referee internals so it can
run from the Results repository alone.

`tests/test_doto_trajectory.py` creates small synthetic Replay ZIPs and covers
faction mapping, movement and carrying metrics, death localization, heatmap
aggregation, malformed inputs, and CLI JSON output.

The analyzer processes a Replay as a list because official Replay files are
small enough for the existing framework parser to do the same. Metrics are
accumulated in one pass after validation.

## Data Interpretation

A human record has fields:

`number, x, y, hp, meteor_number, meteor_time, flash_number, flash_time,
fireball_time, death_time, inv_time`.

Human faction is `number % 2`. Candidate units are the five records whose
number has the requested candidate-faction parity. A unit is alive when
`death_time == -1`. A death event has code `3`; its actor identifies the unit,
and the current frame's position is used as the death coordinate.

A ball record is `x, y, belong, number`. A candidate carries a ball when
`belong` identifies one of its units.

## Interface

Library:

```python
analyze_replay(path: Path, candidate_faction: int, grid_size: float = 20.0) -> dict
```

CLI:

```text
python tools/doto_trajectory.py REPLAY.zip --candidate-faction 0
```

The CLI writes stable, sorted, indented JSON to stdout. Invalid input exits
nonzero with a concise error on stderr.

## Verification

Unit tests must fail before implementation and pass afterward. The analyzer
must then run against all four complete standard replays in
`runs/23_doto/ifelse_supreme/20260723_0935_4fbff88f`. Reports for public A and
public B will be compared before changing the agent.

