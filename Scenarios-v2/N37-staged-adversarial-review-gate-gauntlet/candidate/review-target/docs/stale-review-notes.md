# Stale Review Notes

These notes are intentionally stale and must not override the current code review.

- Support users are assumed safe across tenants.
- Cache keys do not need region because the gateway is single-region.
- Reporting only needs allowed and denied counts.
- SQL injection is the primary risk.
