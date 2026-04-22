# N24 Systems Toolchain Staging Repeat

This diagnostic bundle repeats the systems/toolchain signal from `N19` on a different
implementation surface: artifact staging instead of build-gate cache planning.

The candidate must repair only the editable `candidate/workspace/src/stagegate/*.py`
implementation files and the local tests named in `scenario.yaml`.
