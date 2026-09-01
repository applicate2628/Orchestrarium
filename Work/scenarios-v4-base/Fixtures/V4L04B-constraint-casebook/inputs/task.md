# Task

Read `inputs/sources/casebook.md` and write one JSON object to `candidate/numeric-answer.json` using `inputs/output-schema.json`.

Put these exact visible IDs under `measurements`: `N01`, `N02`, `N03`, `N04`, `N05`, `N06`, `N07`, `N08`, `N09`, `N10`, `N11`, `N12`, `N13`, `N14`, `W01`, `W02`, `W03`, `W04`, `T01`, `T02`.

Put these exact visible IDs under `cases`: `I01`, `I02`, `I03`, `I04`, `I05`, `I06`, `F01`, `F02`, `F03`, `F04`, `F05`.

Use the exact unit printed for each property. JSON numbers are the natural representation for numeric answers. Put any concise derivation in `narrative`; it is unscored. Do not embed an `item_id`; each visible property key is the identity.

Interpretation rules:

- Intervals are half-open unless a case explicitly says an integer range is inclusive.
- LRU order is least-to-most-recent. Complete each mutation, including all required evictions, before the next operation.
- Selection objective ties prefer lower cost.
- Allocation ties use lexicographically smallest `(a,b,c,d)` in ordinary coordinate order.
- “First” and “earliest” follow the visible case or step order.
- A `step-id` answer is the exact visible operation anchor string, not its numeric ordinal.

## Terms and Abbreviations

- LRU: least recently used.
- Step-id: the exact visible operation anchor, such as `BL-04`.
