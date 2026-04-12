# Security Review — Orchestrarium Monorepo

**Date:** 2026-04-09  
**Stage:** security-reviewer  
**Gate:** PASS  

## Findings

| ID | Finding | Severity | Class |
|----|---------|----------|-------|
| F-01 | Predictable temp file path in `install-codex.ps1:430` | MEDIUM | WARNING |
| F-02 | `rm -rf` scoping — validated paths only | INFO | PASS |
| F-03 | Bash variable quoting — consistent double-quotes | INFO | PASS |
| F-04 | Command injection surface — no dynamic execution | INFO | PASS |
| F-05 | `.gitignore` coverage — all sensitive patterns excluded | INFO | PASS |
| F-06 | Hardcoded paths — only in documentation examples | INFO | PASS |
| F-07 | No file permissions set on installed governance files | LOW | WARNING |
| F-08 | Governance files as AI control surface — inherent to design | LOW | WARNING |

## Required fixes: None

## Optional hardening

1. Replace predictable temp path in `install-codex.ps1` with `New-TemporaryFile`
2. Consider integrity verification (checksum) for installed governance files
