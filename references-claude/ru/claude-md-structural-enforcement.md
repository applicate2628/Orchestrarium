# Детали структурного enforcement для Claude Markdown

Этот provider-local maintainer reference владеет текущим исчерпывающим контрактом хуков Claude Code; это источник документации, а не installed runtime content.

Всегда загружаемый `src.claude/CLAUDE.md` хранит действующие правила структурного enforcement и ссылается сюда за исчерпывающими деталями хуков и инсталлятора.

<!-- BEGIN ORCHESTRARIUM PAYLOAD: structural-overview -->
Пак поставляет тринадцать записей: девять структурных хуков — четыре blocking-enforcement (bugfix-discipline, git-push-gate, passive-polling, MCP force) и пять warn-only аудитов (machine-local-path, no-trash-in-repo, stale-relation-residue, repository-orientation, typed-routing) — плюс четыре reminder/context хука. Это backstop'ы; они не заменяют текстовые правила выше.
Три записи `SessionStart` (`mcp-usage-reminder`, `agents-mode-reminder`, `check-scratch-valuables`) срабатывают на startup/resume/clear/compact; `turn-anchor-reminder` — на каждом `UserPromptSubmit`. Общие reminders выдают структурированный `hookSpecificOutput`-контекст; все четыре fail-open. MCP-напоминание остаётся generic и обнаруживает подключённую серверную поверхность вместо поставки machine-local списка.
`agents-mode-reminder` использует `agents_mode_runtime.resolve_scalar`, единственного владельца Claude scalar-precedence, и выдаёт контекст только для `delegationMode: force|auto`; manual или unresolved остаются молчаливыми. `check-scratch-valuables` read-only и сообщает о ценном содержимом `.scratch/`, не восстановимом из Git. `turn-anchor-reminder` переякоривает продолжение и раннюю Lead-делегацию на каждом пользовательском ходе. Диспатчнутые промпты должны разрешать релевантное использование MCP в пределах роли, scope и safety limits.
<!-- END ORCHESTRARIUM PAYLOAD: structural-overview -->

<!-- BEGIN ORCHESTRARIUM PAYLOAD: hook-behavior-contracts -->
**Хук PreToolUse bugfix-discipline.** `check-bugfix-discipline.py` ловит самое частое нарушение pre-fix дисциплины: модель собирается сделать code-mutating вызов инструмента (`Edit`/`Write`/`NotebookEdit`/`apply_patch`) в ответ на пользовательское сообщение, содержащее сигнал bug-report или change-request (напр. `fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, `поменяй`, traceback, `Error:`), но при этом НЕ вызвала сначала `/agents-bugfix` и иначе не захватила diagnostic data. Хук читает `transcript_path` из конверта PreToolUse, парсит недавний хвост транскрипта и:

- Если конверт несёт `agent_id` (контекст субагента) → exit 0 (разрешить; диспатчащая main conversation владеет diagnostic discipline в момент dispatch-решения, а субагента блокировать нельзя никогда).
- Если целевой путь записи находится под `.reports/`, `.scratch/`, `.plans/`, `work-items/` или `docs/` (совпадение как сегмент, ограниченный `/`, поэтому `src/mydocs/x.py` НЕ освобождается) → exit 0 (разрешить; запись doc/report/scratch/plan/task-memory никогда не является тем CODE-фиксом, на который нацелен этот guard — проверено на реальном транскрипте, где guard легитимно сработал на записи memo в `.reports/` под bug-fix-review промптом без prose-маркера).
- Если последнее пользовательское сообщение не содержит bug-trigger фразы → exit 0 (разрешить; это не bug-контекст).
- Если последнее пользовательское сообщение содержит override-маркер `[skip-bugfix-discipline]` → exit 0 (разрешить; пользователь явно отказался).
- Если текущий turn (всё после последнего пользовательского сообщения) показывает сигналы дисциплины (вызов `/agents-bugfix`, загрузка скилла `agents-bugfix`, текст, содержащий `diagnostic`/`hypothesis`/`reproducing`/`VERIFIED:`) → exit 0 (разрешить; модель следует flow).
- Иначе → выдать структурированный JSON payload `permissionDecision: "deny"`, сообщающий модели точно, как выполнить требование (вызвать скилл, захватить diagnostic data или использовать override-маркер).

**Хук PreToolUse git-push publication-gate.** `check-git-push-gate.py` — это структурный backstop для правила publication-safety «human review до `git push` должен включать leak-check staged-изменений» — прежде существовавшего только как проза, тогда как менее рискованные edit/stop моменты имели блокирующие хуки. Зарегистрированный на matcher `Bash`, он детектирует `git push` в командной позиции той же shell-aware техникой парсера, что и stray-artifact аудит (`git push` внутри кавычек — это данные, а не команда; `git push --dry-run` разрешён всегда), и:

- Если конверт несёт `agent_id` (контекст субагента) → exit 0 (разрешить; зеркалит bugfix guard — субагент не может инъектировать user-side override в главный транскрипт. Governance всё равно запрещает делегировать push субагенту, чтобы увернуться от review).
- Если ПОСЛЕДНЕЕ ПОДЛИННОЕ ПОЛЬЗОВАТЕЛЬСКОЕ СООБЩЕНИЕ содержит per-turn override `[approve-publication]` → разрешить. В отличие от `[skip-bugfix-discipline]`, этот маркер учитывается ТОЛЬКО из собственного сообщения пользователя — никогда из прозы ассистента, вызовов инструментов или вывода инструментов — потому что процитированный или инъектированный контент не должен одобрять публикацию.
- Если последнее подлинное пользовательское сообщение содержит явную инструкцию push (`push`, `запушь`, `залей`, ...) И вызовы инструментов модели в текущем turn показывают вызов publication-safety скана (`check-publication-safety` / `check-publication-gate` / `agents-check-safety`) → разрешить.
- Иначе → выдать структурированный payload `permissionDecision: "deny"` с точными инструкциями по выполнению (сообщить о готовности и попросить пользователя одобрить маркером; или, когда push уже был предписан, сначала запустить safety-скан в этом turn и повторить; или использовать `--dry-run`).

Это BACKSTOP, а не гарантия: push, спрятанный за wrapper-скриптом, `eval` или command substitution, не моделируется, и хук fail-open при любой внутренней ошибке или отсутствующем транскрипте — связующим правилом остаётся текст governance (human review + leak-check до любого push).

**Хук Stop passive-polling.** `check-passive-polling-stop.py` ловит другой сбой: модель собирается завершить свой turn, сказав, что ждёт асинхронный внешний источник (bot/review/CI/job/notification/reply) без релевантной проверки состояния в текущем turn. Хук читает `last_assistant_message` напрямую из конверта Stop, немедленно выходит, когда `stop_hook_active=true`, и парсит транскрипт только после того, как обнаружена passive-polling фраза. Он разрешает user handoff'ы вроде `waiting for your response` / `жду твоего подтверждения`, разрешает per-stop override-маркер `[acknowledge-passive-stop]`, и в остальных случаях требует релевантный probe в текущем turn: команды времени/статуса (`date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`), вывод процесса/задачи или чтения файлов output/log/task. Если релевантного probe нет, он выдаёт top-level `{"decision":"block","reason":"..."}`, предписывая модели проверить состояние сейчас, использовать override для настоящего handoff или вызвать конкретный инструмент вроде `Bash: gh pr view`.



**Пять PreToolUse аудит-хуков (warn-only).** `check-machine-local-path.py` предупреждает, когда machine-local абсолютный путь (конкретный домашний каталог пользователя или dev-корень рабочей станции; плейсхолдеры вроде `<you>`, `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}` разрешены) записывается в файл не под `.scratch/`. `check-no-trash-in-repo.py` (guard от stray-артефактов — имя файла и install-маркер сохранены ради install continuity; переименование в `check-stray-artifact` — отслеживаемый follow-up) предупреждает на каждом уверенно распарсенном `git worktree add`, кроме одного add, чья команда заканчивается точным маркером `# orchestrarium:requested-isolation-worktree`, требуемым установленным протоколом parallel-isolation; отсутствующие, почти-совпадающие, закавыченные, переиспользованные или batch-маркеры не подавляют аудит. `git worktree list/remove/prune`, `git add` (не `git worktree add`), `git` внутри закавыченной строки и не-git команды никогда не предупреждают; парсер shell-aware (shlex-токенизация, отслеживание командной позиции через `&&`/`;`/`|`/`(`, пропуск env-assignment-префикса и git-global-опций) и fail-open при любой ошибке токенизатора. Это заменило name-based версию, которая предупреждала только на новых директориях с именами `kosyaks`/`mistake-log` — бесполезно, потому что это словарь личного процесса *пользователя*, а не имена, которые когда-либо создаёт *агент* (актор, которого сторожит PreToolUse хук), поэтому она никогда не срабатывала; реально сообщавшаяся проблема была в том, что агент создаёт stray-артефакты, главным образом незапрошенные worktree, поэтому guard теперь ключуется по ОПЕРАЦИИ, а не по имени. Отложено: форма `isolation: "worktree"` инструмента Claude `Agent` (нужен захваченный конверт PreToolUse, чтобы подтвердить форму поля). Отброшено: записи вне репозитория (статичный allow-list заливает false-positive'ами легитимные install/temp/global-config/memory записи) и произвольный in-repo мусор (нет надёжного non-name сигнала — это остаётся за governance). Оба читают `tool_input` собственного вызова (не session context), пишут UTF-8 stderr-предупреждение и ВСЕГДА разрешают вызов инструмента — режим AUDIT. При попадании каждый теперь выходит с кодом 1 (никогда 2, что заблокировало бы): согласно hooks reference Claude Code, stderr обычного exit 0 пишется только в debug log и остаётся невидимым в транскрипте, тогда как ненулевой, не-2 exit выводит неблокирующее уведомление `<hook name> hook error` плюс первую строку stderr — изменение, которое делает AUDIT-предупреждение достаточно видимым, чтобы измерить его собственный false-positive rate; чистая проверка по-прежнему выходит с кодом 0. Повышение до блокирующего `deny` (exit 2) остаётся отдельным отревьюенным шагом, когда этот rate будет измерен. Оба fail-open — wrapper-level или внутренняя ошибка схлопывается в exit 0, никогда 1, поэтому сбой хука никогда не может замаскироваться под настоящее попадание. `check-stale-relation-residue.py` — это структурный backstop для architecture law C6 («superseding change оставляет только корректное текущее состояние; stale-relation residue стирается»): он предупреждает, когда `Edit`/`Write` ДОБАВЛЯЕТ фразу stale-relation residue — маркеры фиксированного словаря, которые почти всегда утверждают УСТАРЕВШЕЕ отношение, которое завершённые rename / merge / deprecation / move / fix должны были стереть (`deprecated alias`, `former alias` / `former name`, `now-retired ... kept as a historical example`, скобочные `(was X)` / `(formerly X)` / `(previously X)`, `misregistered as`, `X -> Y alias`, `this is wrong, the correct is Y`) — в файл LIVE-дерева. Он не может выполнить полный change-specific old-name grep из C6 (хук не знает старого имени), поэтому вместо этого ключуется по этим operation-independent residue-фразам. Дискриминатор STALE-vs-LIVE review-bound — реальная зависимость, намеренное разделение или актуальное сравнение `X vs Y` используют часть тех же слов — поэтому это WARN-only; он освобождает цели, где запись superseded-отношения ЯВЛЯЕТСЯ легитимным provenance: реестры decision/closure/task-memory (`work-items/`), changelog'и / release notes (`RELEASE_NOTES`, `CHANGELOG`, `HISTORY`), архивные деревья (`/archive/`, `/legacy/`, `_archive`), локальную scratch-область (`.scratch/`) и git-внутренности (`.git/`). Он читает `tool_input` собственного вызова, пишет UTF-8 stderr-предупреждение, ВСЕГДА разрешает, выходит с кодом 1 при попадании / 0 при чистой проверке (никогда 2) и fail-open — тот же AUDIT-контракт, что и у двух других.

**Аудит Repository-orientation.** `check-repository-orientation.py` предупреждает перед рискованной мутацией репозитория или repository-local run/build/test, когда написанная ассистентом проза после последней подлинной пользовательской задачи не содержит ровно одной валидной записи `REPOSITORY ORIENTATION:`. Он валидирует пять обязательных полей, цитату `path:line`, non-conflict статус и scope ancestry; пропускает discovery-only команды, записи локальных артефактов и конверты субагентов; и выдаёт дополнительное предупреждение для сегментов пути `archive`, `deprecated`, `superseded` или `frozen`, если не указаны соответствующий non-live статус и явный user-approved historical scope. Он никогда не сканирует прозу репозитория и не трактует deprecation-слова как evidence канонического статуса. Он пишет UTF-8 stderr-предупреждение, ВСЕГДА разрешает вызов инструмента и fail-open; при попадании он теперь выходит с кодом 1 (никогда 2, что заблокировало бы), а чистая проверка выходит с кодом 0 — тот же контракт видимости, что и у его четырёх соседних аудитов, поэтому его предупреждение всплывает как неблокирующее уведомление в транскрипте, а не остаётся невидимым в debug log.

**MCP-force binding.** `check-mcp-momentum.py` использует общий классификатор source-navigation и имена настроенных code-intelligence серверов. Claude `mcpMode: auto` и каждый конверт с `agent_id` остаются advisory через `hookSpecificOutput.additionalContext`. Корневой диалог Claude при эффективном `mcpMode: force` запрещает каждый квалифицирующий поиск структурированным `permissionDecision: deny` с `[MCP-FORCE-1]`; предыдущий MCP-вызов не даёт зачёта для последующего поиска. Точный `[approve-mcp-fallback:v1]` в ограниченной host-projected записи с ролью `user` разрешает один recovery-ход. Текст ассистента/инструмента и зарегистрированные injected spans не могут создать маркер, но проекция не является аутентифицированной авторизацией, и поддельная host-shaped user JSONL-запись может ему удовлетворить. Отсутствие серверов и неразрешённый режим допускают действие со стабильной диагностикой. Адаптер fail-open при внутренней ошибке и регистрируется из `agents/scripts/` на `Grep|Bash|PowerShell|shell_command|exec_command`.

**Аудит Typed-routing.** `check-typed-routing.py` (только Claude) предупреждает, когда оркестратор диспатчит встроенный catch-all `subagent_type: general-purpose` для работы, которая выглядит как типизированная специалист-работа, поэтому routing-запах всплывает в единственный момент, когда он наблюдаем — само решение о диспатче. Он срабатывает, только когда всё из: `tool_name` конверта — это subagent-dispatch инструмент; `tool_input.subagent_type` в casefold попадает в член `CATCH_ALL_TYPES` (`general-purpose` изначально — `Explore`/setup-агенты намеренно исключены как легитимные read-only агенты); проза диспатча (prompt/description) несёт сигнал специалист-работы (`implement|fix|build|refactor|.ps1|.py|.ts|toolchain|installer|hook|review|audit|security|perform|design|architecture|migrat`, регистронезависимо, зеркаля сужение mcp-momentum «срабатывать только когда это похоже на целевой класс»); и нет `agent_id` (пропуск контекстов субагентов — вложенный диспатч выполняет собственную политику). При попадании он пишет одну строку stderr `[typed-routing AUDIT]`, указывающую на типизированный реестр (`.claude/agents/*.md` — напр. toolchain-engineer / platform-engineer для `.ps1`/install-работы, engineer-роль для кода, reviewer-роль для review) и выходит с кодом 1 (никогда 2), поэтому подсказка видима, а не только в debug log; чистая проверка выходит с кодом 0. Он ВСЕГДА разрешает вызов инструмента (warn-only не нужен override-маркер — модель продолжает в любом случае) и fail-open при любой внутренней ошибке. Форма dispatch-инструмента была захвачена в Phase-0 из реальных транскриптов сессий: `tool_name == "Agent"` (НЕ `Task`), с `subagent_type` в `tool_input`; он ключуется по этим ИМЕНОВАННЫМ константам и ИНЕРТЕН (exit 0, молчание), если любой из них отсутствует, поэтому будущее переименование делает хук ничего-не-выдающим, а не ложным блоком. Он только для Claude — у Codex CLI нет аналогичного subagent-dispatch инструмента, поэтому Codex-зеркала нет, и счётчик структурных хуков Codex-пака не меняется. Зарегистрирован на matcher dispatch-инструмента `Agent`.
<!-- END ORCHESTRARIUM PAYLOAD: hook-behavior-contracts -->

<!-- BEGIN ORCHESTRARIUM PAYLOAD: hook-entrypoints-placement -->
Точки входа хуков:

- `.claude/agents/scripts/check-{bugfix-discipline,git-push-gate,passive-polling-stop,mcp-momentum}.py`
- `.claude/agents/hooks/check-{machine-local-path,no-trash-in-repo,stale-relation-residue,repository-orientation,typed-routing}.py`

Этот список покрывает девять структурных хуков (четыре blocking и пять warn-only аудитов); четыре reminder/context хука (`mcp-usage-reminder`, `agents-mode-reminder`, `check-scratch-valuables`, `turn-anchor-reminder`) регистрируются через `.claude/agents/scripts/<name>.py`.

Согласно source-hygiene placement law, пять warn-only аудитов живут в `agents/hooks/`; четыре блокирующих и четыре reminder/context хука — в `agents/scripts/` рядом с `hook_common.py`. Python-файлы — единственные зарегистрированные точки входа хуков.
<!-- END ORCHESTRARIUM PAYLOAD: hook-entrypoints-placement -->

<!-- BEGIN ORCHESTRARIUM PAYLOAD: installer-removal-json-path -->
**Инсталлятор по умолчанию авто-устанавливает все тринадцать hook-записей.** И `scripts/install-claude.sh --global`, и `scripts/install-claude.sh --target <project>` мержат записи `PreToolUse` (bugfix-discipline + git-push-gate на matcher `Bash` + machine-local-path + no-trash-in-repo, последний с `Bash`-инклюзивным matcher, чтобы он видел команду `git worktree add`, + stale-relation-residue + repository-orientation на полном edit/shell matcher + mcp-momentum на matcher `Grep|Bash|PowerShell|shell_command|exec_command` + typed-routing на matcher dispatch-инструмента `Agent`), запись `Stop` (passive-polling), три информационные записи `SessionStart` (`mcp-usage-reminder` + `agents-mode-reminder` + `check-scratch-valuables`, все без matcher) и запись `UserPromptSubmit` (`turn-anchor-reminder`, тоже без matcher) в `settings.json` идемпотентным JSON-мержем, который сохраняет другие ключи и хуки. Отказаться на этапе установки можно через `--no-hypothesis-hook` (legacy имя флага сохранено для обратной совместимости) или `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1`. Удалять записи независимо:

По умолчанию регистрация напрямую запускает установленный `.py` через абсолютный `sys.executable` Python-процесса инсталлятора. До изменения регистрации runtime Python проверяет каждый принадлежащий пакету хук: интерпретатор и `.py`-цель должны быть абсолютными обычными файлами; в Windows интерпретатор должен быть `.exe`, не являющимся reparse-точкой, а в POSIX у него должно быть право на выполнение. Последующий health-gate действительно запускает каждый зарегистрированный хук. Зарезервированный native runtime требует настоящий исполняемый native-файл и завершается до изменения регистрации, поскольку пакет не поставляет native-бинарники хуков. Порядок фиксирован: **SYNC → REGISTER → VERIFY**; `scripts/check-hook-health.py` является жёстким VERIFY-гейтом.

```bash
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-git-push-gate --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event Stop --script-marker check-passive-polling-stop --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-machine-local-path --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-no-trash-in-repo --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-stale-relation-residue --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-repository-orientation --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-mcp-momentum --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-typed-routing --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker mcp-usage-reminder --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker agents-mode-reminder --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker check-scratch-valuables --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event UserPromptSubmit --script-marker turn-anchor-reminder --script-path <ignored> --remove
```

На Windows и POSIX авто-устанавливаемые записи используют одну direct-Python exec-форму; различаются только абсолютные пути:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit|apply_patch",
        "hooks": [
          {
            "type": "command",
            "command": "C:\\Python314\\python.exe",
            "args": [
              "C:\\Users\\<you>\\.claude\\agents\\scripts\\check-bugfix-discipline.py"
            ]
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "C:\\Python314\\python.exe",
            "args": [
              "C:\\Users\\<you>\\.claude\\agents\\scripts\\check-passive-polling-stop.py"
            ]
          }
        ]
      }
    ]
  }
}
```

Заметки по разрешению путей:

- И executable, и `.py`-аргумент — абсолютные пути, поэтому запуск не зависит от текущего рабочего каталога.

Matcher `Edit|Write|NotebookEdit|apply_patch` (regex по имени инструмента) покрывает code-mutating инструменты Claude плюс `apply_patch` от Codex. `Stop`, `SessionStart` и `UserPromptSubmit` все игнорируют matcher; инсталлятор опускает его для этих записей.
<!-- END ORCHESTRARIUM PAYLOAD: installer-removal-json-path -->

## Термины и сокращения

- `JSON`: JavaScript Object Notation, структурированный формат, используемый настройками и конвертами хуков.
- `LF`: Line Feed, формат байта перевода строки, сохраняемый в каждом payload.
- `MCP`: Model Context Protocol, runtime-интерфейс, используемый для предоставления подключённых инструментов и ресурсов.
