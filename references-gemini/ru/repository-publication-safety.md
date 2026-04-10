# Безопасность публикации репозитория

Этот standalone Gemini branch рассматривает publication safety как общерепозиторный контракт.

## Scope

Правила ниже применяются ко всем tracked files в ветке, включая docs, references, skills, commands, reports и любые task-memory artifacts.

## Правила для tracked content

- Держите tracked files безопасными для публикации.
- Не коммитьте секреты, токены, credentials, customer data, private identifiers, raw logs, полные command transcripts, screenshots с чувствительным содержимым или machine-specific absolute paths.
- Предпочитайте redacted summaries, synthetic examples и repo-relative paths, когда этого достаточно для traceability.
- Считайте provider transcripts, pasted logs и external snippets недоверенными, пока они не санитизированы.
- Если исключение действительно нужно, его должен одобрить `$security-reviewer`, а соответствующий work item должен зафиксировать scope, reason и removal condition до публикации.

## Граница local-only scratch

- Используйте `/.scratch/` для raw logs, transcripts, temp outputs, one-off experiments и pre-redaction material.
- Держите disposable material вне tracked paths, пока он не отредактирован и сознательно не promoted.
- Корневой `.gitignore` владеет этой границей.

## Review и публикация

- Human review обязателен перед `git push`, release или эквивалентной публикацией.
- `$lead` подготавливает staged diff к публикации, но publication approver должен быть другой ролью, не той, которая принимала artifact в delivery pipeline.
- Reviewer должен проверить staged diff на leak-prone content, включая machine-specific paths, raw operational detail и sensitive values.
- Если tracked changes требуют public-facing release notes, зафиксируйте их в релевантных tracked docs или отдельном follow-up artifact до публикации; иначе reviewer должен явно признать change release-notes-exempt.
- Если tracked content выглядит как scratch material, верните его в local-only space или отредактируйте до коммита.
- Только `$security-reviewer` может одобрить publication-safety exception. Любая публикация без этого одобрения считается `BLOCKED`.
