# Lean Implementation Policy

Use this optional policy only after the task, owning boundary, callers, and required behavior are understood.

1. Confirm that a new implementation is necessary; do not build speculative behavior.
2. Reuse the owning repository helper, type, protocol, or established pattern before adding another one.
3. Prefer the language standard library and native platform capability over custom infrastructure.
4. Prefer an already admitted dependency over introducing a new dependency.
5. Make the smallest coherent owner-level change that fixes the general cause rather than one visible symptom.
6. Keep the number of new abstractions, files, configuration keys, and compatibility paths proportional to demonstrated consumers.
7. Leave the smallest runnable verification that would fail if the non-trivial behavior regressed, while still running every repository-mandated check.

This policy never removes or weakens input validation at trust boundaries, security controls, authorization, data-loss prevention, recovery, accessibility, observability required by contract, explicit user requirements, mandatory tests, review gates, or publication controls.

When a deliberately simple implementation has a known ceiling, record the ceiling and a measurable trigger for revisiting it in the existing work-item or decision record. Do not create a parallel debt system solely for this policy.
