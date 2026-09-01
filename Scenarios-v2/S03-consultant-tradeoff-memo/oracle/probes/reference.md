# S03 Consultant Advisory Memo

## Provenance

- Execution role: consultant
- Assigned / replaced internal role: none
- Requested provider: internal
- Resolved provider: none
- Requested consultant mode: internal
- Actual execution path: internal consultant
- Model / profile used: runtime default
- Deviation reason: none

## Decision question

Should the lead validate the memo-only bundle pattern by materializing one local advisory pilot
first (`inputs/accepted-brief.md`), or spend the next slice on shared memo scaffolding before any
new bundle exists?

## Recommended direction

Recommend Option A - one local advisory pilot first. It is the smallest safe reversible step: the
change stays local to one bundle root, so the blast radius is one directory rather than several
future roots. Building the pilot first produces real evidence about the advisory memo contract
before any shared abstraction hardens, which is the signal the accepted brief and evidence summary
(`inputs/evidence-summary.md`) say we do not yet have.

## Alternatives considered

### Option A - one local advisory pilot first

Preferred, as above: reversible, local, and evidence-producing before the shape is fixed.

### Option B - shared memo scaffolding first

Rejected for the near term. Building shared memo scaffolding first would freeze the memo shape
before the sibling memo roles S06 (analyst) and S10 (algorithm-scientist) have proven they want the
same structure. The open questions confirm that role convergence is not proven, so a shared
scaffold is a premature abstraction: if S06 or S10 later diverge, unwinding the scaffold re-touches
multiple future roots and widens the blast radius far beyond one pilot. The claimed authoring-time
saving is unmeasured, so it cannot justify hardening the shape now.

### Option C - wait for more evidence before materializing

Rejected: this overstates the blocker. The packet already supports one narrow pilot, so choosing to
wait for more evidence mainly postpones the first concrete signal about memo-bundle ergonomics.

## Major tradeoffs

Option A trades a little duplicated verifier code now for a reversible, low-blast-radius probe that
keeps future roots free. Option B trades that reversibility away for an unproven reuse saving.

## Key risks

- The pilot may under-sample the shape the analyst and algorithm-scientist memos eventually need.
- Duplicated scaffolding may accumulate if a shared abstraction is deferred too long.

## Assumptions and uncertainty

This memo assumes the accepted brief and open questions (`inputs/open-questions.md`) are current.
There is missing evidence: authoring-time savings for a shared scaffold are unmeasured, the open
questions about role overlap are unresolved, and downstream review friction is still partly unknown.
This uncertainty is why the reversible pilot is preferred over an early shared shape.

## Confidence

Moderate confidence in Option A; it is robust precisely because it stays reversible while the
uncertainty is resolved.

## Advisory status

NON-BLOCKING

## Continuation prompt

Continue working: run the Option A pilot, then revisit shared scaffolding once S06 and S10 shapes
are observed.
