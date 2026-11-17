# Windows Job initial presentation

## Orche public contract
WindowsJobOwnerV1.launch accepts the keyword-only presentation option:
- default: unchanged behavior, with no explicit show-window flag.
- hidden: request hidden initial presentation through STARTF_USESHOWWINDOW and SW_HIDE.

The type is Literal["default", "hidden"]. Other values fail with WJOB-REQUEST at
launch before native resource allocation. Non-Windows calls still fail with
WJOB-UNAVAILABLE. The existing v1 module identity contract remains compatible;
its marker alone does not prove this newer optional capability is installed.

Add presentation="hidden" to the caller's existing authorized launch operation.
Keep its environment, creation gate, before-resume observation, stream ownership,
creator/session joins and settlement unchanged. Do not alter CreateProcessW
arguments inside an observation callback to simulate this option.

## Native behavior and limits
Microsoft's [STARTUPINFOW contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfow)
requires the show-window flag for wShowWindow to apply. This is an initial
presentation request, not containment of every future window. An application can
later display UI; consumer-specific behavior still requires qualification.

The option does not change creation flags, priority, creation-time Job assignment,
suspended creation, membership verification, pre-resume ordering, inherited
standard handles or all-exit settlement. It supplies no launch permission and
does not grant control over an existing foreign process or session.

## Qualification and receiving
Tests observe the startup fields without modifying them, inspect the fields
received by a real Python child, and retain default behavior, real creation
failure, creation-gate callback failure, no-resume failure and descendant-settlement coverage.
A hidden console test parent keeps default-mode console fixtures out of view.
No GUI application, solver or export is part of this qualification.

Source tests do not establish installed receiving. Verify the installed owner
and its public parameter in a fresh qualified process before relying on it.
Do not hot-swap an active owner or its handles across module instances. A caller
that already imported the old owner has not gained a parameter merely because
the file was updated.

## Terms and Abbreviations
Job: Windows object owning the created process and its descendants.
Initial presentation: the startup window-state request, not perpetual invisibility.
Creation gate: the existing caller-controlled boundary around one process creation.
