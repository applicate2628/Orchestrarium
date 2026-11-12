# Copilot native parser acceptance

## What was verified (2026-11-12)

The installed VS Code Insiders distribution was inspected without starting the
editor: version 1.146.0-insider, commit
`6bd30dab6e29addbe64365b91e27e20e611f064c`, build 2026-11-10.
It ships Copilot Chat 0.74.2026111002 and the shared Copilot runtime 1.0.73
(build metadata commit `98003c0`).

The runtime's own native hook loader accepted the generated
`--bundled-advisory-relative` registration:
- Empty isolated hook session: zero hooks.
- Repository load: exactly one `preToolUse` hook and one resource, not a policy.
- Parsed command configuration exactly matched the generated JSON.
- No loader warnings or errors.
- A separate malformed JSON fixture produced diagnostics and zero hooks.

Only native hook loading, snapshots, resource enumeration and disposal were
called. No hook command, chat/model session, plugin, policy discovery, authentication
or editor window was started. User directories/settings were isolated.
The earlier shell/bundled-Python receiving remains separate evidence for execution.

## Repeat the opt-in test

Select the installed official runtime's `runtime.node` and Node executable explicitly
through `ORCHE_COPILOT_NATIVE` and `ORCHE_NODE`, then run
`tests/test_copilot_native_discovery.py`. Without both selections the test skips.
The test uses `tests/fixtures/copilot_native_discovery.cjs` and disposable directories;
its generated executable fixtures are deliberately not executable.

This is an internal version-specific runtime API, not a stable public SDK contract.
If the API changes, investigate the installed implementation rather than treating
the failure as proof that the editor does not support hooks.

## What this does not prove

A native parser result is not editor discovery in the user's selected session,
workspace trust, native tool payload coverage, context delivery, tool denial or
enterprise-policy compatibility. It does not upgrade the advisory adapter into
the publication gate or a complete Copilot integration.

The official editor workflow requires selecting the **Copilot** session target,
checking the Hooks page for duplicate sources, then starting a disposable session
and triggering a harmless tool call. That final model/tool-session check was not
performed. It needs separate permission under this project's run rules.
Seeing a hook in the editor alone would still not prove execution.

Sources inspected:
- https://code.visualstudio.com/docs/copilot/customization/hooks
- The installed Copilot SDK's `createNativeHookSession`, `getHooksDir`, and
  deferred repository-hook loading code.
The SDK selects the Git root for repository hooks when host Git operations are
enabled; otherwise it uses the working directory. The test supplies its isolated
repository root explicitly, so it does not qualify Git-root detection.

The repeatable test does not pin or authenticate those binaries: its result applies
to the explicitly supplied runtime. The version above was separately inspected
for this run. The report execution flag describes the harness call surface, not
an independent trace of every internal native instruction.

## Composed installed receiving

A separate opt-in test, `tests/test_copilot_installed_receiving.py`, requires
`ORCHE_COPILOT_BUNDLE` in addition to the explicit native parser and Node paths.
Supply a freshly assembled Windows bundle from this source. The test compares
eight selected installed source files byte-for-byte with the checkout; this is not
full release authentication.

The verified chain uses the supplied interpreter and bundle `launch.py` with
`--permanent-runtime`, then the normal root registration entry. It checks preview,
apply and unchanged reapply without creating another installation owner. A foreign
hook file remains intact. The actual native parser loads that installed registration,
and a standalone PowerShell process executes the exact command returned in its
parsed configuration, not a reconstructed command.

Positive machine-path advisory, neutral input and malformed-input refusal pass
before and after moving the project and nested runtime together. Registration
bytes remain unchanged; a missing bundled executable fails without a system
Python fallback. The command environment has empty PATH, isolated user/config
folders, the Windows system root and `PATHEXT=.EXE`. Windows PowerShell needs
PATHEXT to classify a native executable even when its path is explicit; omitting
it initially broke this overly stripped fixture, not the real adapter.

The same composed test also verifies a portable runtime-path change through the
root update entry: no prior selection refuses without mutation; preview leaves
bytes intact; a user edit after selection refuses as stale; exact selected update
retains the previous registration in project trash and the native parser discovers
the replacement. The exact replacement command executes the advisory cases.
Selected removal retains its previous bytes in trash, native discovery then finds
zero hooks, and repeated removal is unchanged. The foreign hook file remains
byte-identical and the bundled interpreter remains present. These results qualify the existing selected-file
lifecycle, not automatic ownership adoption or whole-runtime uninstall.

This composed test passed on the inspected installed runtime. It still does not
exercise the editor session target, trust UI, enterprise controls or model/tool
lifecycle. No production code change was needed to make the existing owners
compose correctly.

## Actual native hook execution without a model

The composed receiving test additionally invokes the installed native hook processor
itself, not only the command extracted from its parser. The harness mirrors the
installed SDK wrapper's `hookProcessorConfigure`, `hookProcessorPreToolUse`, and
`hookProcessorCompletePreToolUseLifecycle` calls on a hook-only session. It loads
only the selected native module, never creates an SDK client or chat/model session,
and executes no proposed tool. The environment contains only isolated test paths
and Windows shell support, not ambient credentials or user configuration.

Four cases run before relocation, after relocation, and after selected update:
canonical command advisory, machine-path advisory, neutral content, and unknown
tool. The native processor delivers the expected additional context without a
permission allow, ask or denial. Proposed output files and worktrees do not appear.
Each lifecycle is completed and asynchronous end callbacks are awaited before
session disposal. The five-second callback deadline is a test failure bound, not
a production timeout or permission policy. The parent process also has a bounded
execution timeout.

This is observed installed native execution for the previously identified runtime,
not a stable public native API contract. Editor workspace trust, session activation,
model delivery, enterprise policy and publication enforcement remain unqualified.
The provider shell runner needs PowerShell discovery, so this native test supplies
only its Windows directory in PATH; the hook itself still addresses bundled Python
by a relative literal path and has no system-Python fallback.

## Terms and Abbreviations

- SDK: software development kit.
- API: application programming interface; the test uses an internal native API.
- JSON: JavaScript Object Notation, the hook configuration format.
- cwd: process working directory.
- Native parser acceptance: the installed runtime recognizes the supplied hook
  configuration, distinct from execution in an editor session.
