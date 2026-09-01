# Frontier Constraint Casebook

## F-IE4 and F-WINDOW

For four sets A-D, inclusive singles are `(34,29,27,23)`; pairs AB, AC, AD, BC, BD, CD are `(13,11,8,9,7,6)`; triples ABC, ABD, ACD, BCD are `(5,4,3,2)`; the four-way intersection is `2`. Report `N01` union size (`records`), `N02` exactly-one size (`records`), and `N03` exactly-two size (`records`).

Activity windows are `[0,7)`, `[5,13)`, `[12,19)`, `[18,24)`; blackouts are `[3,6)`, `[10,15)`, `[20,22)`. Reopened ticks `{5,12,20}` override a blackout only when the tick is in an activity window. Report `N04` active ticks (`ticks`).

## F-LRU weighted trace

Capacity is 12 weight-units. Initial least-to-most-recent entries are `[A:3,B:2,C:4]`. `PUT` of a new key appends; `PUT` of an existing key updates its weight and promotes it; `TOUCH` promotes; `RESIZE` changes weight and promotes; after each operation evict least-recent entries repeatedly until total weight is at most 12. `REMOVE` of a missing key is a no-op.

| Step/anchor | Operation |
|---|---|
| `FW-01` | `TOUCH B` |
| `FW-02` | `PUT D:6` |
| `FW-03` | `PUT E:5` |
| `FW-04` | `RESIZE D:7` |
| `FW-05` | `PUT F:4` |
| `FW-06` | `TOUCH D` |
| `FW-07` | `PUT G:3` |
| `FW-08` | `PUT H:5` |
| `FW-09` | `RESIZE G:6` |
| `FW-10` | `PUT I:4` |
| `FW-11` | `REMOVE X` |
| `FW-12` | `PUT J:3` |
| `FW-13` | `TOUCH I` |
| `FW-14` | `RESIZE J:6` |
| `FW-15` | `PUT K:5` |
| `FW-16` | `PUT L:2` |

Report `N05` final total weight (`weight-units`), `N06` total evictions (`evictions`), `N07` surviving entry count (`items`), and `N08` promotion count (`promotions`). Report `I01` distinct-key invariant, `I02` post-normalization weight cap, and `I03` “at most one eviction per operation,” each as `holds` or `violated` with unit `enum`.

## F-SELECT

Choose exactly five jobs.

| Job | Cost | Hours | Risk | Value | Channel |
|---|---:|---:|---:|---:|---|
| A | 6 | 4 | 3 | 16 | X |
| B | 4 | 6 | 4 | 15 | Y |
| C | 7 | 3 | 2 | 18 | X |
| D | 3 | 7 | 3 | 12 | Z |
| E | 6 | 4 | 6 | 20 | Y |
| F | 4 | 4 | 3 | 11 | Z |
| G | 3 | 5 | 2 | 10 | W |
| H | 5 | 2 | 4 | 14 | W |
| I | 2 | 6 | 1 | 9 | X |
| J | 5 | 3 | 3 | 17 | Z |
| K | 4 | 5 | 2 | 13 | R |

Constraints: cost `<=24`, hours `<=22`, risk `<=15`, cover channels X/Y/Z/W, not both A/C, not both D/F, `E` implies both `B` and `H`, `J` excludes `D`, `I` implies `G`, and `K` excludes `C`. Maximize value; among equal maximum values, prefer lower cost. Descending value/cost without backtracking selects an infeasible prefix.

Report `N09` feasible-set count (`selections`), `N10` maximum value (`utility-points`), `N11` number of maximum-value sets (`selections`), and `N12` cost of the maximum-value set (`cost-credits`).

## F-LEDGER mutation trace

Initial active set `{p,q}`, tombstones `{}`, generation `0`. A successful state change increments generation; rejected/no-op attempts do not. Delete moves active to tombstones; add succeeds only if the key is in neither set; restore moves tombstone to active; rename succeeds only when source is active and target is absent from both sets.

| Step/anchor | Operation |
|---|---|
| `FL-01` | delete q |
| `FL-02` | add r |
| `FL-03` | restore q |
| `FL-04` | rename p to s |
| `FL-05` | add s |
| `FL-06` | delete r |
| `FL-07` | restore r |
| `FL-08` | rename q to r |
| `FL-09` | delete z |
| `FL-10` | rename s to t |
| `FL-11` | restore z |
| `FL-12` | add p |

Report `N13` successful mutations (`mutations`) and `N14` final tracked-key cardinality, active plus tombstoned (`items`). Report `I04` active/tombstone disjointness, `I05` “every attempted mutation increments generation,” and `I06` “every successful rename leaves the old source key tombstoned,” each as `holds` or `violated` with unit `enum`.

## F-ALLOC structured witness

Return nonnegative integer counts `(a,b,c,d)`, each in `0..6`, maximizing `16a+15b+13c+30d`. Resource constraints are `6a+4b+3c+7d<=38`, `3a+8b+6c+5d<=36`, and `5a+2b+7c+6d<=34`; interacting constraints are `6<=a+b+c+d<=9`, `d<=2`, `a+c<=6`, `d>=1 => b>=2`, `c<=a+2`, `b+d<=6`, and `a+2d<=7`. If several maxima exist, choose the lexicographically smallest `(a,b,c,d)`. The runner-up is the best strictly smaller objective value.

Report `W01=a`, `W02=b`, `W03=c`, `W04=d`, each in `units`; `T01` global objective (`utility-points`); and `T02` optimum minus runner-up (`utility-points`).

## Falsification cards

- `F01` (`case-id`): Claim exactly-two is `S2-3*S3`, omitting the four-way correction. Return the first falsifying row: `FF01-A=(S2=30,S3=10,Q=0)`, `FF01-B=(S2=44,S3=13,Q=1)`, `FF01-C=(S2=38,S3=11,Q=2)`.
- `F02` (`step-id`): Claim one eviction always suffices in F-LRU. Return the exact visible anchor string for the earliest falsifying operation.
- `F03` (`case-id`): Claim descending value/cost and taking the first five jobs solves F-SELECT. Return `FF03-C` if false, else `NO-COUNTEREXAMPLE`.
- `F04` (`case-id`): Claim checking only non-wrapping three-slot windows suffices to enforce that every circular three-slot window has at most two ones. Return the first falsifying ID: `FS-021=11001000`, `FS-022=11001001`, `FS-023=10110101`.
- `F05` (`step-id`): Claim every F-LEDGER operation after step six changes state. Return the exact visible anchor string for the earliest falsifying operation.

## Answer-property ladder

| ID | Question | Unit | Difficulty |
|---|---|---|---|
| N01 | F-IE4 union size | records | easy |
| N02 | F-IE4 exactly one | records | easy |
| N03 | F-IE4 exactly two | records | medium |
| N04 | F-WINDOW active ticks | ticks | easy |
| N05 | F-LRU final total weight | weight-units | easy |
| N06 | F-LRU eviction count | evictions | medium |
| N07 | F-LRU surviving entry count | items | medium |
| N08 | F-LRU promotion count | promotions | medium |
| N09 | F-SELECT feasible-set count | selections | hard-tail |
| N10 | F-SELECT maximum value | utility-points | hard-tail |
| N11 | F-SELECT optimal-set count | selections | hard-tail |
| N12 | cost of maximum-value set | cost-credits | hard-tail |
| N13 | successful F-LEDGER mutations | mutations | medium |
| N14 | final tracked-key cardinality | items | medium |
| I01 | F-LRU distinct-key invariant | enum | easy |
| I02 | F-LRU post-normalization weight cap | enum | easy |
| I03 | at most one eviction per operation | enum | medium |
| I04 | active/tombstone disjointness | enum | medium |
| I05 | every attempt increments generation | enum | hard |
| I06 | successful rename tombstones old source | enum | hard |
| F01 | first omitted-Q counterexample | case-id | easy |
| F02 | earliest multi-eviction operation | step-id | medium |
| F03 | greedy counterexample anchor | case-id | hard |
| F04 | first wrapping-window counterexample | case-id | medium |
| F05 | first post-six no-op | step-id | hard |
| W01 | F-ALLOC `a` | units | hard-tail |
| W02 | F-ALLOC `b` | units | hard-tail |
| W03 | F-ALLOC `c` | units | hard-tail |
| W04 | F-ALLOC `d` | units | hard-tail |
| T01 | F-ALLOC global objective | utility-points | hard-tail |
| T02 | optimum minus runner-up | utility-points | hard-tail |

## Terms and Abbreviations

- ALLOC: bounded integer allocation search over `(a,b,c,d)`.
- IE: inclusion-exclusion.
- LRU: least recently used.
- SELECT: constrained finite job-subset search.
- Step-id: the exact visible operation anchor, such as `FW-03` or `FL-08`.
