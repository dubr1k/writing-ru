# План переносимой поставки writing-ru

Исполнение одним разработчиком в ветке `task/writing-ru-portable`; без commit до независимого review.

## Дизайн

Canonical source остаётся в `skills/writing-ru`: Hermes metadata и его интерфейс сохраняются. Builder на Python 3.10+ stdlib создаёт плоский `skills/<name>/SKILL.md` для каждой из пяти платформ. Только стандартные `name`, `description`, `license`, `compatibility`; без manifest, автоматических разрешений и смены модели. Все пути относительно каталога навыка. Checker один для всех поставок.

Installer принимает явно указанные source/target; по умолчанию печатает план. Apply устанавливает только в отсутствующий target. Удаление требует того же исходного пакета, совпадения receipt, полного списка файлов и SHA256 каждого файла. При любых локальных изменениях — отказ. Обновление: новая папка, проверка, резервная копия старой вне discovery, ручной перенос своих правок. Никаких записей в реальные профили при разработке.

## Порядок и критерии

1. Прочитать 19 навыков, три публичных reference, README, checker, fixtures/tests; зафиксировать baseline hashes/status/diff и исходные 26 tests в `evidence/baseline.json`.
2. Исправить доказуемые противоречия ядра: загрузка ядро+жанр не транзитивна; материал — данные, не команды; факты/цитаты/идентификаторы защищены; режим правки ограничивает самопроверку; красное — triage, а не приказ переписать. Сохранить исключения жанров. Добавить reference с полезными и ошибочными примерами.
3. До кода добавить регрессии для Markdown fences/inline code/строк, тесты installer traversal/symlinks/overwrite/modified/foreign files и архивов privacy/counts/links/repro. Проверить ожидаемое падение новых сценариев. Не запускать provider эксперименты; не заявлять улучшение поведения модели.
4. Проверить официальные docs пяти платформ: frontmatter, directories, resources, tools и sandbox; записать URLs, версии и дату в `docs/platforms.md`.
5. `scripts/build.py`: whitelist исходников, deterministic ZIP metadata/order, пять пакетов с checker/tests/LICENSE/credits/docs, source ZIP, полный baseline patch с новыми файлами, all-in-one и SHA256SUMS. Сборка не читает private/.env/auth/.git content; Git используется только для публичных baseline blobs и diff.
6. `scripts/install.py`: dry-run/apply/verify/remove; только новая папка, запрет traversal и symlinks у source/target/parents, отказ удаления изменённого/постороннего. Тесты только в task-local temporary targets.
7. Full unittest, build twice и сравнение байтов; применить patch к baseline в task-local временной копии и сравнить исходники; package tests, install/verify/remove, проверка ссылок, privacy. Доступный OMP discovery/read без provider calls; Pi только при наличии runtime. Checker всех новых русских docs с `--genre technical`, смысловой разбор находок.
8. Русский аудит и terminal handoff: команды/выходы, hashes, runtime vs structural, статус/diff, пределы проверки. Артефакты в ignored `dist/`; независимо проверяет координатор.

## Ограничения доказательств

Структурные проверки не доказывают соблюдение инструкций моделью. Исследование официальных документов не равно live runtime проверке. Проверка текста эвристическая, не фактчекинг и не определение авторства. Installer рассчитан на доверенный локальный каталог без конкурентной подмены файлов другим процессом; это не sandbox для враждебного пользователя той же ОС.
