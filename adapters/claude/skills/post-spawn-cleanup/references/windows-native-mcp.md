# Windows native MCP settlement, when supported

Read this only for an existing selected native endpoint whose caller needs physical resource settlement. This is a conditional operating method, not a required Windows stack, executable helper or permission to sweep host processes. Prefer an already-supported exact-context release API with sufficient creator binding and proven teardown semantics.

## Bind the public observation to its actual child

The observed endpoint exposes its own public request metadata through `nodeRepl.requestMeta.threadId`. In a runtime that currently supports this surface, an authorized direct self-probe can pair that value with its own executable ancestor chain. The observed method used Node's `node:child_process` module and synchronous `execFileSync`, calling an already-available Python interpreter with `psutil.Process().parents()`. It returned only the current thread ID and each ancestor's `pid`, `ppid`, `name` and `created` (`create_time()`). Use the caller's accepted finite probe budget and retain the actual public result.

This is an example of available APIs, not a hardcoded tool dependency. Discover the fitting tool/capabilities at runtime. Do not install a missing dependency, start another MCP endpoint for comparison, dump arguments/environment/credentials, inspect broad private sessions, or substitute hidden metadata. A runtime may not expose a general Node `process` global; do not assume one. If this particular route is absent, use a different already-supported sufficient proof route or preserve the unknown resource.

Match the returned thread to the exact caller-issued child/task, including its actual terminal state after the probe. The self-chain is evidence about this endpoint, not every process beneath a provider host. Select only endpoint roles whose context ownership was positively established. Provider/editor ancestors and other shared contexts are protection subjects, not termination targets. Parent/time/name similarity cannot extend the selection to another MCP family or an unbound thread.

A self-probe can lazily start a server or kernel. Use pre-probe launch/creation evidence when available, distinguish newly probe-created objects, and retain unknown prior existence. Do not call every selected exit a pre-existing orphan removed or a performance saving. Case counts, timestamps and machine identities belong in the existing task evidence, never as workflow defaults.

## Retain native objects before acting

For an authorized Windows operation with .NET process APIs available:

1. Capture the selected subject and protected identities from the accepted context binding. Obtain each current `System.Diagnostics.Process` and retain its `SafeHandle` before mutation. A fresh process lookup is acquisition, not ownership proof.
2. Compare the acquired `StartTime.ToUniversalTime()` on the same UTC Unix-seconds basis as the observation's `created` value, and compare the actual `ProcessName` with the observed executable-name representation. Account explicitly for the API's executable-suffix representation; do not broaden matching to patterns. If identity equivalence cannot be established, preserve the object rather than widening a time tolerance. Native handles, selection and protection checks must remain live through the action.
3. An already-exited original object is a no-op. A current object with a different creation identity is PID reuse and must remain untouched. Preserve the current orchestrator/editor and all unselected or shared services, even when ancestry is common.
4. After the selected child is terminal and authority still applies, use the supported graceful release if effective. If the admitted operation requires termination, invoke `.Kill()` on the same retained selected `Process`, then `.WaitForExit(...)` with the caller's actually accepted wait budget. Do not use a process-tree option, reacquire a different target by PID, or terminate a parent/group. A request that throws, times out or is refused retains that actual outcome; no shell fallback follows a host denial.
5. Independently acquire read-only current identity/absence observations. An absent PID, or a reused PID with a different creation identity, establishes absence of the original selected identity without granting authority over the new object. Also verify required protected identities against their retained creation/name binding. This readback is distinct from `.Kill()`/`.WaitForExit()` success.
6. In `finally`, dispose every retained selected/protected `Process` and separately retained handle as appropriate to actual ownership; do not abandon handles on an early return, mismatch, readback error or serialization failure. Report incomplete disposal as incomplete settlement, not a clean result.

These library calls describe the observed handle-bound method. They do not ship a new script, native interop layer or process-control framework. If the host's current APIs or identity representation cannot preserve these guarantees, stop the dependent action and retain the exact unknown. Do not replay historical PIDs or start fresh resources solely to test termination.

## Preserve the result's limits

Retain actual context binding, selected/protected observations, method outcomes and independent readback in the existing caller result/artifact before optional formatting. Separate execution, capture, persistence and interpretation failures; later errors do not erase acquired results or prevent required settlement. Missing public host finalization remains unknown, not an invented release receipt.

A successful selected endpoint cleanup proves that selected scope only. Other MCP families or unbound host contexts remain protected and unclassified. File-trash disposition and historical evidence retention remain with their existing owners; neither substitutes for native object settlement.

## Terms and Abbreviations

MCP: Model Context Protocol. PID: process identifier. UTC: coordinated universal time. .NET: Windows runtime exposing `System.Diagnostics.Process`. SafeHandle: managed owner of a retained operating-system handle. Probe-created: started by the ownership observation itself, rather than proved present beforehand.
