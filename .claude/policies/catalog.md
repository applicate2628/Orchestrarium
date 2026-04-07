# Policy Catalog

Each policy area has a key, a question for the user, available options, and a default. The `/init-project` skill uses this catalog to guide onboarding. The result is written to `## Project policies` in CLAUDE.md.

## testing-methodology

**Question:** How should tests be written in this project?

| Option | Description |
| --- | --- |
| `tdd` | Test-driven: write failing test first, then implement, then refactor (RED-GREEN-REFACTOR) |
| `test-after` | Write tests after implementation, before merge |
| `minimal` | Tests only for critical paths and regressions |
| `none` | No testing policy enforced |

**Default:** `test-after`

## coverage-target

**Question:** What test coverage target should agents aim for?

| Option | Description |
| --- | --- |
| `90` | Strict — 90%+ line coverage |
| `80` | Standard — 80%+ line coverage |
| `60` | Pragmatic — 60%+ for core logic |
| `none` | No coverage target enforced |

**Default:** `none`

## commit-format

**Question:** What commit message format should be used?

| Option | Description |
| --- | --- |
| `conventional` | Conventional Commits: `type(scope): description` (feat, fix, refactor, docs, test, chore, perf, ci) |
| `descriptive` | Free-form but descriptive: summary line + optional body explaining why |
| `custom` | Project-specific template (user provides format) |

**Default:** `descriptive`

## branching-model

**Question:** What branching strategy does this project use?

| Option | Description |
| --- | --- |
| `trunk` | Trunk-based: short-lived feature branches, merge to main frequently |
| `gitflow` | Gitflow: develop/release/hotfix branches with main as stable |
| `simple` | Simple: feature branches off main, no develop branch |

**Default:** `simple`

## file-size-policy

**Question:** Should agents flag large files?

| Option | Description |
| --- | --- |
| `strict` | Hard review trigger at 400 lines, split required at 800 |
| `moderate` | Soft guidance: prefer under 500 lines, review at 800 |
| `none` | No file size policy — rely on readability judgment |

**Default:** `none`

## error-handling

**Question:** How should errors be handled?

| Option | Description |
| --- | --- |
| `explicit` | Every operation that can fail must handle errors explicitly |
| `boundary` | Validate at system boundaries only, trust internal code |
| `framework` | Follow the framework's default error handling conventions |

**Default:** `boundary`

## pr-review

**Question:** What is the PR review policy?

| Option | Description |
| --- | --- |
| `required` | All PRs require review before merge |
| `optional` | Review recommended but not blocking |
| `none` | No PR review policy — direct push allowed |

**Default:** `required`

## documentation

**Question:** When should documentation be written?

| Option | Description |
| --- | --- |
| `public-api` | Required for all public APIs, exported functions, and interfaces |
| `decision-only` | Document non-obvious decisions and trade-offs only |
| `minimal` | Only when explicitly requested |

**Default:** `decision-only`

## language-style

**Question:** Are there language-specific style preferences?

This is a free-form field. Examples:
- "Prefer immutable data structures and spread operators (JS/TS)"
- "Use type hints everywhere (Python)"
- "Follow Google C++ Style Guide"
- "No preference — follow existing codebase conventions"

**Default:** `"Follow existing codebase conventions"`

## dependency-policy

**Question:** How conservative should agents be with new dependencies?

| Option | Description |
| --- | --- |
| `conservative` | Minimize external deps; prefer stdlib and existing deps |
| `pragmatic` | Add deps when they save significant effort and are well-maintained |
| `liberal` | Use best available package for the job |

**Default:** `pragmatic`
