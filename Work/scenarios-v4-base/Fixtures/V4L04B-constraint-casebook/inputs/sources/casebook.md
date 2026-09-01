# Base Constraint Casebook

## B-IE3 and B-WINDOW

For three sets, inclusive intersection counts are singles `(29,24,18)`, pairs `(11,8,6)`, and triple `4`. Report `N01` union size (`records`), `N02` exactly-one size (`records`), and `N03` exactly-two size (`records`).

For integer ticks, activity windows are `[0,5)`, `[4,11)`, `[13,17)`, `[16,21)`; blackout windows are `[2,4)`, `[7,9)`, `[10,14)`, `[18,20)`. Active means union of activity minus union of blackout. Report `N04` active ticks (`ticks`).

## B-LRU count trace

Capacity is five distinct keys. Initial least-to-most-recent order is `[A,B,C]`. `TOUCH` and `ADD` of an existing key promote it; a new `ADD` appends then evicts least-recent keys until within capacity; removing a missing key is a no-op.

| Step | Operation |
|---:|---|
| 1 | `TOUCH A` |
| 2 | `ADD D` |
| 3 | `ADD E` |
| 4 | `ADD F` |
| 5 | `TOUCH C` |
| 6 | `ADD G` |
| 7 | `REMOVE E` |
| 8 | `ADD D` |
| 9 | `REMOVE Z` |
| 10 | `ADD H` |
| 11 | `ADD I` |
| 12 | `TOUCH G` |
| 13 | `ADD C` |
| 14 | `ADD J` |

Report `N05` final occupancy (`items`), `N06` total evictions (`evictions`), `N07` total promotions of existing keys (`promotions`), and `N08` maximum post-step occupancy after normalization (`items`). For invariants, report `holds` or `violated` with unit `enum`: `I01` distinct-key invariant, `I02` post-step capacity invariant, and `I03` “step 9 leaves order unchanged.”

## B-SELECT

Choose exactly five jobs.

| Job | Cost | Hours | Risk | Value | Channel |
|---|---:|---:|---:|---:|---|
| A | 5 | 4 | 3 | 14 | X |
| B | 4 | 5 | 4 | 13 | Y |
| C | 6 | 3 | 2 | 16 | X |
| D | 3 | 6 | 3 | 11 | Z |
| E | 5 | 4 | 5 | 17 | Y |
| F | 4 | 3 | 3 | 10 | Z |
| G | 3 | 4 | 2 | 9 | W |
| H | 4 | 2 | 4 | 12 | W |
| I | 2 | 5 | 1 | 8 | X |
| J | 5 | 3 | 2 | 15 | Z |

Constraints: cost `<=22`, hours `<=20`, risk `<=14`, cover channels X/Y/Z/W, not both A/C, not both D/F, `E` implies both `B` and `H`, `J` excludes `D`, and `I` implies `G`. Maximize value; among equal maximum values, prefer lower cost. Descending value/cost without backtracking selects an infeasible prefix.

Report `N09` feasible-set count (`selections`), `N10` maximum value (`utility-points`), `N11` number of maximum-value sets (`selections`), and `N12` cost of the maximum-value set (`cost-credits`).

## B-LEDGER mutation trace

Initial active set `{p,q}`, tombstones `{}`, generation `0`. A successful state change increments generation; rejected/no-op attempts do not. Delete moves active to tombstones; add succeeds only if the key is in neither set; restore moves tombstone to active; rename succeeds only when source is active and target is absent from both sets.

| Step/anchor | Operation |
|---|---|
| `BL-01` | delete q |
| `BL-02` | add r |
| `BL-03` | restore q |
| `BL-04` | rename p to r |
| `BL-05` | delete z |
| `BL-06` | delete p |
| `BL-07` | rename r to s |
| `BL-08` | add p |
| `BL-09` | restore p |
| `BL-10` | rename q to s |

Report `N13` successful mutations (`mutations`) and `N14` final tracked-key cardinality, active plus tombstoned (`items`). Report `I04` active/tombstone disjointness, `I05` “every attempted mutation increments generation,” and `I06` “`|active|+|tombstones|` never decreases,” each as `holds` or `violated` with unit `enum`.

## B-ALLOC structured witness

Return nonnegative integer counts `(a,b,c,d)`, each in `0..5`, maximizing `15a+14b+10c+24d`. Resource constraints are `5a+4b+3c+6d<=28`, `3a+7b+5c+4d<=26`, and `4a+2b+6c+5d<=24`; interacting constraints are `5<=a+b+c+d<=8`, `d<=2`, `a+c<=5`, `d>=1 => b>=2`, `b+c<=6`, and `c<=a+2`. If several maxima exist, choose the lexicographically smallest `(a,b,c,d)`. The runner-up is the best strictly smaller objective value.

Report `W01=a`, `W02=b`, `W03=c`, `W04=d`, each in `units`; `T01` global objective (`utility-points`); and `T02` optimum minus runner-up (`utility-points`).

## Falsification cards

- `F01` (`case-id`): Claim that clamping both endpoints to `[0,9]` before counting an inclusive integer range equals clipping the original range count to ten. Return the first falsifying case ID: `BF01-A=(-3,2)`, `BF01-B=(1,5)`, `BF01-C=(8,12)`.
- `F02` (`case-id`): Claim that union is always `sum(singles)-sum(pairs)`. Return the first falsifying row: `BF02-A=((7,6,5),(2,2,1),triple=0)`, `BF02-B=((9,8,6),(4,3,2),triple=2)`, `BF02-C=((10,7,6),(5,3,2),triple=1)`.
- `F03` (`case-id`): Claim that descending value/cost and taking the first five jobs solves B-SELECT. Return `BF03-C` if false, else `NO-COUNTEREXAMPLE`.
- `F04` (`step-id`): Claim every attempted B-LEDGER operation increments generation. Return the exact visible anchor string for the earliest falsifying operation.
- `F05` (`case-id`): Claim a linear no-adjacent-ones check proves circular no-adjacency. Return the first falsifying case: `BF05-A=1010100`, `BF05-B=100001`, `BF05-C=010101`.

## Answer-property ladder

| ID | Question | Unit | Difficulty |
|---|---|---|---|
| N01 | B-IE3 union size | records | easy |
| N02 | B-IE3 exactly one | records | easy |
| N03 | B-IE3 exactly two | records | medium |
| N04 | B-WINDOW active ticks | ticks | easy |
| N05 | B-LRU final occupancy | items | easy |
| N06 | B-LRU eviction count | evictions | medium |
| N07 | B-LRU promotion count | promotions | medium |
| N08 | B-LRU post-step peak occupancy | items | medium |
| N09 | B-SELECT feasible-set count | selections | hard-tail |
| N10 | B-SELECT maximum value | utility-points | hard-tail |
| N11 | B-SELECT optimal-set count | selections | hard-tail |
| N12 | cost of maximum-value set | cost-credits | hard-tail |
| N13 | successful B-LEDGER mutations | mutations | medium |
| N14 | final tracked-key cardinality | items | medium |
| I01 | B-LRU distinct-key invariant | enum | easy |
| I02 | B-LRU post-step capacity invariant | enum | easy |
| I03 | step 9 leaves order unchanged | enum | medium |
| I04 | active/tombstone disjointness | enum | medium |
| I05 | every attempt increments generation | enum | hard |
| I06 | combined active/tombstone cardinality never decreases | enum | hard |
| F01 | first clamp-claim counterexample | case-id | easy |
| F02 | first two-term IE counterexample | case-id | medium |
| F03 | greedy counterexample anchor | case-id | hard |
| F04 | earliest generation counterexample | step-id | medium |
| F05 | first circular-boundary counterexample | case-id | hard |
| W01 | B-ALLOC `a` | units | hard-tail |
| W02 | B-ALLOC `b` | units | hard-tail |
| W03 | B-ALLOC `c` | units | hard-tail |
| W04 | B-ALLOC `d` | units | hard-tail |
| T01 | B-ALLOC global objective | utility-points | hard-tail |
| T02 | optimum minus runner-up | utility-points | hard-tail |

## Terms and Abbreviations

- ALLOC: bounded integer allocation search over `(a,b,c,d)`.
- IE: inclusion-exclusion.
- LRU: least recently used.
- SELECT: constrained finite job-subset search.
- Step-id: the exact visible operation anchor, such as `BL-04`.
