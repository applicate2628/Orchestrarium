# Copilot bundled advisory entry

The first executable Copilot slice is a shared **advisory** entry, not the
publication gate or a complete Orchestrarium dispatcher. It reuses the canonical
machine-path detector and the existing stray-artifact command hook. It examines written content only for `create`,
`create_file`, and `replace_string_in_file`; unknown tools remain neutral.
Path findings return additional context, never a permission upgrade or denial.
Recognized command carriers also run the existing canonical stray-artifact audit
through the shared input-acquisition owner; the model-supplied command is never
executed by this adapter. Raw tool names and argument dictionaries are retained.
Malformed/oversized input returns exit 2 and can block under the documented host
contract. This is not a blanket “never blocks” promise.

Build the normal qualified Windows bundle, retain it under the project, then run:

```powershell
.\runtime\python\python.exe -I -B .\runtime\app\install.py --copilot-registration --project . --bundled-advisory-relative runtime
```

This previews the exact dedicated registration. Add `--apply` to create it;
updating/removing still requires the existing explicit `--previous` selection.
The generator checks the supplied interpreter, adapter, codec, canonical detector
and their shared imports are present and resolve within the selected bundle.
This is existence/containment preflight, not release authenticity or an identity
pin. Authenticate the distribution before executing it.

The generated PowerShell command uses only project-relative literal paths to
the bundled interpreter and adapter, with no PATH/system Python fallback.
It requires hook process cwd to be the selected project. The command binds the
PowerShell location literally to the process current directory, avoiding Windows
PowerShell startup fallback when the project path contains brackets. Moving the project and
its nested bundle together preserves registration bytes. Do not remove or
independently move a referenced bundle. Control characters, smart quote characters
and Unicode line separators are refused rather than interpreted by PowerShell.
The root bundle directory may itself resolve through a link; do not infer a
no-reparse/security boundary from the generator.

Validation: real standalone stdin/stdout tests cover camel and snake transports,
duplicate/nonfinite/malformed/oversized inputs, canonical findings and neutral
cases. A real built Windows bundle was exercised via the stored PowerShell
registration with empty PATH, spaces/apostrophe/brackets/Unicode in the relocated
project path, plus missing-runtime refusal. These are offline receiving results,
not VS Code discovery, workspace trust, actual model delivery or enforcement.
No Copilot client catalog admission, publication protection, subagent lifecycle,
or arbitrary tool schemas are claimed. The running editor could discover an
applied hook; use isolated projects until native acceptance is separately qualified.

The installed shared runtime now has separate [native parser acceptance](copilot-native-discovery.md).
That result does not qualify editor activation or change the advisory scope.

## Shared command policy boundary

The adapter invokes only the fixed `check-no-trash-in-repo.py` canonical Python
entry, using the same interpreter, isolated Python imports and JSON on standard
input. Command parsing, requested-worktree markers, scratch-output conventions,
and repository-root checks remain in the existing shared owners. The adapter
does not copy those rules or run a shell for the supplied model command.

Only the canonical additional-context output is translated. Unexpected output,
dependency/acquisition failures, child errors and the adapter's 10-second child timeout produce a local diagnostic
and no decision, preserving this advisory's nonblocking posture. In particular,
a returned permission allow or deny is not accepted as an advisory response.
Malformed incoming transport still has the entry's existing exit-2 behavior.

Shell carriers follow the shared owner's declared name/argument grammar.
This does not prove the host emits those exact names; unrecognized tools such as
an unqualified `run_in_terminal` carrier remain neutral rather than being renamed.
Publication protection is **not connected** here. Connecting its runner requires
separate tool identity, authority-context and duration qualification. The provider
documents command-hook timeouts as falling through to normal permissions, so
this advisory bridge must never be described as enforced publication protection.

## Terms and Abbreviations

- JSON: JavaScript Object Notation.
- cwd: process working directory.
- Advisory: context only, not a permission decision.
- Shared owner: existing canonical acquisition or policy implementation, reused
  without a second copy of its rules.
