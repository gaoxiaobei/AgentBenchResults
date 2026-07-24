# 23-DOTO trajectory findings

The four JSON files in this directory were generated from the complete
standard run `20260723_0935_4fbff88f` with:

```bash
python tools/doto_trajectory.py REPLAY.zip --candidate-faction FACTION
```

## Baseline diagnosis

- The public-A faction-0 win carried the enemy crystal for 3,788 aggregate
  unit-frames and had 15 deaths.
- Both public-B games had zero carry frames and 97 total deaths.
- Against public B, four faction-0 units followed effectively identical paths.
  The main death concentration was grid cells `(6,5)` and `(7,5)`.
- Candidate units were much closer to enemies than to crystals against public
  B, showing that the policy entered combat before completing the steal.
- Public B kept two units near the two bonus locations and used one crystal
  leader plus two combat supports. This role split became the basis for the
  next deterministic policy.

## Fixed-seed screening evidence

All candidates below used the framework `quick` profile with seed `20260724`;
the runs stayed under `/tmp` and are not benchmark claims.

| Candidate | Public A | Public-B pickups | Public-B goals | Public-B deaths | Public-B mean score |
| --- | ---: | ---: | ---: | ---: | ---: |
| previous policy | 1–1 | 0 | 0 | 15 | 2.6 |
| bonus control + armed attackers | 1–1 | 0 | 0 | 21 | 10.5 |
| leader + two supports | 2–0 | 0 | 0 | 16 | 11.0 |
| staged crystal route | 2–0 | 3 | 0 | 18 | 10.75 |
| carrier-priority override | 2–0 | 2 | 1 | 17 | 51.75 |

The carrier-priority candidate is the retained policy. It improved the public-B
faction-1 cell from `10–180` with no goals to `92–178` with one goal while
preserving two public-A wins. It has not yet beaten public B, so a standard run
is intentionally deferred until further screening closes that gap.

