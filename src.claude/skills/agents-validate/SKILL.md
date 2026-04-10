---
name: agents-validate
description: Run the structural integrity check for the Claudestrator skill-pack.
disable-model-invocation: true
---
# Validate Skill-Pack

Run the structural integrity check for the Claudestrator skill-pack.

## Steps

1. Run: `bash .claude/agents/scripts/validate-skill-pack.sh`
2. Read the output and present results to the user.
3. If any FAIL or WARN items exist, suggest specific fixes.
4. If all PASS, confirm the skill-pack is structurally sound.

## Rules

- This is a read-only check — do not modify any files.
- Run from the repository root.
