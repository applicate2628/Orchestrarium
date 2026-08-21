# Детали структурного enforcement для Claude Markdown

Этот provider-local maintainer reference владеет текущим исчерпывающим контрактом хуков Claude Code; это источник документации, а не installed runtime content.

Всегда загружаемый `src.claude/CLAUDE.md` хранит действующие правила структурного enforcement и ссылается сюда за исчерпывающими деталями хуков и инсталлятора.

`check-git-push-gate-runner.py` — зарегистрированная минимальная точка входа. Она импортирует только фиксированные обычные siblings `hook_common.py` и `check-git-push-gate.py`; последний остаётся единственным policy owner. Любой сбой загрузки или делегирования возвращает постоянный deny без сырых деталей. Обычный warm-cache запуск использует стандартный import cache Python вместо исполнения большого policy source как `__main__`. Поскольку registered command identity меняется, следующая установка Codex требует interactive trust review.

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

**Хук PreToolUse git-push publication-gate.** `check-git-push-gate.py` — это структурный backstop для правила publication-safety «human review до `git push` должен включать leak-check staged-изменений» — прежде существовавшего только как проза, тогда как менее рискованные edit/stop моменты имели блокирующие хуки. Зарегистрированный на matcher `Bash`, каждый live- или transcript-вызов сохраняет фактическое имя инструмента, один раз определяет dialect и строит одну immutable effective-publication-проекцию. Единый declarative registry из семи wrapper-строк и одна argv state machine владеют точными дочерними командами `eval`, `env`, `command`, `exec`, `sudo`, POSIX-shell и PowerShell-host. Assignments, option tokens и attached/detached values, terminators, modes, operands и suffixes сохраняются как типизированные terminal participants; malformed, incomplete, unsupported или unresolved publication-capable участники на любой глубине остаются неавторизующими кандидатами и не могут дать exact-empty graph. Direct child argv не соединяются и не парсятся повторно. Полностью доказанные тела heredoc/here-string являются данными; неопределённые регионы сохраняют консервативные push-кандидаты. В открытом PowerShell-токене без кавычек backtick плюс line feed остаётся содержимым токена, а backtick плюс carriage-return/line-feed является исполняемой границей в обеих поддерживаемых версиях PowerShell. Внутрипроцессный test-only harness даёт только cooperative evidence и не является publication authority. Произвольная same-process мутация делает наблюдение harness недостоверным и может выполнить произвольный caller code; единственный доказанный invariant состоит в том, что неизменённый shipped source не содержит external adapter или launcher, а его cooperative result имеет ноль production/publication consumers. Один lifecycle owner обеспечивает exact typed preparation, one-use run binding, шесть фактических deadline/cancellation phases, canonical bounded capture и reverse-order cleanup; clean close удаляет все member/state/capability/resource records, а cleanup failure сохраняет один bounded retry record до успешного retry и полного purge. Каждый из шести external owners один раз вызывает literal unavailable factory и останавливается на `ORACLE-AUTHORITY-UNAVAILABLE`, adapter/external `0/0`; shipped harness не содержит external adapter, launcher, discovery или fallback. Fast allow получает только ровно одна однозначная самостоятельная публикация с положительным long `--dry-run` и без sibling publication. Далее хук:

- Если конверт несёт `agent_id` (контекст субагента) → exit 0 (разрешить; зеркалит bugfix guard — субагент не может инъектировать user-side override в главный транскрипт. Governance всё равно запрещает делегировать push субагенту, чтобы увернуться от review).
- Если ПОСЛЕДНЕЕ ПОДЛИННОЕ ПОЛЬЗОВАТЕЛЬСКОЕ СООБЩЕНИЕ содержит per-turn override `[approve-publication]` → разрешить. В отличие от `[skip-bugfix-discipline]`, этот маркер учитывается ТОЛЬКО из собственного сообщения пользователя — никогда из прозы ассистента, вызовов инструментов или вывода инструментов — потому что процитированный или инъектированный контент не должен одобрять публикацию.
- Если последнее подлинное пользовательское сообщение содержит явную инструкцию push (`push`, `запушь`, `залей`, ...), текущий turn содержит коррелированный чистый непустой publication-safety скан, А push является одной самостоятельной прямой ambient-командой без prefix/global redirect, только с безопасными output-опциями и ровно одним remote плюс одним refspec → разрешить. Range-receipt дополнительно связывает remote и destination.
- Иначе → выдать структурированный payload `permissionDecision: "deny"` с точными инструкциями по выполнению (сообщить о готовности и попросить пользователя одобрить маркером; или, когда push уже был предписан, сначала запустить safety-скан в этом turn и повторить; или использовать `--dry-run`).

Это BACKSTOP, а не гарантия: точные literal wrapper-child команды, включая multi-argument `eval`, остаются видимыми, а любая последующая direct-, candidate-, child- или nested-publication расходует receipt. Содержимое непрозрачного wrapper-файла, runtime-generated expansion вне typed literal input и aliases/functions, разрешаемые только во время выполнения, не моделируются; произвольный adjacent argument text не считается отдельно исполняемой командой. Generic-receipt не связывает identity репозитория или source/tip refspec. Детектированный non-dry push либо консервативный кандидат без транскрипта запрещается; malformed envelope и точно установленный non-push текст сохраняют fail-open семантику. Связующим правилом остаются human review и leak-check до любого push.

**Хук Stop passive-polling.** `check-passive-polling-stop.py` ловит другой сбой: модель собирается завершить свой turn, сказав, что ждёт асинхронный внешний источник (bot/review/CI/job/notification/reply) без релевантной проверки состояния в текущем turn. Хук читает `last_assistant_message` напрямую из конверта Stop, немедленно выходит, когда `stop_hook_active=true`, и парсит транскрипт только после того, как обнаружена passive-polling фраза. Он разрешает user handoff'ы вроде `waiting for your response` / `жду твоего подтверждения`, разрешает per-stop override-маркер `[acknowledge-passive-stop]`, и в остальных случаях требует релевантный probe в текущем turn: команды времени/статуса (`date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`), вывод процесса/задачи или чтения файлов output/log/task. Если релевантного probe нет, он выдаёт top-level `{"decision":"block","reason":"..."}`, предписывая модели проверить состояние сейчас, использовать override для настоящего handoff или вызвать конкретный инструмент вроде `Bash: gh pr view`.



**Пять PreToolUse аудит-хуков (warn-only).** `check-machine-local-path.py` предупреждает, когда machine-local абсолютный путь (конкретный домашний каталог пользователя или dev-корень рабочей станции; плейсхолдеры вроде `<you>`, `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}` разрешены) записывается в файл не под `.scratch/`. `check-no-trash-in-repo.py` — guard от stray-артефактов; имя файла и install-маркер сохранены ради install continuity, а переименование в `check-stray-artifact` остаётся отдельным follow-up. Его четыре триггера перечислены ниже. Оба хука читают `tool_input` собственного вызова, всегда разрешают вызов и передают предупреждение модели через `hookSpecificOutput.additionalContext` в stdout с кодом 0; чистая проверка также выходит с кодом 0, а внутренняя ошибка fail-open и ничего не выводит. `check-stale-relation-residue.py` служит структурным backstop для architecture law C6: он предупреждает, когда `Edit`/`Write` добавляет в LIVE-дерево маркер устаревшего отношения (`deprecated alias`, `former alias` / `former name`, `(was X)` / `(formerly X)` / `(previously X)`, `misregistered as`, `X -> Y alias`, `this is wrong, the correct is Y`). Поскольку различение STALE и LIVE требует review, хук остаётся warn-only и исключает provenance-поверхности: `work-items/`, changelog/release notes, архивные деревья, `.scratch/` и `.git/`. Он использует тот же stdout/`hookSpecificOutput.additionalContext` канал, всегда разрешает, возвращает 0 при срабатывании и чистом результате и fail-open при внутренней ошибке. Повышение любого из этих аудитов до блокирующего `deny` с кодом 2 требует отдельного review.

Guard no-trash использует четыре замкнутых триггера, выводимых из текста команды: (1) описанный выше незапрошенный `git worktree add`; (2) повреждённую Windows-цель перенаправления вроде `> r:Tempxbuild.log`, где после префикса с буквой диска нет разделителя пути; (3) перенаправление build/log-артефакта в голое имя вроде `> build.log` или `> probe.obj`; (4) компиляцию через `ifx`/`ifort`/`icx`/`gfortran`/`cl`/`gcc`, когда есть исходный файл, но нет флага, направляющего выходной файл. Триггеры (3) и (4) применяются только тогда, когда `cwd/.git` подтверждает, что рабочий каталог процесса является корнем репозитория, а команда не содержит `cd`, `pushd` или `popd`; явная смена каталога делает место назначения неопределимым и потому не вызывает предупреждение. Цели перенаправления классифицируются по исходному тексту команды, чтобы POSIX-токенизация не стирала обратные слеши Windows. Эти дополнения не возвращают отклонённые открытые проверки произвольных записей вне репозитория или произвольного мусора.

Все warn-only audit-хуки передают предупреждение модели через `hookSpecificOutput.additionalContext` в stdout и возвращают код 0 как при срабатывании, так и при чистом результате; код 2 зарезервирован только для отдельно одобренного блокирования. Внутренняя ошибка остаётся fail-open и ничего не выводит.

**Аудит Repository-orientation.** `check-repository-orientation.py` предупреждает перед рискованной мутацией репозитория или repository-local run/build/test, когда написанная ассистентом проза после последней подлинной пользовательской задачи не содержит ровно одной валидной записи `REPOSITORY ORIENTATION:`. Он валидирует пять обязательных полей, цитату `path:line`, non-conflict статус и scope ancestry; пропускает discovery-only команды, записи локальных артефактов и конверты субагентов; и выдаёт дополнительное предупреждение для сегментов пути `archive`, `deprecated`, `superseded` или `frozen`, если не указаны соответствующий non-live статус и явный user-approved historical scope. Он никогда не сканирует прозу репозитория и не трактует deprecation-слова как evidence канонического статуса. Он пишет UTF-8 stderr-предупреждение, ВСЕГДА разрешает вызов инструмента и fail-open; при попадании он теперь выходит с кодом 1 (никогда 2, что заблокировало бы), а чистая проверка выходит с кодом 0 — тот же контракт видимости, что и у его четырёх соседних аудитов, поэтому его предупреждение всплывает как неблокирующее уведомление в транскрипте, а не остаётся невидимым в debug log.

**MCP-force binding.** `check-mcp-momentum.py` использует общий классификатор source-navigation и имена настроенных code-intelligence серверов. Claude `mcpMode: auto` и каждый конверт с `agent_id` остаются advisory через `hookSpecificOutput.additionalContext`. Корневой диалог Claude при эффективном `mcpMode: force` запрещает каждый квалифицирующий поиск структурированным `permissionDecision: deny` с `[MCP-FORCE-1]`; предыдущий MCP-вызов не даёт зачёта для последующего поиска. Точный `[approve-mcp-fallback:v1]` в ограниченной host-projected записи с ролью `user` разрешает один recovery-ход. Текст ассистента/инструмента и зарегистрированные injected spans не могут создать маркер, но проекция не является аутентифицированной авторизацией, и поддельная host-shaped user JSONL-запись может ему удовлетворить. Отсутствие серверов и неразрешённый режим допускают действие со стабильной диагностикой. Адаптер fail-open при внутренней ошибке и регистрируется из `agents/scripts/` на `Grep|Bash|PowerShell|shell_command|exec_command`.

**Аудит Typed-routing.** `check-typed-routing.py` (только Claude) предупреждает, когда оркестратор диспатчит встроенный catch-all `subagent_type: general-purpose` для работы, которая выглядит как типизированная специалист-работа, поэтому routing-запах всплывает в единственный момент, когда он наблюдаем — само решение о диспатче. Он срабатывает, только когда всё из: `tool_name` конверта — это subagent-dispatch инструмент; `tool_input.subagent_type` в casefold попадает в член `CATCH_ALL_TYPES` (`general-purpose` изначально — `Explore`/setup-агенты намеренно исключены как легитимные read-only агенты); проза диспатча (prompt/description) несёт сигнал специалист-работы (`implement|fix|build|refactor|.ps1|.py|.ts|toolchain|installer|hook|review|audit|security|perform|design|architecture|migrat`, регистронезависимо, зеркаля сужение mcp-momentum «срабатывать только когда это похоже на целевой класс»); и нет `agent_id` (пропуск контекстов субагентов — вложенный диспатч выполняет собственную политику). При попадании он пишет одну строку stderr `[typed-routing AUDIT]`, указывающую на типизированный реестр (`.claude/agents/*.md` — напр. toolchain-engineer / platform-engineer для `.ps1`/install-работы, engineer-роль для кода, reviewer-роль для review) и выходит с кодом 1 (никогда 2), поэтому подсказка видима, а не только в debug log; чистая проверка выходит с кодом 0. Он ВСЕГДА разрешает вызов инструмента (warn-only не нужен override-маркер — модель продолжает в любом случае) и fail-open при любой внутренней ошибке. Форма dispatch-инструмента была захвачена в Phase-0 из реальных транскриптов сессий: `tool_name == "Agent"` (НЕ `Task`), с `subagent_type` в `tool_input`; он ключуется по этим ИМЕНОВАННЫМ константам и ИНЕРТЕН (exit 0, молчание), если любой из них отсутствует, поэтому будущее переименование делает хук ничего-не-выдающим, а не ложным блоком. Он только для Claude — у Codex CLI нет аналогичного subagent-dispatch инструмента, поэтому Codex-зеркала нет, и счётчик структурных хуков Codex-пака не меняется. Зарегистрирован на matcher dispatch-инструмента `Agent`.
<!-- END ORCHESTRARIUM PAYLOAD: hook-behavior-contracts -->

<!-- BEGIN ORCHESTRARIUM PAYLOAD: hook-entrypoints-placement -->
Точки входа хуков:

- `.claude/agents/scripts/check-{bugfix-discipline,passive-polling-stop,mcp-momentum}.py`
- `.claude/agents/scripts/check-git-push-gate-runner.py` (зарегистрированная точка входа) и её фиксированные siblings `hook_common.py` и policy `check-git-push-gate.py`
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
