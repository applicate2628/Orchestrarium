# Prohibited Patterns

- Do not translate the task into browser or DOM event handling.
- Do not solve the scenario by editing only the direct tests while leaving the dialog behavior
  wrong.
- Do not move focus or keyboard policy into a separate model/view, geometry, or harness layer.
- Do not make the validation label a focus target or tab stop.
- Do not preserve unconditional `Return` acceptance for invalid names.
- Do not leave stale accept or reject state alive across `prepare_for_reopen(...)`.
