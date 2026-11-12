# Copilot bundled advisory entry

The first executable Copilot slice is a machine-local-path **advisory**, not the
publication gate or a complete Orchestrarium dispatcher. It reuses the canonical
machine-path detector. It examines written content only for `create`,
`create_file`, and `replace_string_in_file`; unknown tools remain neutral.
Path findings return additional context, never a permission upgrade or denial.
Malformed/oversized input returns exit 2 and can block under the documented host
contract. This is not a blanket “never blocks” promise.

Build the normal qualified Windows bundle, retain it under the project, then run:

```powershell
.\runtime\python\python.exe -I -B .\runtime\app\install.py --copilot-registration --project . --bundled-advisory-relative runtime
```

This previews the exact dedicated registration. Add `--apply` to create it;
updating/removing still requires the existing explicit `--previous` selection.
The generator checks the supplied interpreter, adapter, codec, canonical detector
and its shared import are present and resolve within the selected bundle.
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
