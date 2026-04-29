# S11 Computational Scientist Model Validation Memo

`S11` benchmarks `R11 $computational-scientist` on a non-web, evidence-heavy numerical or
physical reasoning task. The candidate is asked to produce one model and validation memo for a
proposed lumped thermal model of a benchtop calibration block. The bundle stays in the scientist
lane: formalize the model, state assumptions, check units and invariants, evaluate the validation
criteria against supplied traces, and explain uncertainty before any implementation or policy work.

## Scenario summary

The lab has a draft one-state thermal model intended to predict the temperature of an aluminum
calibration puck during a local non-networked conditioning cycle. The draft model is plausible on
first inspection, but the evidence packet includes:

1. a bounded operating range and admitted use
2. the proposed governing equation and parameter estimates
3. validation traces with measured and predicted temperatures
4. explicit acceptance criteria
5. anomaly notes showing sensor lag and a fan-regime change

A passing answer must turn that material into a computational-scientist memo, not a code patch and
not generic architecture prose.

All materials in this bundle are synthetic and local to the repository.

## Expected candidate work

Edit only `candidate/model-validation-memo.md`.

Use the evidence packet in `inputs/` to produce a computational-scientist artifact with:

- the system scope and admitted operating range
- explicit governing equations and state variables
- assumptions and admissibility checks
- units and invariants
- validation evidence tied to the stated criteria
- residual interpretation tied to the data
- explicit uncertainty and limitations
- a recommended model disposition
- numbered claims and a final gate decision

## What this bundle tests

- scientific model framing instead of generic design prose
- validation discipline grounded in equations, units, and measured traces
- explicit treatment of uncertainty and model limits instead of false certainty
- role fidelity for `R11 $computational-scientist`

## Bundle map

- `inputs/` holds the immutable evidence packet
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected model read, validation anchors, and anti-patterns
- `verifiers/` checks bundle shape and the completed memo
