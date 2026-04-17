# Accepted Performance Budgets

- dashboard refresh should stay comfortably under one frame for a typical cohort
- memory growth should remain bounded during repeated metric updates
- review target should avoid repeated full payload serialization in the hottest path
