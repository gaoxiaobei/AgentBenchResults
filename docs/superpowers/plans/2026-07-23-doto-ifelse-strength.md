# DOTO If-Else Strength Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stronger deterministic if-else 23_doto candidate and retain its framework-produced standard evaluation in AgentBenchResults.

**Architecture:** Retain the candidate's SDK-safe BFS, flash, combat, and meteor helpers. Replace the all-in default role loop with a state-priority policy (`RECOVER`, `ESCORT`, `STEAL`, `PRESSURE`) backed by BFS carrier-route prediction and map-aware role waypoints inferred from the public opponents' supplied code and valid replays.

**Tech Stack:** C++11 DOTO SDK, Python unittest, AgentBenchFramework `uv` benchmark runner, framework-generated JSON/TOML result artifacts.

## Global Constraints

- Read only `AgentBenchFramework` and `AgentBenchResults`; never read `AgentBench`.
- The candidate must remain deterministic and pure if-else: helpers/static match state are allowed; search, learned policies, randomness, and external runtime input are forbidden.
- Preserve the evaluator and generate results through `benchmarks/23_doto/run.py --data-dir /home/six/Documents/THU/activities/SAST/AgentBenchResults`.
- Do not overwrite existing result runs or hand-author evaluation metadata.

---

### Task 1: Establish reproducible route and build evidence

**Files:**
- Modify: `AgentBenchFramework/benchmarks/23_doto/agents/ifelse_supreme/playerAI.cpp`
- Test: `AgentBenchFramework/benchmarks/23_doto/tests/test_build.py`

**Interfaces:**
- Consumes: `Logic::map`, `Logic::crystal`, `Logic::humans`, and the framework public-opponent source/replay artifacts.
- Produces: a candidate source accepted by `benchmark.build.build_candidate(source, sdk, output_dir)`.

- [ ] **Step 1: Record public-route invariants before policy changes**

Read only `runtime/opponents/public_a/playerAI.cpp`,
`runtime/opponents/public_b/{playerAI.cpp,TaskScheduler.cpp}`, map metadata, and
valid replay artifacts. Record the reproducible facts in implementation comments:
public A uses `fixedCrystalPosition` and a central `(170,150)` route waypoint;
both factions have five humans; targets are `(72.5,67.5)` and `(247.5,264.5)`.

- [ ] **Step 2: Compile the unmodified source to establish the build baseline**

Run: `python -m unittest benchmarks/23_doto/tests/test_build.py -v`

Expected: all build tests pass, including `test_builds_public_a_source_with_the_sdk`.

- [ ] **Step 3: Add a failing source-contract test if the existing suite lacks one**

Add a test that calls `build_candidate` on
`agents/ifelse_supreme/playerAI.cpp`, asserting that the artifact is executable
and that `build/candidate/build.json` exists. The test body is:

```python
artifact = build_candidate(
    BENCHMARK_ROOT / "agents" / "ifelse_supreme" / "playerAI.cpp",
    RUNTIME_ROOT / "sdk", root / "build",
)
self.assertTrue(artifact.path.is_file())
self.assertTrue(os.access(artifact.path, os.X_OK))
```

- [ ] **Step 4: Run the source-contract test and observe the baseline result**

Run: `python -m unittest benchmarks/23_doto/tests/test_build.py -v`

Expected: the new candidate source-contract test passes before strategy work;
if it does not, stop and repair compilation before changing tactics.

### Task 2: Replace all-in rushing with state-priority roles

**Files:**
- Modify: `AgentBenchFramework/benchmarks/23_doto/agents/ifelse_supreme/playerAI.cpp:172-473`
- Test: `AgentBenchFramework/benchmarks/23_doto/tests/test_build.py`

**Interfaces:**
- Consumes: `predictEnemyCarrierPath(int,double)`, `go(int,Point,bool)`, `doFire(int)`, `castMeteor(int,Point)`, `threatened(Point,Point&)`.
- Produces: `roleTarget(int, int carrier, int enemyCarrier, Point myTarget, Point enemyCrystal, int bonusTarget)` behavior encoded in the `playerAI()` condition chain.

- [ ] **Step 1: Write the failing structural regression test**

Add a source-text assertion that the candidate contains all four named tactical
state comments (`RECOVER`, `ESCORT`, `STEAL`, `PRESSURE`) and no longer contains
the prior `Rush enemy crystal!` default. This guards the requested pure
if-else policy boundary without coupling to a particular score.

```python
source = candidate_source.read_text()
for state in ("RECOVER", "ESCORT", "STEAL", "PRESSURE"):
    self.assertIn(state, source)
self.assertNotIn("Rush enemy crystal!", source)
```

- [ ] **Step 2: Run the structural test to verify it fails**

Run: `python -m unittest benchmarks/23_doto/tests/test_build.py -v`

Expected: FAIL because current source has neither the four state labels nor the
new default role policy.

- [ ] **Step 3: Implement the minimal deterministic policy replacement**

Replace only the main role assignment loop with these ordered conditions:

```cpp
if (enc >= 0) {                 // RECOVER
    // nearest alive pursuer -> predicted carrier position;
    // next nearest -> 24-frame route intercept;
    // remaining units -> home screen or carrier fire range.
} else if (carrier >= 0) {      // ESCORT
    // carrier -> myTarget without flash;
    // lead -> 12-frame homeward waypoint; rear -> carrier; screen -> chaser.
} else if (enemy crystal is safely reachable) { // STEAL
    // one home defender, one central interceptor, two separated attackers,
    // one bonus collector only when no defender/interceptor is needed.
} else {                        // PRESSURE
    // preserve defender/interceptor posts and send remaining units toward
    // distinct attack approaches.
}
```

Keep meteor evasion before movement. When `enc >= 0`, cast only at the
40-frame predicted carrier position if in range; otherwise retain the existing
high-value meteor fallback. Permit flash only for the assigned role target and
not for a carrier.

- [ ] **Step 4: Run compile and structural regression tests**

Run: `python -m unittest benchmarks/23_doto/tests/test_build.py -v`

Expected: all tests pass and the candidate source is compiled with the supplied SDK.

### Task 3: Evaluate, choose the strongest screened candidate, and retain legal data

**Files:**
- Create: `AgentBenchResults/runs/23_doto/ifelse_supreme/<framework-run-id>/run.toml`
- Create: `AgentBenchResults/runs/23_doto/ifelse_supreme/<framework-run-id>/summary.json`
- Create: `AgentBenchResults/runs/23_doto/ifelse_supreme/<framework-run-id>/events.jsonl`
- Create: `AgentBenchResults/runs/23_doto/ifelse_supreme/<framework-run-id>/matches.jsonl`
- Create: `AgentBenchResults/runs/23_doto/ifelse_supreme/<framework-run-id>/artifacts/`

**Interfaces:**
- Consumes: candidate source and the framework CLI.
- Produces: evaluator-authored standard result data with its raw build and match artifacts.

- [ ] **Step 1: Run a quick profile for tactical screening**

Run:

```bash
uv run --with numpy python benchmarks/23_doto/run.py \
  --candidate-name ifelse_supreme \
  --candidate-source benchmarks/23_doto/agents/ifelse_supreme/playerAI.cpp \
  --profile quick --seed 20260723 \
  --data-dir /home/six/Documents/THU/activities/SAST/AgentBenchResults
```

Expected: a new framework-generated run directory, a successful candidate
build, and valid cells where the legacy runner completes.

- [ ] **Step 2: Inspect raw outcomes, not only the aggregate**

Run: `tail -n +1 <quick-run>/matches.jsonl && jq '.doto' <quick-run>/summary.json`

Expected: confirm that every non-valid cell is labelled `infra_error`; compare
valid cells by score rate, score ratio, goals, and deaths. Revise only the
role thresholds supported by those artifacts, then repeat Steps 1-2 once if a
revision is made.

- [ ] **Step 3: Run the official standard profile with the selected source**

Run:

```bash
uv run --with numpy python benchmarks/23_doto/run.py \
  --candidate-name ifelse_supreme \
  --candidate-source benchmarks/23_doto/agents/ifelse_supreme/playerAI.cpp \
  --profile standard --seed 20260723 \
  --data-dir /home/six/Documents/THU/activities/SAST/AgentBenchResults
```

Expected: a new `runs/23_doto/ifelse_supreme/<run-id>/` directory containing
the legal raw documents and artifacts. Its outcomes must be reported exactly
as produced; do not edit JSON/TOML after evaluation.

- [ ] **Step 4: Verify repository-visible result completeness**

Run:

```bash
latest=$(find runs/23_doto/ifelse_supreme -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)
test -f "$latest/run.toml" && test -f "$latest/summary.json" && \
test -f "$latest/events.jsonl" && test -f "$latest/matches.jsonl" && \
jq -e '.doto.aggregate.attempted_games == 4' "$latest/summary.json"
```

Expected: exit 0. If the evaluator returns infrastructure errors, the directory
is still legal but the final report must state the exact valid/error split.
