# Проверки и границы доказательств

## Исходная точка

`python3 -I -m unittest discover -s tests -v`: baseline 26 tests, OK (0.507 s). Snapshot публичных файлов: [baseline.json](../evidence/baseline.json).

## Узкие проверки разработки

- `python3 -I -m unittest discover -s tests -p test_checker.py -v`: новые сценарии дали 3 ожидаемых failures на старом parser; после исправления 27 tests, OK.
- `python3 -I -m unittest discover -s tests -p test_bundle.py -v`: до реализации installer отсутствовал; после реализации 9 tests, OK. Проверены dry-run, apply/verify/remove, existing target, changed/missing/foreign files, receipt, traversal, symlinks и изменённый source. Только временные target внутри репозитория.
- `python3 -I -m unittest discover -s tests -p test_distribution.py -v`: после исправления состава пакетов и изоляции patch 4 tests, OK; затем добавлены извлечение/самопроверка всех пяти пакетов и пересборка из source ZIP без Git.

## Полная проверка

`python3 -I -m unittest discover -s tests -v`: **44 tests, OK** (10.835 s) на момент портативной поставки; после выпуска 2.2.0 — 52 tests, OK. Внутри этой команды каждый из пяти распакованных пакетов проходит собственные тесты checker и installer. Это не пять live runtime испытаний.

Distribution tests сравнивают все файлы двух независимых сборок побайтно, проверяют SHA256SUMS, 19 навыков/пакет, стандартный frontmatter, относительные ссылки и отсутствие Hermes tool calls. Privacy-canaries вне whitelist не экспортируются; symlink whitelisted файла блокирует чтение. Полный patch применяется через `git apply --check` и `git apply` к копии baseline с `GIT_CEILING_DIRECTORIES`, после чего каждый файл сравнивается с source ZIP. Из source ZIP без `.git` режим `--packages-only` пересобирает пять побайтно одинаковых пакетов.

`python3 -I scripts/build.py`: пять ZIP, source, patch, all-in-one и SHA256SUMS созданы в `dist/`. Результаты повторной сборки проверяются тем же distribution test; финальные hashes — в `dist/SHA256SUMS`, не в исходниках (чтобы не создавать самоссылку).

## Runtime scope

OMP **18.18.2**: `omp skill list --json` в изолированном пустом окружении сначала дал 0 skills/0 warnings; после временной установки OMP-пакета в `dist/runtime-probe/workspace/.omp/skills` — ровно **19 native:project skills, 0 warnings**, все пути из этого target. `omp read skill://<name>/SKILL.md:raw` для каждого из 19 навыков и `omp read skill://russian-text-craft/references/<name>:raw` для четырёх references вернули точное содержимое файлов: **23/23**, exit 0. Sanitized evidence: [runtime.json](../evidence/runtime.json).

Процессы запускались через subprocess с отдельными HOME, `PI_CODING_AGENT_DIR`, `PI_CONFIG_DIR`, XDG_CONFIG_HOME и XDG_CACHE_HOME внутри dist; окружение не наследовало credentials. Prompt/model/provider команды не вызывались, MCP не подключался при локальном read. `omp --help`/`skill list --help`/`read --help` использованы только для проверки интерфейса, не как доказательство discovery.

`pi`, `codex`, `claude`, `openclaw` не найдены в PATH; зависимости и runtime не устанавливались. Эти платформы structural/package-tested, не live-tested. Даже live discovery/read не доказывает соблюдение навыка моделью: provider prompt не отправлялся.

## Воспроизведение

```bash
python3 -I -m unittest discover -s tests -v
python3 -I scripts/build.py --output dist/fresh
python3 -I scripts/build.py --output dist/fresh-repro
```

Различающийся существующий artifact не перезаписывается без `--replace`. Тесты пакетов запускают реальные CLI в временных каталогах; новые профили пользователя не создаются. Состав архивов и whitelist проверяются, SHA256SUMS создаётся builder. Версии runtime и официальные URLs: [platforms.md](platforms.md).

## Проверка русской документации

Для README, CHANGELOG, каждого `docs/*.md` и triage reference выполнено:

```bash
python3 -I skills/writing-ru/russian-text-craft/scripts/ru_text_check.py <документ> --genre technical --json
```

Все анализы выполнены с exit 0 (без `--strict`). Triage reference даёт красный из-за двух учебных примеров «Вот вариант:» в одной строке таблицы: оставить, иначе исчезнет пример ложного срабатывания. Упоминания экосистемы/траектории/уникального индекса там — предметные контрпримеры. В README и аудите «вызовы» употреблено о runtime/tools, а не как пустой штамп; оставлено. Жёлтые тройки и жирные пункты в README/плане — перечисления состава и навигация технической инструкции, оставлены. Остальные docs не дали красного. Нулевой отчёт не является критерием приёмки.

Повторное чтение этого отчёта тоже даёт красный на дословном названии учебного примера в предыдущем абзаце; это допустимое ложное срабатывание. Проверены и все пять генерируемых README: четыре без сигналов, у OMP красное на обозначении имени reference в URI-шаблоне. Оно намеренное, рядом объяснена подстановка реального имени; это инструкция, не незаполненное поле публикуемого письма. Находки оставлены по смыслу, а не скрыты ради нуля.

## Что не доказано

Не проверены модельная генерация, фактчекинг, качество стиля и устойчивость к injection в controlled experiment. Нет live Hermes, Windows/macOS sandbox, OpenClaw Gateway, Codex CLI, Claude Code или Pi. Нет push/release/установки в пользовательские профили; commit не выполняется до независимого review координатора.
