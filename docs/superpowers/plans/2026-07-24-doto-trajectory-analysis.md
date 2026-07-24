# DOTO Trajectory Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested offline analyzer that turns complete DOTO Replay ZIP files into spatial and behavioral metrics useful for improving a pure if-else agent.

**Architecture:** A single dependency-free Python module decodes and validates historical Replay fields, accumulates per-unit and team metrics in one pass, and exposes both a library function and JSON CLI. Synthetic ZIP fixtures verify exact behavior before the implementation is run on the four standard evaluation replays.

**Tech Stack:** Python 3.11 standard library, `unittest`, JSON, ZIP, `ast.literal_eval`.

## Global Constraints

- Do not read or modify the `AgentBench` repository.
- Do not modify referee behavior, benchmark scoring, or legal result files.
- Replay content must only be decoded with JSON and `ast.literal_eval`.
- The tool must have no third-party runtime dependencies.
- Production code is written only after the corresponding test has failed.

---

### Task 1: Replay decoding and validation

**Files:**
- Create: `tests/test_doto_trajectory.py`
- Create: `tools/doto_trajectory.py`

**Interfaces:**
- Produces: `TrajectoryError`, `load_frames(path: Path) -> list[dict]`,
  `parse_humans(frame: dict) -> list[Human]`, and
  `parse_balls(frame: dict) -> list[Ball]`.

- [ ] **Step 1: Write the failing decoding tests**

Create a synthetic Replay ZIP containing map, two positive frames, and a
terminal frame. Assert that `load_frames` accepts exactly one JSON member,
`parse_humans` returns typed numeric fields, and malformed literals or
non-finite coordinates raise `TrajectoryError`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python -m unittest tests.test_doto_trajectory.ReplayDecodingTest -v
```

Expected: import failure because `tools.doto_trajectory` does not exist.

- [ ] **Step 3: Implement minimal safe decoding**

Implement frozen `Human` and `Ball` dataclasses, ZIP JSON-member validation,
frame-list validation, literal-sequence decoding, exact record-length checks,
numeric type checks, and finite-coordinate checks.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
python -m unittest tests.test_doto_trajectory.ReplayDecodingTest -v
```

Expected: all decoding tests pass.

### Task 2: Spatial and behavioral metrics

**Files:**
- Modify: `tests/test_doto_trajectory.py`
- Modify: `tools/doto_trajectory.py`

**Interfaces:**
- Consumes: typed Replay frames from Task 1.
- Produces:
  `analyze_replay(path: Path, candidate_faction: int, grid_size: float = 20.0) -> dict`.

- [ ] **Step 1: Write failing metric tests**

Using known unit movement, ball ownership, and death events, assert exact
distance travelled, stationary ratio, alive ratio, carry frames, death
coordinates, heatmap cells, occupancy cells, revisit ratio, nearest-enemy
distance, and nearest-ball distance. Add validation tests for faction and grid
size.

- [ ] **Step 2: Run metric tests and verify RED**

Run:

```bash
python -m unittest tests.test_doto_trajectory.TrajectoryMetricsTest -v
```

Expected: failure because `analyze_replay` does not exist.

- [ ] **Step 3: Implement one-pass metric accumulation**

Track previous positions per candidate unit; accumulate movement only across
consecutive alive frames; count alive, stationary, carrying, occupancy, and
revisits; localize candidate death events; sample nearest live enemy and ball
distances; calculate means and nearest-rank percentiles; return only
JSON-serializable values with deterministic key and list ordering.

- [ ] **Step 4: Run metric and full tests**

Run:

```bash
python -m unittest tests.test_doto_trajectory -v
python tests/test_doto_ifelse_source.py -v
```

Expected: all tests pass.

### Task 3: CLI and real-replay diagnostic reports

**Files:**
- Modify: `tests/test_doto_trajectory.py`
- Modify: `tools/doto_trajectory.py`
- Create: `analysis/23_doto/20260723_0935_4fbff88f/*.json`

**Interfaces:**
- Consumes: `analyze_replay`.
- Produces: CLI arguments `replay`, `--candidate-faction`, `--grid-size`, and
  stable JSON stdout.

- [ ] **Step 1: Write and fail a CLI test**

Invoke the script on the synthetic Replay and assert exit code zero, valid JSON
stdout, and faction-specific results. Invoke it with malformed input and assert
nonzero exit plus a concise stderr message.

- [ ] **Step 2: Implement the CLI**

Use `argparse`; serialize with `json.dump(..., sort_keys=True, indent=2)`; catch
`TrajectoryError`, print `error: <message>` to stderr, and return exit code 2.

- [ ] **Step 3: Run all tests and generate four reports**

Run the test suite, then invoke the CLI once for every match directory in the
standard run, using the faction encoded in each directory name. Save reports
under `analysis/23_doto/20260723_0935_4fbff88f/`.

- [ ] **Step 4: Compare public A and public B**

Read the four reports and record concrete policy implications: highest death
cells, weakest units, route-revisit differences, carry-frame differences, and
enemy-distance differences. Use this evidence to choose the next if-else
policy change.

- [ ] **Step 5: Commit the analyzer**

Stage only the analyzer, its tests, the plan, and compact JSON reports. Do not
stage Replay ZIPs, stdout logs, build products, or exploratory run directories.

