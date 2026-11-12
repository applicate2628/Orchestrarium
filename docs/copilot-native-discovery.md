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
six selected installed source files byte-for-byte with the checkout; this is not
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

This composed test passed on the inspected installed runtime. It still does not
exercise the editor session target, trust UI, enterprise controls or model/tool
lifecycle. No production code change was needed to make the existing owners
compose correctly.

## Terms and Abbreviations

- SDK: software development kit.
- API: application programming interface; the test uses an internal native API.
- JSON: JavaScript Object Notation, the hook configuration format.
- cwd: process working directory.
- Native parser acceptance: the installed runtime recognizes the supplied hook
  configuration, distinct from execution in an editor session.
