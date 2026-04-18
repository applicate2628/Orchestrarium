# Expected Findings

The ground-truth report for `N03` should return `REVISE` with these findings, in severity order.

## 1. Blocking: changed-path coverage drops added and renamed files

- anchor file: `candidate/review-target/src/review_packet_builder.py`
- supporting reference: `inputs/accepted-review-scope.md`
- reason: `collect_changed_paths` only keeps entries whose `status` equals `modified`, so `added`
  and `renamed` surfaces disappear from the packet even though the admitted generic review scope
  requires the reviewer to see the full touched set

## 2. Major: title-only dedupe collapses distinct findings

- anchor file: `candidate/review-target/src/review_packet_builder.py`
- supporting reference: `inputs/accepted-review-scope.md`
- reason: `collapse_findings` keys only on `title_key`, so two findings with the same title text but
  different `path` or `line` anchors collapse into one record and lose review evidence

## 3. Major: malformed hunk headers are silently turned into empty evidence

- anchor file: `candidate/review-target/src/review_packet_builder.py`
- supporting reference: `inputs/review-boundary.md`
- reason: `parse_hunk_lines` catches parse failures and returns `[]`, which hides malformed diff
  evidence instead of surfacing an explicit parse problem for the reviewer

## Expected gate

`REVISE`
