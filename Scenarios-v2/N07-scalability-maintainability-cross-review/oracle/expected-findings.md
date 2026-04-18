# Expected Findings

The ground-truth report for `N07` should return `REVISE` with these findings, in severity order.

## 1. Blocking: repeated full-tree rescans in lane-card assembly

- anchor file: `candidate/review-target/routing-matrix/assemble_lane_matrix.py`
- supporting references:
  - `collect_lane_members`
  - `build_lane_cards`
  - `scenarios_root.iterdir()`
- reason: every lane rebuild rescans the full scenario root, reparses each `scenario.yaml`, and
  repeats lane resolution work instead of building one shared view

## 2. Blocking: duplicated lane-basis ownership invites drift

- anchor files:
  - `candidate/review-target/routing-matrix/lane_basis.py`
  - `candidate/review-target/routing-matrix/lane_catalog.py`
- reason: lane membership is maintained in both `ROUTING_BASIS` and `ROUTE_GROUPS`, so routing
  truth can drift across two local owners

## 3. Major: unbounded snapshot retention stores full serialized card payloads

- anchor file: `candidate/review-target/routing-matrix/assemble_lane_matrix.py`
- reason: `HISTORY.append(json.dumps(cards))` retains full lane-card snapshots with no bound, so
  repeated refreshes compound memory cost

## Expected gate

`REVISE`
