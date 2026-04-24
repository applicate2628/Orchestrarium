# N47 UI Compact Operator-Budget Hotfix

This diagnostic bundle hardens the UI implementation signal from `N20` and `N25` with an
immutable visible-test constraint and a visible low-noise operator budget. The worker must repair
editor state, rendering, and CSS behavior without changing the fixed visible test baseline and
without exceeding the runner transcript budget declared in `inputs/task.md`.
