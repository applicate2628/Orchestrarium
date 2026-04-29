# Seam Options

## Option A - Consumer Dispatch Normalization

Each adapter normalizes `externalPriorityProfiles` just before dispatch.

Problem: duplicates policy parsing across worker and reviewer adapters and lets transport code own
lane semantics.

## Option B - Agents-Mode Loader Normalization

The agents-mode loader resolves singular compatibility input, validates lane-specific profile keys,
and emits one normalized profile catalog.

Benefit: one owner for policy parsing, adapters stay transport-only, and route facts like the `X4`
secret wrapper remain runtime constraints rather than policy keys.

## Option C - Provider Fallback Profile

Each provider carries its own default profile and the selected provider fills missing lane policy.

Problem: provider defaults silently override lane routing intent and make missing profile errors hard
to diagnose.
