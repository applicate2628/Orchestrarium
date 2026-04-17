# E1 System And Workload Brief

## Workflow

`cohort-packet-packager` is a local CLI used by benchmark authors and release engineers. For a
named cohort it performs these stages:

1. scan the admitted scenario roots and load `scenario.yaml`
2. materialize a run folder with `inputs/`, `candidate/`, `oracle/`, and `verifiers/`
3. compute a per-file SHA-256 hash manifest for the staged packet
4. emit a redacted replay packet and a compressed archive for each scenario
5. write a cohort summary index used by later local replay and review tools

The flow is intentionally non-web. It runs on a workstation during author iteration and on a
single CI worker during release rehearsal.

## Reference environments

- author workstation: 8-core laptop CPU, 32 GiB RAM, local NVMe SSD
- release worker: 8 vCPU VM, 16 GiB RAM, attached SSD

## Admitted workloads

- author loop: `6` scenarios, `3.2 GiB` total staged input bytes before compression
- release rehearsal: `12` scenarios, `6.5 GiB` total staged input bytes before compression
- stretch observation only: `24` scenarios, not part of the budget gate but used to understand
  scaling direction

## Required invariants

- every staged file must remain represented in the hash manifest
- replay packets must preserve byte-stable redaction output
- the same cohort definition must produce the same summary ordering across repeated runs
- no remote cache, browser, daemon, or background worker is allowed in the admitted design
