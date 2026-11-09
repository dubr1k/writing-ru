# Проверка платформ

Проверено 2026-11-09 по официальным страницам и публичным исходникам; это снимок документации, не обещание совместимости со всеми прошлыми и будущими версиями. Проверка discovery отделена от проверки поведения модели.

## Источники и решения

| Платформа | Официальные URLs | Проверенные факты и выбранная поставка |
| --- | --- | --- |
| OpenClaw | https://docs.openclaw.ai/tools/skills ; https://docs.openclaw.ai/tools/exec | Минимум `name` и `description` в YAML frontmatter. Workspace `skills/` имеет приоритет; поддержаны `.agents/skills`, managed и extraDirs. Документация описывает grouped discovery до 6 уровней, но пакет плоский. `{baseDir}` разрешается в путь текущего навыка. Скрипт выполняет `exec`; нужен Python в выбранном execution host. Пакет не plugin и не ClawHub manifest. |
| Codex | https://developers.openai.com/codex/skills (перенаправляет на https://learn.chatgpt.com/docs/build-skills) ; https://raw.githubusercontent.com/openai/codex/main/docs/skills.md | `SKILL.md`, обязательные `name`/`description`, optional scripts/references/assets. Repo discovery `.agents/skills` от cwd до корня repo; user `$HOME/.agents/skills`. Явный вызов через `$name` или `/skills`; сначала каталог, затем полное тело. `agents/openai.yaml` опционален и не требуется нашему bundle. Использовано tool-agnostic чтение/shell без выдуманного имени API. |
| Claude Code | https://code.claude.com/docs/en/skills ; https://code.claude.com/docs/en/sandboxing | Project `.claude/skills/<name>/SKILL.md`, personal `~/.claude/skills`; YAML frontmatter, `name` optional, `description` рекомендован. Read/Bash — штатные механизмы. References нужно читать явно. `/name` вызывает навык. Не используем extensions frontmatter: `allowed-tools`, `model`, `hooks`, dynamic shell. Bash sandbox относится к shell, не ко всем file tools; может ограничить доступ к checker. |
| Pi | https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/skills.md ; https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/cli.md ; https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/README.md ; https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/package.json | Текущий публичный пакет `@earendil-works/pi-coding-agent` **1.5.0**, upstream теперь earendil-works/pi. `name`/`description`, Agent Skills specification, scripts/references; recursive directory discovery, `.pi/skills` и `.agents/skills`. `read` и `bash` штатные, `/skill:name` для явной загрузки; `--skill`, `--no-skills`, `--offline` описаны в CLI. Поставляем каталог, не npm package/manifest. |
| Oh My Pi | https://raw.githubusercontent.com/can1357/oh-my-pi/main/docs/skills.md ; https://raw.githubusercontent.com/can1357/oh-my-pi/main/docs/environment-variables.md ; https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/package.json | Публичный source package **18.18.3**, доступный локальный бинарник **18.18.2**. Conventional roots и customDirectories сканируют только `skills/<name>/SKILL.md`, не `skills/group/name`. Native project `.omp/skills`, user agent directory; `description` обязателен для native provider. Чтение `skill://name` и supporting paths, shell `bash`; `/skill:name`. Не используем registry/plugin manifest. Изоляция agent directory: `PI_CODING_AGENT_DIR`, config root: `PI_CONFIG_DIR`. |

OpenClaw, Codex и Claude Code: страницы rolling/unversioned, конкретный установленный release не проверялся. Номера новых возможностей Claude Code на странице не являются заявленной минимальной версией нашего пакета. Версии Pi/OMP выше — значения публичных package.json на дату проверки, а не закрепление runtime пользователя.

## Общий контракт архива

У всех пакетов `skills/<name>/SKILL.md` (ядро + 18 жанров) непосредственно под `skills`, четыре публичных reference, checker и синтетические tests. Frontmatter адаптаций ограничен `name`, `description`, `license`, `compatibility`. YAML-строки кодируются JSON-кавычками, совместимыми с YAML. Нет runtime manifest, plugin registration, сетевых зависимостей, auto-install, смены модели или автоматического расширения прав.

Metadata Hermes остаётся только в canonical source. Builder заменяет его конкретный вызов самопроверки обычной shell-командой с runtime-пояснением. Ссылки жанров на ядро явные и относительные; каталог не означает транзитивную загрузку. Office/цитатные/почтовые смежные навыки — только опциональные примеры, не зависимости. Приватные навыки Hermes не читались и не копировались.

## Tools и ограничения окружения

Файлы Markdown не создают tools и не дают разрешения на выполнение. Поддержка `scripts/` не означает автоматический запуск. Если чтение или shell недоступны, агент должен сообщить о непроведённой проверке; не делать вид, что checker запускался. Python 3.10+ нужен там, где выполняется команда: контейнер OpenClaw, sandbox Codex/Claude или локальная оболочка Pi/OMP. Ничего не устанавливается автоматически.

В Codex и иных интерфейсах названия tool API могут отличаться: инструкция намеренно описывает действие чтения/shell, а не подставляет вымышленный вызов. Для OpenClaw использован документированный `exec`, для Claude — Read/Bash, для Pi/OMP — read/bash. Не обходим sandbox отказ запуском на другом host. Провайдер получает материалы по правилам вашего runtime; локальный checker сам сеть не использует.

## Статус испытаний

Точные команды и доказательства находятся в [verification.md](verification.md). OpenClaw, Codex, Claude Code и Pi без доступного бинарника — только structural/package-tested, не live-tested. Для OMP выполнена отдельная изолированная проверка discovery и чтения, без provider prompt. Никакого controlled experiment по качеству текста здесь нет.
