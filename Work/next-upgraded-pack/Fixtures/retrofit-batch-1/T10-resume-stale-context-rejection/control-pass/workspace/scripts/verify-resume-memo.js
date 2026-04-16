const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

const expectedStatus = `- **Last accepted artifact**: \`runs/x3-x4-parity-batch-2026-04-14.md\`
- **Open obligations before closeout**: continue top-target waves before fallback expansion, capture additional pairwise and lane-priority verdicts through \`W2\` and \`W3\`, keep MCP scoring deferred, and preserve \`X4\` as a Claude-internal fallback path rather than a separate provider

## Next action

Execute \`W2\` on \`X3\`, \`X4\`, \`X1\`, and \`X5\` using \`M02\`, \`M06\`, \`M07\`, and \`M10\`, then extend pairwise and lane-priority verdicts with the accepted \`X3↔X4\` provider-local path note.
`;

const expectedBrief = `- Open obligations before closeout:
  - keep lead-owned task memory synchronized with accepted artifacts and execution progress
  - execute \`W1\`, \`W2\`, and \`W3\` on top targets before fallback expansion
  - build pairwise comparison verdicts across all \`15\` target pairs, with priority on \`X3↔X4\`, \`X1↔X2\`, and \`X5↔X6\`
  - translate pairwise and role-suitability evidence into workflow-lane preferred priority guidance for \`externalPriorityProfiles\`
  - establish go or no-go criteria for \`X2\` and \`X6\`
  - keep MCP scoring deferred into its own later track
`;

const expectedStale = `## Next step

Move into \`W2\` on \`X3\`, \`X1\`, and \`X5\` with \`M02\`, \`M06\`, \`M07\`, and \`M10\`, unless the operator decides to spend one bounded retry on restoring the blocked \`X4\` secret-backed fallback path first.
`;

const expectedAccepted = `| Field | Verdict |
|---|---|
| \`same provider or not\` | same provider; \`X3↔X4\` remains a Claude-internal path note, not a provider-order change |
| \`fallback admissibility\` | \`X4\` is now runnable and acceptable as a real Claude fallback path |
| \`largest caveat\` | \`X4\` currently exposes a broader ambient tool and MCP surface at init than \`X3\`, so model-only cleanliness is lower even without observed tool use |
`;

function read(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), "utf8");
}

try {
  const memo = read("../resume-memo.md");

  assert.match(
    memo,
    /^active scope\r?\n- Execute `W2` on `X3`, `X4`, `X1`, and `X5` using `M02`, `M06`, `M07`, and `M10`, then extend pairwise and lane-priority verdicts with the accepted `X3↔X4` provider-local path note\./m
  );
  assert.match(memo, /^ignored stale context\r?\n- Do not restart `W1`; that step is already behind the current accepted state\./m);
  assert.match(
    memo,
    /- Ignore the stale suggestion to spend a bounded retry on restoring blocked `X4`; accepted parity evidence already says `X4` is runnable\./m
  );
  assert.match(memo, /^next three actions\r?\n(?:- .+\r?\n){3}/m);
  assert.match(memo, /^open risks\r?\n(?:- .+\r?\n){2}/m);
  assert.doesNotMatch(memo, /fallback-only waves/i);
  assert.doesNotMatch(memo, /Start MCP scoring now/i);

  assert.equal(read("../artifacts/status.md"), expectedStatus);
  assert.equal(read("../artifacts/brief.md"), expectedBrief);
  assert.equal(read("../artifacts/stale-w1-top-path-synthesis.md"), expectedStale);
  assert.equal(read("../artifacts/accepted-x3-x4-parity-batch.md"), expectedAccepted);

  console.log("VERIFY_T10_RESUME_OK");
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
