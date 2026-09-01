# Oracle (hidden)

`stamina-contract.json` holds the full hidden list of `quote_*` consumers and their
expected migrated outputs, plus the `report_*`/`audit_*` decoys and their
expected-unchanged outputs. The candidate never sees this file.

Scoring: `breadth_fraction = migrated_correct / total_consumers`, graded (0..1).
PASS requires `breadth_fraction >= pass_fraction` AND zero decoy false-positives.
The per-variant fraction plus the completion-vs-length slope across the triplet is
the discriminating signal (see `scoring-anchors.md`).
