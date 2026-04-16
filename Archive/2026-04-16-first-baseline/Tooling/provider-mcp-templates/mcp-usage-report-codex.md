
Честно: да, MCP сильно помогает, но полезность очень неравномерная. И да, serena я использую, но не как основной молоток.

MCP / tool	Насколько помогает мне в этой репе	Где реально полезен	Честный минус
shell_command	10/10	rg, git status, cmake --list-presets, чтение файлов, быстрые проверки	Без него я был бы заметно медленнее
multi_tool_use.parallel	9/10	параллельно читать статус, план, конфиги, grep по нескольким файлам	Надо аккуратно не перегружать контекст
update_plan	8/10	держать живой execution plan и не терять основной поток	Сам по себе не даёт фактов, только дисциплину
sequential-thinking	7/10	перед рискованными изменениями: план, риски, rollback point	Если задача простая, это уже overhead
fetch	8/10	статьи, vendor docs, IEEE/веб-источники, свежая литература	Для локального кода почти бесполезен
context7	6/10	официальные docs библиотек/фреймворков	Для нашей numerics/Fortran задачи используется редко
memory	5/10	долгие многосессионные проекты, сохранить repo-конвенции и resume points	В этой репе source of truth чаще всё же work-items/ и файлы, а не memory
serena	6/10	symbol-aware навигация, overview, точечные безопасные правки	На этом проекте rg + прямое чтение часто быстрее, особенно в больших Fortran-файлах
clangd	7/10	C/C++ symbol references, definition, rename	Для Fortran lane почти не помогает
web	7/10	когда нужен именно интернет-поиск, а не fetch одного URL	Легко утонуть в шуме, если не сужать задачу
По serena совсем честно:

да, я его использую;
но не как главный инструмент в этой репе;
он хорош, когда надо symbol-level понимание по C++/структуре;
для текущего bench_driver.f90 и Fortran-интеграций чаще быстрее и надёжнее идут rg + прямое чтение кусков файла.
Почему так:

репа очень file-heavy и workflow-heavy;
у нас много truth лежит в work-items, reports, plans, benchmark.conf, CMakePresets.json;
Fortran здесь большой и местами удобнее исследуется простым текстовым поиском, чем символическим tooling.
Если совсем коротко, мой текущий реальный стек полезности такой:

Уровень	Инструменты
основной костяк	shell_command, parallel, update_plan
полезные усилители	sequential-thinking, fetch, clangd
ситуативные	serena, memory, context7, web
Так что ответ без прикрас: MCP реально ускоряют и делают работу аккуратнее, но не все одинаково. serena полезен, просто не доминирует здесь над обычным rg-стилем работы.

Возвращаюсь к основной задаче: следующий конкретный шаг у меня уже зафиксирован — впаять resonance_aware_adaptive в shared harness (bench_driver.f90, CMakeLists.txt, benchmark_config.hpp, generate_benchmark_reports.py) и после этого прогнать preset-based build/verification.


12:21 AM
это у тебя не доминирует, но если будешь использовать то как?
12:22 AM



Да. Если буду использовать serena, то не “вместо всего”, а как точечный symbol-aware скальпель.

Когда	Как бы я использовал serena	Зачем
большой кодовый файл	get_symbols_overview по файлу	быстро понять структуру без ручного скролла
нужен конкретный subroutine/function	find_symbol	найти точное тело и границы символа
страшно сломать call sites	find_referencing_symbols	посмотреть, кто реально зависит от символа
нужна аккуратная правка по символу	replace_symbol_body, insert_after_symbol, insert_before_symbol	меньше шанс зацепить соседний код
нужен безопасный rename	rename_symbol	когда rename должен пройти по связанным usage
На текущей задаче с abs-resonance я бы применял его так:

Файл	Что бы я делал через serena
bench_driver.f90	быстро поднял бы overview, потом отдельно нашёл load_benchmark_conf, parse_selector_driver, selector_driver_name, build_selection_driver_order
benchmark_config.hpp	проверил бы точное место массива direct-only selectors и связанные usage
selector_order_source.hpp	если бы новый selector цеплял sidecar/contract path, посмотрел бы references и контракты
А вот где я не стал бы тащить serena:

benchmark.conf
generate_benchmark_reports.py
markdown-отчёты и results-cpp
массовый поиск по строкам/ключам по всей репе
Там чаще быстрее и честнее:

rg для поиска
обычное чтение кусков файла
apply_patch для маленьких line-based правок
То есть мой реальный паттерн такой:

rg сужает область.
serena аккуратно понимает символ и его связи.
Правка идёт уже минимально и безопасно.
Если совсем коротко: serena для меня здесь не “двигатель”, а инструмент точности. На Fortran-гигантах вроде bench_driver.f90 это особенно полезно, когда нужно менять не “строки примерно здесь”, а конкретные подпрограммы без лишнего шума.