# vcpkg Builder Runtime Reference

## Command profiles

Select exactly one profile from the accepted plan:

- Targeted base: the repository-defined single-port wrapper with one exact port/triplet selection.
- Targeted release: the repository-defined release selection, only after its base prerequisite passes when the plan requires that ordering.
- Aggregate: one explicitly named repository wrapper and arguments; never substitute an aggregate for targeted validation or vice versa.
- Diagnostic/read-only: no build command; inspect only the admitted logs and MCP surfaces.

There is no universal full-lane-first rule. The user and accepted plan own whether the next gate is targeted or aggregate. A failure stops the admitted invocation sequence unless the plan already authorizes the next command under an explicit condition.

## Root policy

- Find the repository's canonical selector, environment overrides, and root-order documentation before probing candidates; never invent a drive, mount, home-directory, or checkout fallback.
- Classify each resolved path by lifecycle: transient build, package staging, durable install/cache, aggregate, routing sentinel, scratch evidence, or external vcpkg checkout.
- Apply protected/prohibited paths from the current repository contract and accepted plan. Do not copy machine-specific paths from a previous repository, user profile, drive layout, WSL distribution, or session.
- Verify repository-defined external-root guards before and after any wrapper that can touch the checkout. A wrapper-owned pull requires explicit user authorization; a separate pull is a separate command and needs its own admission.

## Runtime evidence

For every build record:

- exact wrapper argv and invocation count;
- UTC start/end and pre-run cutoff;
- selected buildtrees, packages, install, cache, and scratch roots;
- relevant source/artifact hashes and current MCP facts;
- wrapper exit and the port/triplet terminal result;
- requested generated-build evidence such as Ninja rules, response files, compiler commands, effective flags, patch order, or installed markers;
- absence/presence checks bounded to current-run files and timestamps;
- post-run process query proving descendants are reaped;
- exact retained evidence paths on failure.

For an admitted crash or performance claim, require evidence from the repository's designated debugger, profiler, trace, or benchmark surface. A clean build or exit code alone does not prove the runtime root cause or performance budget.

For a release gate, confirm the optimization invariant declared by the repository's owning triplet/toolchain profile, including any explicit per-port exemption. Do not assume a flag from the compiler family alone, and do not generalize a base PASS to release or one triplet PASS to another.

## Result ownership

| Last proven stage | What the result proves | Target-port status |
|---|---|---|
| Admission or validation harness | The harness admitted, refused, or failed and its resources settled | `UNVERIFIED` unless separate target evidence exists |
| Wrapper or dispatch | Root selection, environment, mount/session, or child-launch behavior | `UNVERIFIED` |
| vcpkg resolution/plan | Overlay/triplet selection and dependency planning | `UNVERIFIED` for compile/install behavior |
| Target build | The named port/triplet reached configure/compile/link with current-run evidence | `PASS` or `REVISE` only for the proved build criteria |
| Install/package receiver | Current artifacts were installed and inspected by the requested oracle | Eligible for the admitted runtime verdict |

An already-installed exit-zero path is a no-op, not receiving-side proof of a new source/toolchain fix. Preserve the durable install family, and request a separately admitted fresh-build mechanism rather than deleting shared state implicitly.

Triplet names do not universally own storage identity. Repositories may strip release or feature suffixes for a shared durable install family while retaining full variant names for buildtrees and packages. Read the repository's resolver output and record every resolved identity explicitly.

## Stop rules

Stop without retry, cleanup, or command substitution when:

- a preflight criterion fails;
- the selector resolves an unexpected root;
- a protected surface would overlap another active build;
- the wrapper or requested port/triplet fails;
- a required runtime oracle is absent even though the build exits zero;
- source, plan, artifact, or external-root state drifts;
- a new failure class invalidates the accepted diagnosis;
- a child remains running or process ownership cannot be established.

Preserve the exact failing tree and logs. Return control to the root lead for diagnosis, planning, or review.
