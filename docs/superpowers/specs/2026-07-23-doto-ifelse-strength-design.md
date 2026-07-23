# DOTO If-Else Strength Design

## Goal

Replace the current all-in `ifelse_supreme` behavior with a deterministic,
pure if-else DOTO agent that prioritizes competitive strength against the
framework's public 23_doto opponents. The agent may use helper functions,
static match-local state, map analysis, and offline opponent-path research; it
must not use search, learned policies, randomness, or external runtime input.

## Scope and constraints

- Read and use only `AgentBenchFramework` and `AgentBenchResults`; do not read
  `AgentBench`.
- Modify only the candidate source in
  `AgentBenchFramework/benchmarks/23_doto/agents/ifelse_supreme/playerAI.cpp`
  for strategy changes.
- Preserve the framework evaluator and the legal result schema.
- Produce a fresh framework-generated standard-profile result directory under
  `AgentBenchResults/runs/23_doto/ifelse_supreme/` without overwriting existing
  runs.
- Treat framework timeouts as infrastructure errors, never as strategy losses.

## Evidence and problem statement

The existing standard run has one valid public-B game: a 180.8:1097.2 loss,
with 47 candidate deaths and only two goals. The other three cells timed out
in the legacy process launcher and contain no complete replay, so they cannot
justify tactical conclusions. The candidate's current normal-state policy
sends every unit to the enemy crystal. It consequently commits no reliable
defenders, carrier interceptors, or escort threshold, despite having pathing
and skill helpers.

## Alternatives considered

1. Patch the existing rush priorities. This is low-risk but retains the
   all-in attack structure and leaves large tactical holes.
2. Replace the candidate with a minimal fixed role script. This is stable but
   discards the useful routing and ability machinery already present.
3. Keep the deterministic movement/ability helpers and replace the policy
   layer with map-aware roles and threat states. This has the best expected
   strength because it combines safe execution with explicit counterplay to
   the supplied opponents. This is the chosen design.

## Architecture

### Offline opponent-route model

Use the public opponent source and valid framework replay artifacts to map
each opponent's crystal-carrier route from the candidate's crystal to its
target. Record the stable corridor cells, choke points, and common movement
direction for each faction. Encode the resulting map constants and route
selection as deterministic conditions in the candidate; the candidate does
not parse replays or opponent source at match time.

### Match-local state

On the first frame, cache map dimensions, faction count, home/away target
locations, BFS distance fields, and route waypoints. Each frame derives one
of these mutually exclusive global states in priority order:

1. `RECOVER`: the enemy carries our crystal;
2. `ESCORT`: an allied unit carries the enemy crystal;
3. `STEAL`: the enemy crystal is unheld and a safe attacker can take it;
4. `PRESSURE`: neither side has a carrier.

The selected state determines explicit roles. Conditions may reassign a role
when its current unit is dead or too far from the relevant route waypoint.

### Roles and decisions

- **RECOVER:** one nearest unit shadows the carrier, one holds the predicted
  route choke point, one protects home from escorts, and remaining units
  apply ranged pressure. A meteor is reserved for a predicted carrier
  position inside range; a second unit never burns its meteor on a low-value
  cluster while a carrier exists.
- **ESCORT:** the carrier follows BFS home without flashing. A lead blocker
  moves to the next homeward waypoint, a rear guard stays within fireball
  range, and the remaining units screen the closest chaser. No unit abandons
  this formation to farm a bonus rune.
- **STEAL/PRESSURE:** allocate a home defender, a mid-route interceptor, and
  two attackers. Attackers approach on distinct safe corridors instead of
  converging on the crystal. Bonus runes are taken only when their assigned
  unit is not required by recovery, escort, or home defense.
- **Survival:** meteor evasion precedes movement, firing is target-led, and
  flash is conditioned on a legal landing point plus a role-specific gain
  (intercept, crystal pickup, escape, or progress to the next route waypoint).

## Data flow

`Logic` state -> carrier detection and map/route predicates -> global tactical
state -> per-unit role condition chain -> movement plus ability actions.
The evaluator builds the candidate, runs the balanced public-A/public-B and
both-faction matrix, retains raw artifacts, and writes JSON/TOML result files
directly to the results repository.

## Error handling and evaluation

First run the framework's compiler/unit checks and quick profile while
iterating. Inspect every valid replay and `matches.jsonl` to distinguish
strategy losses from infrastructure errors. Once a candidate improves the
valid-cell score rate and has no candidate build failure, run a standard
profile with the evaluator's `--data-dir` targeting `AgentBenchResults`.
The delivered result must remain framework-produced and retain all required
metadata/artifacts; no hand-authored summary or score is permitted.

## Success criteria

- Candidate source remains a deterministic if-else policy under the agreed
  boundary.
- It builds under the supplied SDK and does not introduce evaluator changes.
- Quick evaluation supplies valid games and demonstrates better tactical
  evidence than the existing all-in loss, especially lower deaths and/or
  stronger score rate against public B.
- A fresh standard run is present in `AgentBenchResults` in the framework's
  legal data format, with its actual outcomes and any infrastructure errors
  preserved.
