# Operator Signals

Current rules:

- quota is `REQUEUE` / `NOT-RUN`, never verifier `FAIL`
- wrapper timeout is not a clean `PASS` even when the generated artifact can be manually verified
- wrapper timeout remains retryable while an explicit attempt budget is still available
- denominators must count only scoreable cells unless a table explicitly says it is an artifact diagnostic
- the sample row fixture must produce scoreable summary `1/2`; any composed result like `1/5`
  shows the causal path still mixes non-scoreable cells into the final read
