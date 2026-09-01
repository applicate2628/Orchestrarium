# Design Note — dedup authority (SUPERSEDED)

Source id: `SRC-DESIGN-B`
Status: **SUPERSEDED by `SRC-DESIGN-A` on 2026-06-30. Retained for history only.**
Dated: 2026-05-12.

> NOTE: This note is superseded. It is kept in the source package only so the history of the decision is
> visible. It is NOT a current authority and must not be weighed against `SRC-DESIGN-A` as if the two
> still compete.

## Former proposal (no longer live)

Introduce a **new standalone dedup service** that all four services call. This was the earlier direction.
It was replaced by the boundary-owned approach in `SRC-DESIGN-A` after review found the standalone
service added an extra network hop on the hot payment path.

Because this note is superseded, there is **no unresolved conflict** between `SRC-DESIGN-A` and
`SRC-DESIGN-B`: `SRC-DESIGN-A` is the single current design authority and `SRC-DESIGN-B` is closed
history.
