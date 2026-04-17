# Anti-Patterns

The following patterns should lose major points in `S09`:

1. rewriting the task as repository research, architecture redesign, or review findings instead of
   a phase plan
2. embedding implementation code, diffs, or command transcripts inside the plan
3. placing docs or QA work before the JSON contract and `--dry-run` behavior are stabilized
4. widening the file scope into runner, scorer, results, or archive surfaces
5. omitting dependencies, tests and checks, or rollback notes for one or more phases
6. inventing an implementation workspace inside `candidate/` instead of keeping the artifact
   plan-only
