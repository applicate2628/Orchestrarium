const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const memo = fs.readFileSync(path.join(__dirname, "..", "resume-memo.md"), "utf8");

test("uses the accepted W2 resume scope instead of stale W1 state", () => {
  assert.match(
    memo,
    /^active scope\r?\n- Execute `W2` on `X3`, `X4`, `X1`, and `X5` using `M02`, `M06`, `M07`, and `M10`, then extend pairwise and lane-priority verdicts with the accepted `X3↔X4` provider-local path note\./m
  );
});

test("explicitly rejects stale W1 and blocked-X4 recovery context", () => {
  assert.match(memo, /^ignored stale context\r?\n- Do not restart `W1`; that step is already behind the current accepted state\./m);
  assert.match(
    memo,
    /- Ignore the stale suggestion to spend a bounded retry on restoring blocked `X4`; accepted parity evidence already says `X4` is runnable\./m
  );
});

test("keeps MCP scoring deferred and stays inside accepted scope", () => {
  assert.match(memo, /^next three actions\r?\n(?:- .+\r?\n){3}/m);
  assert.match(memo, /- Keep MCP scoring deferred and continue top-target waves before any fallback expansion\./m);
  assert.doesNotMatch(memo, /^active scope\r?\n- Restart `W1`/m);
  assert.doesNotMatch(memo, /^next three actions\r?\n- Reopen the blocked `X4` fallback path/m);
  assert.doesNotMatch(memo, /fallback-only waves/i);
});
