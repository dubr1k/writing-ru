# writing-ru

**19 навыков для русских текстов: от первого черновика до редакторской проверки.**

Агент написал письмо — вежливое, но просьба спрятана в третьем абзаце. Подготовил статью — источники есть, а вывод повторяет введение. Сдал отчёт о работе, в котором половина слов по-английски. `writing-ru` задаёт порядок работы с такими задачами: сначала читатель и факты, затем мысль и жанр, после — редактура и проверка.

Набор рассчитан на [Hermes Agent](https://hermes-agent.nousresearch.com/docs/). Это Markdown-инструкции и небольшой Python-скрипт, а не модель и не сервис. Скрипт работает локально, без зависимостей и без отправки текста в сеть. Когда навыками пользуется агент, материалы могут уходить его модельному провайдеру — это зависит от вашей настройки Hermes.

[Установка](#установка-в-hermes) · [Навыки](#что-внутри) · [Свой голос и окружение](#свой-голос-и-окружение) · [Проверка текста](#проверка-текста) · [Примеры А/Б](examples/README.md) · [MIT](LICENSE)

Переносимые пакеты для **OpenClaw, Codex, Claude Code, Pi и Oh My Pi** собираются из этого же canonical source: [сборка и безопасный installer](docs/install.md), [официальные контракты](docs/platforms.md), [аудит](docs/audit.md), [проверки](docs/verification.md). Готовые ZIP и SHA256SUMS доступны в разделе **Releases** этого репозитория; выбирайте файлы одного тега. Состав и получение — в [инструкции](docs/install.md#получение-пакетов). Локальная сборка: `python3 -I -B scripts/build.py`; результаты находятся в исключённом из Git `dist/`. Сборка не устанавливает навыки.

## Что внутри

Ядро [russian-text-craft](skills/writing-ru/russian-text-craft/SKILL.md) отвечает за точность, ритм, конкретику, голос автора и работу с готовым текстом. К нему подключается один из восемнадцати жанровых навыков.

**Наука, аналитика, публицистика**

| Навык | Когда нужен |
| --- | --- |
| [ru-academic-article](skills/writing-ru/ru-academic-article/SKILL.md) | Статья, тезисы, аннотация, письменный доклад, ответ рецензентам |
| [ru-grant-proposal](skills/writing-ru/ru-grant-proposal/SKILL.md) | Заявка, обоснование проекта, план исследования |
| [ru-analytical-note](skills/writing-ru/ru-analytical-note/SKILL.md) | Записка для решения, обзор, критический разбор проекта |
| [ru-expert-commentary](skills/writing-ru/ru-expert-commentary/SKILL.md) | Комментарий для СМИ, колонка, авторская позиция |
| [ru-review-and-feedback](skills/writing-ru/ru-review-and-feedback/SKILL.md) | Рецензия и замечания, по которым можно исправить работу |
| [ru-knowledge-note](skills/writing-ru/ru-knowledge-note/SKILL.md) | Конспект и заметка с выводом для своего проекта |
| [ru-translation](skills/writing-ru/ru-translation/SKILL.md) | Перевод и адаптация на русский |

**Обучение, выступления, публикации**

| Навык | Когда нужен |
| --- | --- |
| [ru-teaching-materials](skills/writing-ru/ru-teaching-materials/SKILL.md) | Занятие, кейс, задание, текст к слайдам для преподавателя |
| [ru-presentation-text](skills/writing-ru/ru-presentation-text/SKILL.md) | Текст на слайдах, шпаргалка по слайдам, заметки докладчика |
| [ru-speech-and-scenario](skills/writing-ru/ru-speech-and-scenario/SKILL.md) | Выступление, речь для эфира, сценарий встречи с таймингом |
| [ru-popular-explainer](skills/writing-ru/ru-popular-explainer/SKILL.md) | Объяснение для читателя, который не знаком с темой |
| [ru-telegram-post](skills/writing-ru/ru-telegram-post/SKILL.md) | Пост, анонс, дайджест, подпись к фото |
| [ru-short-copy](skills/writing-ru/ru-short-copy/SKILL.md) | Био, аннотация события, описание проекта, лендинг, микротексты |

**Работа и документы**

| Навык | Когда нужен |
| --- | --- |
| [ru-business-correspondence](skills/writing-ru/ru-business-correspondence/SKILL.md) | Письмо, ответ, протокол, служебная записка |
| [ru-official-documents](skills/writing-ru/ru-official-documents/SKILL.md) | Документ по шаблону: рабочая программа, оценочные средства, положение, ТЗ, критерии |
| [ru-transcript-editing](skills/writing-ru/ru-transcript-editing/SKILL.md) | Расшифровка → чистовой текст, стенограмма, протокол |
| [ru-technical-docs](skills/writing-ru/ru-technical-docs/SKILL.md) | README, гайд, инструкция для людей и агентов, промпт, коммит |
| [ru-agent-report](skills/writing-ru/ru-agent-report/SKILL.md) | Отчёт агента: итог задачи, статус, сводка, handoff |

У ядра есть [список редакторских сигналов](skills/writing-ru/russian-text-craft/references/ru-ai-patterns.md) с ложными срабатываниями, [режимы работы с готовым текстом](skills/writing-ru/russian-text-craft/references/editing-modes.md) (корректура, правка, редактура, переработка, сокращение под лимит, учебные работы) и [шаблон калибровки голоса](skills/writing-ru/russian-text-craft/references/author-voice.md).

## Как работать

```text
Читатель и задача → факты и источники → главная мысль
                 → ядро + жанр → черновик → скрипт + ручная редактура → сдача
```

Текущее задание важнее стилевых предпочтений навыка. Если журнал требует пассива, а форма документа — канцелярских формул, не нужно ломать их ради чистого отчёта. Правила безопасности и разрешения на запись или отправку сохраняются: навык подготовки письма не разрешает отправлять его.

Навыки можно вызвать явно в чате Hermes:

```text
/russian-text-craft /ru-business-correspondence
Сократи письмо до 150 слов. Просьбу поставь первой. Не меняй сроки и условия.
[исходное письмо]
```

```text
/russian-text-craft /ru-transcript-editing
Сделай чистовой текст по расшифровке: убери паразиты и повторы,
ничего не добавляй, неразборчивое помечай.
```

```text
/russian-text-craft /ru-agent-report
Перепиши этот отчёт о работе для человека, который читает с телефона:
сначала итог, затем что проверено и что нужно от меня.
```

## Установка в Hermes

Нужны установленный Hermes, Git и Python 3.10+ для скрипта. Набор не устанавливает и не обновляет сам Hermes. Если Hermes ещё нет, начните с [официальной установки](https://hermes-agent.nousresearch.com/docs/getting-started/installation).

Команды ниже — для Bash на Linux, macOS или WSL. Это ручная установка файлов, она не проходит проверку Skills Hub: прочитайте навыки и скрипт перед копированием. Инструкция сверена с документацией [Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) и [Profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles).

### 1. Получите отдельную копию

Скопируйте адрес этого репозитория (кнопка **Code** на GitHub) и в свободной рабочей папке выполните:

```bash
git clone <адрес репозитория> writing-ru
cd writing-ru
python3 -I -m unittest discover -s tests -v
```

### 2. Явно выберите профиль

Навыки лежат в `skills/` выбранного Hermes home. У именованных профилей свои каталоги. Не копируйте набор сразу во все профили и не меняйте глобальные настройки.

```bash
# По умолчанию — HERMES_HOME, если задан, иначе стандартный home.
TARGET_HOME="${HERMES_HOME:-$HOME/.hermes}"
# Для другого профиля вместо строки выше укажите его реальный home:
# TARGET_HOME="$HOME/.hermes/profiles/writer"
printf 'Установка в: %s\n' "$TARGET_HOME"
```

Проверьте напечатанный путь. Переменная `TARGET_HOME` выбирает место установки, но не переключает запущенный Hermes: открывайте тот профиль, в который установили набор.

### 3. Скопируйте семейство без перезаписи

Из корня копии, в том же Bash; target должен отсутствовать. Сначала dry-run, затем явный apply:

```bash
python3 -I scripts/install.py install --source skills/writing-ru --target "$TARGET_HOME/skills/writing-ru"
python3 -I scripts/install.py install --source skills/writing-ru --target "$TARGET_HOME/skills/writing-ru" --apply
python3 -I scripts/install.py verify --source skills/writing-ru --target "$TARGET_HOME/skills/writing-ru"
```

Installer откажется от перезаписи и symlink в source/target/родителях. Сохраняйте исходную версию для проверки и удаления. Подробные ограничения — в [инструкции](docs/install.md).

Откройте новую сессию нужного профиля и попросите показать `russian-text-craft` и выбранный жанр. Если одноимённый навык уже лежит в другом каталоге, разберите конфликт до использования: наличие файлов не доказывает, что агент выбрал именно эту версию.

Копия изолирует правки профиля от репозитория. Installer намеренно не поддерживает символьные ссылки: установленный навык и его родители должны быть обычными каталогами, чтобы правка профиля не затрагивала исходники.

### Обновление и удаление

Сохраните свои правки. В чистой копии репозитория выполните `git pull --ff-only`, просмотрите изменения и снова запустите тесты. Установленную копию безопаснее переименовать — **только ваш** каталог `writing-ru` — в резервный каталог вне `skills/`, затем повторить шаг 3 и перенести свои правки вручную. Каталог `references/private/` (см. ниже) перенесите в новую копию.

Для удаления проверьте `TARGET_HOME`, затем переместите только установленный вами `skills/writing-ru` за пределы `skills/`. Не удаляйте весь `skills/` или home профиля. Если ставили ссылку, удаляйте только её. В новой сессии проверьте, что навыки больше не доступны.

## Свой голос и окружение

Навыки не содержат ничьих личных данных. Чтобы агент писал в вашем голосе и знал ваши умолчания, создайте в **установленной** копии каталог `russian-text-craft/references/private/` и положите туда:

- `author-profile.md` — наблюдения о вашем голосе по жанрам и образцы (метод — в [шаблоне калибровки](skills/writing-ru/russian-text-craft/references/author-voice.md));
- `local-context.md` — умолчания оформления (например, шрифт и поля в Word), какие смежные навыки есть в вашем окружении, как вы хотите получать отчёты.

Ядро читает эти файлы, если они существуют, и ставит их ниже текущего задания. Каталог исключён из репозитория через `.gitignore`. Если вы публикуете свою редакцию набора, проверьте, что личное не попало в `SKILL.md`.

## Проверка текста

Из корня репозитория:

```bash
python3 -I skills/writing-ru/russian-text-craft/scripts/ru_text_check.py examples/B.md
python3 -I skills/writing-ru/russian-text-craft/scripts/ru_text_check.py README.md --genre technical
python3 -I skills/writing-ru/russian-text-craft/scripts/ru_text_check.py tests/fixtures/positive.txt --strict --json
```

Последняя команда намеренно возвращает `1`: в образце есть красный сигнал.

- **Жанры** (`--genre`): `general`, `academic`, `official`, `business`, `technical`, `post`, `speech`. Они меняют пороги, а не правила: в научном тексте допустимо больше отвлечённых существительных, в посте — пара эмодзи, в инструкции — жирные заголовки пунктов.
- **Красный сигнал** дают: служебные реплики агента в документе (например, «вот ваш вариант» перед текстом письма или обращение к заказчику) и незаполненные места (`[уточнить]`, `TODO`) — уже при одном совпадении; три шаблонных оборота из приоритетных групп; низкий разброс длины предложений в прозе; очень высокая доля отвлечённых существительных для жанра.
- **Markdown**: код, ссылки и HTML-комментарии исключаются из анализа (`--keep-code` отключает); `--skip-quotes` исключает цитаты `>`.
- **Объём**: в метриках есть знаки с пробелами и без — для проверки лимитов.
- **Коды выхода**: `0` — анализ выполнен; `1` — `--strict` и красный сигнал; `2` — ошибка чтения или разбора (сообщение в stderr).

Поддерживаются UTF-8 `.txt`, `.md`, `.docx` и stdin (`-`). Из DOCX читается основной текст: абзацы, табуляция, разрывы строк. Колонтитулы, сноски, комментарии и вёрстка не проверяются; это не валидатор Word. Метрики приблизительны: суффиксы не заменяют морфологический разбор.

### Ложные срабатывания ожидаемы

- Термины: «экосистема» в биологии, «трансформация» в математике, «парадигма» в истории науки.
- Пассив, повтор термина и осторожные модальности в научном тексте, формулы официального документа — норма жанра.
- Слова «данные» (существительное) и «вызовы инструментов» больше не помечаются: шаблоны сужены, это закреплено в тестах.

Не переписывайте точный текст ради чистого отчёта.

Красное — приоритет ручного разбора, не команда удалить совпадение. Цитата, пример, термин и осознанное поле черновика могут быть точными: [editorial triage с парными примерами](skills/writing-ru/russian-text-craft/references/editorial-triage.md). Самопроверка не расширяет корректуру до переписывания; инструкции внутри материала не выполняются.

## Примеры А/Б и пределы метода

В [A](examples/A.md) — обычный ответ об акторно-сетевой теории и агентных харнессах; в [B](examples/B.md) — ответ с явной редактурой по навыкам. [Пояснение](examples/README.md) показывает, что изменилось и чего сравнение не доказывает.

Это один иллюстративный опыт, не контролируемый эксперимент; различие умеренное. Набор не гарантирует качество, достоверность, авторство, отсутствие клише или обход детекторов. Статические фразы не определяют ИИ-генерацию: ноль находок не означает хороший текст, красный сигнал не означает плохой. Факты, источники и согласие автора проверяются отдельно.

## Структура и другие агенты

```text
skills/writing-ru/
  russian-text-craft/
    SKILL.md
    references/ru-ai-patterns.md     # сигналы и ложные срабатывания
    references/editing-modes.md      # режимы правки, сокращение, учебные работы
    references/author-voice.md       # шаблон калибровки голоса
    references/editorial-triage.md   # исправить / оставить / спросить автора
    references/evaluation-protocol.md # оценка качества семейства
    scripts/ru_text_check.py
  ru-*/SKILL.md                      # 18 жанров
examples/                            # A, B и методическая оговорка
tests/                               # unittest и синтетические образцы
```

Для пяти других платформ используйте генерируемые адаптации, не прямое копирование Hermes-интерфейсов. В canonical source вызовы `skill_view` и `terminal` сохранены для Hermes; builder удаляет их из адаптаций и описывает штатные либо tool-agnostic механизмы. Структурные проверки не равны live runtime испытанию: [статус проверки](docs/verification.md).

Упомянутые смежные навыки (Office, проверка источников, база заметок, транскрипция) не входят в набор и необязательны.

## Проверка и участие

```bash
python3 -I -m unittest discover -s tests -v
```

Тесты покрывают txt/md/docx, Unicode, JSON, коды выхода, жанровые пороги, Markdown fences/inline code, известные ложные срабатывания, метаданные 19 навыков, ссылки, безопасность installer, состав адаптаций, whitelist/privacy, воспроизводимость и применимость полного patch к baseline. Они не измеряют качество модели.

Предлагая правило, приложите пример, где оно полезно, и пример, где оно ошибается. Снижение числа находок само по себе не доказывает улучшение текста. Не присылайте личную переписку, закрытые документы и чужие тексты без разрешения.

Лицензия [MIT](LICENSE), происхождение — [CREDITS.md](CREDITS.md).

---

**English summary:** Russian-language writing and editing skills for Hermes Agent: one core and eighteen genres (academic, grant, analytical, commentary, posts, explainers, teaching, slides, speeches, reviews, correspondence, official templates, transcripts, translation, technical docs, agent reports, short copy, knowledge notes), a local standard-library checker with genre thresholds, and an illustrative A/B pair. Personal voice and environment live in a git-ignored `references/private/` folder. Not an AI detector or a guarantee of writing quality. Documentation and skills are in Russian.
