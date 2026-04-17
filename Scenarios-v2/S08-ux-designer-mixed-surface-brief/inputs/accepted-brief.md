# Accepted Brief

## Background

The benchmark release workflow intentionally spans two surfaces:

- the desktop `Scenario Workspace`, used by curators to assemble bundle files from local fixture
  directories, inspect local validation output, and prepare a candidate release packet
- the web `Review Console`, used by reviewers and approvers to compare staged bundles, request
  changes, confirm governance checks, and publish approved updates into the shared scenario index

This split is deliberate because the desktop workspace needs direct local filesystem access and the
web console needs shared review history plus publish permissions. The UX problem is not whether the
two surfaces should exist. The UX problem is how to make their relationship coherent.

## Primary users

- `Curator`: prepares or revises a scenario bundle in the desktop workspace
- `Reviewer`: reviews the staged packet in the web console and can request changes
- `Approver`: confirms the final publish step in the web console when the packet is ready

## Goals

1. Make the handoff from desktop preparation to web review unambiguous.
2. Use one visible state model across both surfaces so users can tell what is blocked and why.
3. Make the change-request loop explicit so curators re-enter the right desktop step.
4. Keep the desktop surface focused on local preparation and the web surface focused on shared
   review and publish decisions.

## Protected surfaces

- filesystem access and local validation remain desktop concerns
- shared review history, approval, and publish remain web concerns
- the brief may change the structure, labels, sequence, and handoff behavior, but it must not
  collapse the workflow into a single implementation surface

## Required design emphasis

The output must show explicit information architecture, flow restructuring, and state ownership.
It should be concrete enough for later implementation or review lanes to consume, but it should
not contain component-level build instructions, code diffs, or reviewer findings.
