# Reuse before hand-rolling

## Fundamental rule

Do not build a non-trivial generic capability from scratch when a repo-standard mechanism, framework feature, installed dependency, or mature optimized library/tool can satisfy the requirement.

The rule is not "always add a dependency." It is a build-vs-buy gate:

- first look for existing repository mechanisms and installed dependencies;
- when local options or current knowledge are insufficient, or the tradeoff is consequential, proactively research relevant current mature solutions;
- present meaningful alternatives with benefits, constraints, and integration cost;
- only hand-roll when the user explicitly asked for a from-scratch implementation or evidence shows the existing options fail the task's constraints.

This is a targeted decision step: it neither requires web search nor creates a report gate for every task.

This applies especially to parsers, serializers, schedulers, queues, caches, auth, crypto, date/time handling, numeric solvers, geometry kernels, rendering engines, diff/merge engines, test harnesses, retry/backoff logic, rate limiting, database/query layers, workflow engines, and UI/game/animation logic with established libraries.

Stack choice is part of correctness. Choose the stack that best satisfies correctness, fit, maintainability, performance, security, licensing, platform, and integration constraints; do not choose the fastest familiar development option unless the user explicitly scoped the work for speed/prototype/throwaway delivery. Runtime speed remains a performance constraint; for application optimization, runtime speed may be the primary constraint.

## C and C++ application

When implementing or materially changing C or C++, make the build-vs-buy assessment early enough to shape efficient, compiler-friendly source and interfaces. Assess accepted optimized libraries and toolchain facilities against representative workload benefit, application programming and binary interface fit, numerical behavior, portability, licensing, and build-dependency fit; every new dependency keeps normal admission. Favor analyzable loops and dependencies, locality, suitable contiguous layouts, truthful aliasing and alignment information, and only semantically required opaque calls, volatile access, or barriers. Preserve correctness and readability; substantiate speedup claims with representative measurements and compiler-specific claims with that compiler's optimization remarks or assembly. This creates no universal profiling gate and no blanket requirement for force-inlining, `restrict`, fast-math, intrinsics, or undefined behavior.

## Operational test

Before implementing a non-trivial capability, answer these checks:

1. Is this capability generic enough that established solutions commonly exist?
2. Does the repo already have an owner, helper, framework feature, or installed dependency for it?
3. If local options or current knowledge are insufficient, or the tradeoff is consequential, what relevant current mature solutions were researched?
4. What constraints matter: correctness, performance, licensing, bundle size, security, platform support, API stability, maintainability, offline/runtime requirements, and integration cost?
5. What meaningful alternatives, benefits, constraints, and integration costs were presented, and what stack choice best satisfies them?
6. Is hand-rolling explicitly requested, or is it justified by evidence rather than development speed/convenience?

If the answer to 1 is yes and the answer to 6 is no, do not write the capability from scratch.

## Allowed hand-rolled implementations

Hand-rolling is allowed when one of these is true:

- the user explicitly requested a from-scratch implementation;
- the requirement is small, local, and not a reusable generic capability;
- existing options are unavailable in the target environment;
- existing options fail a verified constraint such as correctness, performance, licensing, security, deployment size, or platform support;
- the repo already owns a custom implementation and the task is to extend that owner rather than introduce a parallel mechanism.

## Commit discipline

For implementation commits that hand-roll a non-trivial generic capability, state:

- the rejected repo-standard and library/tool options;
- the evidence or explicit user instruction that justifies hand-rolling;
- the owner of the new capability;
- the tests or benchmarks that cover correctness and performance-sensitive behavior.

## Banned justifications

These are not valid reasons to hand-roll:

- "It is faster to develop if I just write it."
- "The library would take time to learn."
- "This parser/cache/scheduler is simple."
- "We can replace it with a library later."
- "I know the algorithm, so no need to check."
- "Avoid dependencies" without a repo-standard constraint.
- "This stack is quicker for me."

## Terms and Abbreviations

- **Build-vs-buy gate**: the decision point where an implementation chooses between existing mechanisms and a new custom implementation.
- **Hand-roll**: implement custom logic from scratch instead of using an existing repo mechanism, framework feature, installed dependency, or mature optimized library/tool.
- **Mature optimized library/tool**: a maintained external solution with enough adoption, documentation, versioning, compatibility evidence, and fit for the task's correctness/performance constraints.
- **Repo-standard mechanism**: an existing repository-owned helper, subsystem, framework convention, dependency, or script that already owns the relevant capability.
- **Stack choice**: the selection of repository mechanism, framework feature, dependency, library/tool, service, or custom implementation used to deliver a capability.
- **Runtime speed**: application execution speed, latency, throughput, or responsiveness; a performance constraint, not the development-speed shortcut this rule rejects.
