#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Редакторские сигналы для русского текста: шаблонные обороты, служебные следы, ритм.

Только стандартная библиотека, Python 3.10+. Вход: .txt, .md, .docx или «-» (stdin).
Выход: отчёт на русском; --json — машинный вывод.
Коды: 0 — анализ выполнен; 1 — сработал выбранный режим отказа (см. ниже); 2 — ошибка чтения
или разбора. Режимы отказа: --fail-on-blocking — код 1 только при непройденной обязательной
проверке (для автоматической приёмки); --strict — код 1 при любом красном сигнале, включая стилевые.
--chat — текст является сообщением в чат (отчёт агента, ответ заказчику): обращение и реплики чата
становятся стилевым сигналом, плейсхолдеры, технические следы и объём остаются обязательными.

Отчёт разделён на две части.
«Обязательно перед сдачей» — блокирующие проверки: служебные реплики агента, технические следы
вставки из чат-интерфейса (маркеры цитирования вроде contentReference[oaicite:1], служебные
параметры ссылок), незаполненные плейсхолдеры, объём вне заданных пределов.
«Стилевые сигналы» — места для перечитывания: ритм, шаблонные обороты, плотность отвлечённых
существительных. Это вопросы к тексту, а не оценка его качества: метрики считают форму, смысл
проверяется чтением.

Слои Markdown. Исходник делится на видимый текст, HTML-комментарии и код. Стилевой анализ идёт
по видимому тексту без кода, адресов ссылок и комментариев. Технические следы ищутся в видимом
тексте вместе с адресами ссылок и в комментариях: скрытый комментарий уходит адресату вместе
с файлом. Служебная реплика в комментарии блокирует сдачу, черновая пометка — жёлтый сигнал.
Маркер внутри кода (блок или `строка`) считается документированным примером: он показан
в разделе «Справочно» и сдачу не блокирует. Комментарии и примечания DOCX не читаются.

Объём проверяется только если заданы --max-chars N, --max-words N или --min-words N.
Правило счёта слов: слово — последовательность знаков между пробелами, в которой есть буква
или цифра. Дефисное слово, число («2024», «3,5»), число с разделителями разрядов («10 000»),
диапазон («2020–2024»), адрес — по одному слову; инициалы «А. С.» — два; отдельно стоящие тире,
«%», «№» и прочие знаки — ноль. В Markdown не считаются код, адреса ссылок, HTML-комментарии
и номера пунктов нумерованного списка; текст ссылки считается. Знаки с пробелами считаются
по исходному тексту как есть, с разметкой; для .docx — по извлечённому тексту абзацев.
Поле whitespace_tokens — все последовательности между пробелами, включая отдельные тире:
ориентир, если получатель считает объём текстовым редактором.

В JSON: mandatory и style (списки пар [severity, сообщение]), flags — их объединение,
red — есть ли красный сигнал в любом разделе, blocking — есть ли непройденная обязательная
проверка, notes — справочные строки, которые ничего не блокируют. У каждой находки поле where:
text, comment или code.

Это эвристики для ручной проверки, а не определение авторства или ИИ-генерации.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

VERSION = "2.4.0"

# ---------------------------------------------------------------- стоп-фразы
# Группы соответствуют references/ru-ai-patterns.md. Шаблоны без учёта регистра.
STOP_GROUPS: dict[str, tuple[str, list[str]]] = {
    "zachin": ("Пустые зачины и вводные", [
        r"\bв современном мире\b", r"\bв наше время\b", r"\bна сегодняшний день\b",
        r"\bв настоящее время\b", r"\bв эпоху\b", r"\bв условиях (стремительн|динамичн|постоянн|современн)",
        r"\bважно отметить\b", r"\bстоит отметить\b", r"\bстоит подчеркнуть\b", r"\bследует отметить\b",
        r"\bнеобходимо понимать\b", r"\bнельзя не отметить\b", r"\bпримечательно, что\b",
        r"\bбезусловно\b", r"\bнесомненно\b", r"\bочевидно, что\b", r"\bкак известно\b",
        r"\bдавайте разбер[её]мся\b", r"\bразбер[её]м подробнее\b", r"\bпредставьте себе\b",
    ]),
    "znachimost": ("Раздувание значимости", [
        r"\bигра(ет|ют|ла|ли) (ключев|важн|решающ|значим|центральн|особ)\w* роль",
        r"\bнеотъемлем\w+ част", r"\bоткрыва\w+ нов\w+ (горизонт|возможност)", r"\bна нов\w+ уровень\b",
        r"\bвс[её] более актуальн", r"\bособ\w+ значимост", r"\bмощн\w+ инструмент", r"\bкраеугольн\w+ кам",
        r"\bне имеет аналогов\b", r"\bреволюционн", r"\bпрорывн", r"\bуникальн", r"\bинновационн",
        r"\bнов\w+ эр[аы]\b", r"\bменяет представлени", r"\bпереосмыслени",
    ]),
    "glagoly": ("Глаголы-пустышки", [
        r"\bподч[её]ркива\w+\b", r"\bдемонстриру\w+\b", r"\bотража\w+\b", r"\bсвидетельству\w+ о\b",
        r"\bспособству\w+\b", r"\bпозволя\w+ (обеспечить|повысить|достичь|реализовать)",
        r"\bраскрыва\w+ потенциал", r"\bзада[её]т вектор", r"\bактуализиру\w+",
    ]),
    "landshaft": ("Слова-ландшафты", [
        r"\bландшафт", r"\bэкосистем", r"\bпарадигм", r"\bтрансформаци", r"\bсинерги", r"\bтраектори",
        r"\bхолистическ", r"\bкомплексн\w+ подход", r"\bдинамично развива", r"\bстремительно меня",
        r"\bцифров\w+ сред[аыеу]\b",
        # «вызовы инструментов/функций/API» — термин, не «вызовы времени».
        r"\bвызов(ы|ов|ам|ами)\b(?!\s+(инструмент|функци|метод|api|модел|сервис|процедур|скрипт|команд|tool))",
        r"\bтренд",
    ]),
    "kancelyarit": ("Канцелярит", [
        # Только указательное «данный» в единственном числе: «данные» обычно существительное.
        # «данным» бывает и существительным («по данным опроса», «доступ к данным»), и
        # прилагательным («данным требованиям», «данным приказом»). Отмечаем только второе:
        # за ним идёт слово в дательном падеже множественного числа или в творительном единственного.
        r"\bданн(ый|ая|ое|ого|ой|ом|ую)\b",
        r"\bданным(?=\s+[а-яё]+(?:ам|ям|ом|ем|ём)\b)",
        r"\bв рамках\b", r"\bв целях\b", r"\bосуществл\w+",
        r"\bимеет место\b", r"\bна предмет\b", r"\bв части\b", r"\bпо вопросу\b",
        r"\bпредставля\w+ собой\b", r"\bвыступа\w+ в качестве\b", r"\bоказыва\w+ (влияние|воздействие)",
        r"\bпроизвод\w+ анализ", r"\bиме\w+ возможность\b", r"\bнос\w+ характер\b",
    ]),
    "simmetriya": ("Симметрии", [
        r"\bне просто\b[^.!?]{1,60}\bа\b", r"\bне только\b[^.!?]{1,80}\bно и\b",
        r"\bс одной стороны\b", r"\bс другой стороны\b",
    ]),
    "psevdoglubina": ("Псевдоглубина", [
        r"\bпо сути\b", r"\bна самом деле\b", r"\bв конечном (сч[её]те|итоге)\b", r"\bглавный вопрос в том\b",
        r"\bключев\w+ вопрос\b", r"\bесли задуматься\b", r"\bесли копнуть\b", r"\bдело в том, что\b",
        r"\bсуть в том, что\b", r"\bздесь важно другое\b", r"\bпарадокс в том\b",
    ]),
    "itog": ("Итоговые формулы", [
        r"\bтаким образом\b", r"\bподводя итог", r"\bв заключение\b", r"\bрезюмируя\b",
        r"\bвремя покажет\b", r"\bбудущее уже здесь\b", r"\bвыбор за вами\b", r"\bдальше\s*[—-]\s*больше\b",
        r"\bэто только начало\b", r"\bоста[её]тся надеяться\b", r"\bпожив[её]м\s*[—-]\s*увидим\b",
    ]),
    "ssylki": ("Размытые ссылки", [
        r"\bэксперты (считают|отмечают|полагают|утверждают)\b", r"\bисследования показывают\b",
        r"\bуч[её]ные доказали\b", r"\bряд (авторов|исследователей|специалистов)\b",
        r"\bмногие (специалисты|эксперты|исследователи)\b", r"\bпо данным аналитиков\b",
        r"\bсогласно статистике\b",
    ]),
    "hedging": ("Хеджирование и сервильность", [
        r"\bв некоторой степени\b", r"\bопредел[её]нным образом\b", r"\bможет потенциально\b",
        r"\bвполне возможно, что\b", r"\bотличный вопрос\b", r"\bвы абсолютно правы\b",
        r"\bи это нормально\b", r"\bне стоит переживать\b", r"\bвы не одиноки\b",
    ]),
    "kalki": ("Кальки с английского", [
        r"\bдела\w+ разниц", r"\bв конце дня\b", r"\bна одной (волне|странице)\b", r"\bглубок\w+ погружени",
        r"\bменяет правила игры\b", r"\bбр\w+ (на себя )?ответственность\b", r"\bмасштабиров\w+ (идею|мысль|подход)",
        r"\bчеллендж", r"\bинсайт", r"\bнарратив", r"\bфокусиру\w+ на\b", r"\bэто о том, что\b",
        r"\bабсолютно\b", r"\bбуквально\b", r"\bнавигиров", r"\bпутешестви[ея] (по|в|к)\b", r"\bистория о том, как\b",
    ]),
    "metafory": ("Штампы-метафоры", [
        r"\bмост между\b", r"\bдвигател\w+ прогресса\b", r"\bпалка о двух концах\b", r"\bлакмусов", r"\bверхушк\w+ айсберга\b",
        r"\bна стыке\b", r"\bволшебн\w+ таблетк", r"\bсеребрян\w+ пул", r"\bдорожн\w+ карт", r"\bточк\w+ роста\b",
        r"\bокно возможностей\b", r"\bзон\w+ турбулентност", r"\bзон\w+ комфорта\b",
    ]),
    "agent_leak": ("Служебные реплики агента в документе", [
        r"(^|[.!?…]\s+|[\"«(]\s*)(босс|шеф)\s*[,!]", r",\s*(босс|шеф)\s*[.!?,]",
        r"\bвот (ваш |готовый |мой |обновл[её]нный |итоговый )?(вариант|текст|черновик|пост|ответ)\s*[:—-]",
        r"\bнадеюсь, это (поможет|будет полезно|было полезно)\b", r"\bкак (ии|языковая модель|ии-ассистент|нейросеть), я\b",
        r"\bесли (хотите|нужно|потребуется|понадобится),? (я )?(могу|сделаю|подготовлю|доработаю)\b",
        r"^\s*готово\s*[!.]", r"^\s*готово[,!]\s+(вот|ниже|держите|я )", r"\bкак (вы )?и просили\b", r"\bя (подготовил|написал|сделал)[аи]? для вас\b",
    ]),
    "placeholder": ("Незаполненные места и черновые пометки", [
        r"\[уточнить", r"\[вставить", r"\[todo", r"\btodo\b", r"\btbd\b", r"\bxxx\b", r"\?\?\?",
        r"<(имя|фамилия|дата|название|ссылка|номер|сумма|должность)>",
        r"\[(имя|фамилия|дата|ссылка|источник|название|номер|сумма)\]", r"\blorem ipsum\b",
    ]),
}

# Технические следы вставки из чат-интерфейса: внутренняя разметка цитирования и служебные
# параметры ссылок, которые интерфейс не превратил в текст. Список — известные маркеры, он
# неполон и устаревает. Находка говорит только о том, что в документе остался мусор и что
# утверждение рядом нужно сверить с источником; автора она не определяет.
TECH_TITLE = "Технические следы вставки из чат-интерфейса"
TECH_LEAK = re.compile("|".join([
    r":?contentReference\[oaicite:\d+\](?:\{index=\d+\})?",
    r"\[?oai_citation(?::\d+)?",
    r"\boaicite\b",
    r"(?<![A-Za-z])(?:cite|i)?turn\d+(?:search|image|news|file|view)\d+",
    r"attributableIndex",
    r"\[cite_start\]",
    r"\[cite:\s*\d+(?:\s*,\s*\d+)*\]",
    r"\[span_\d+\]\((?:start|end)_span\)",
    r"grok_render_citation_card_json",
    r"</?grok[-_]card\b",
    r"【[^】\n]{0,40}†[^】\n]{0,40}】",
    r"\battached_file:\d+",
    r"ppl-ai-file-upload",
    r"[?&]utm_source=(?:chatgpt\.com|openai|copilot\.com)(?![\w.-])",
    r"[?&]referrer=grok\.com(?![\w.-])",
]), re.I)

# Три совпадения из этих групп дают красный сигнал (не вердикт).
PRIORITY_GROUPS = {"zachin", "znachimost", "itog", "ssylki", "hedging"}
# Одно совпадение из этих групп — уже красный сигнал: такое не должно уйти адресату.
IMMEDIATE_RED = {"agent_leak", "placeholder"}

# Жанровые пороги: меняют чувствительность, а не правила языка.
# Калибровка отвлечённых существительных (на 100 слов): живой пост ≈ 4, хороший
# объясняющий текст ≈ 7–8, шаблонный «нейротекст» ≈ 10+, официальные документы — выше.
GENRES: dict[str, dict] = {
    "general":   dict(nominal_red=10.0, copula=0.6, cv_red=0.35, emoji=2, bold_lists_red=True, latin_share=0.15, quiet=set()),
    "academic":  dict(nominal_red=14.0, copula=1.2, cv_red=None, emoji=0, bold_lists_red=True, latin_share=0.25, quiet=set()),
    "official":  dict(nominal_red=16.0, copula=1.5, cv_red=None, emoji=0, bold_lists_red=False, latin_share=0.25, quiet={"kancelyarit"}),
    "business":  dict(nominal_red=10.0, copula=0.9, cv_red=None, emoji=0, bold_lists_red=True, latin_share=0.15, quiet=set()),
    "technical": dict(nominal_red=10.0, copula=0.9, cv_red=None, emoji=2, bold_lists_red=False, latin_share=None, quiet={"kalki"}),
    "post":      dict(nominal_red=8.0, copula=0.5, cv_red=0.35, emoji=3, bold_lists_red=True, latin_share=0.2, quiet=set()),
    "speech":    dict(nominal_red=8.0, copula=0.5, cv_red=0.35, emoji=0, bold_lists_red=True, latin_share=0.15, quiet=set()),
}

# Отвлечённые существительные во всех падежах: -ение/-ания/-тие/-ация… и -ость.
# Имена собственные (с заглавной буквы) не считаются: «Германии», «Компании Х».
NOMINAL_RX = re.compile(
    r"^(\w{3,}?(?:ени|ани|яни|ти|аци|яци))(?:е|я|ю|ем|и|й|ям|ями|ях)$|^(\w{3,}?ост)(?:ь|и|ью|ей|ям|ями|ях)$")
NOMINAL_STOP_STEMS = {"мнени", "знани", "решени", "значени", "отношени", "здани", "задани", "заняти",
                      "событи", "названи", "внимани", "сообщени", "понимани", "участи", "компани",
                      "возможност", "ценност", "сущност", "честност", "скорост", "новост", "радост",
                      "молодост", "старост", "должност", "гост", "трост"}


def is_nominal(word: str) -> bool:
    if not word or word[0].isupper():
        return False
    m = NOMINAL_RX.match(word.lower())
    return bool(m) and (m.group(1) or m.group(2)) not in NOMINAL_STOP_STEMS
COPULA = re.compile(r"\b(является|являются|являлся|являлась|являлись|являться)\b", re.I)
TRIAD = re.compile(r"\b[\w-]+,\s+[\w-]+\s+и\s+[\w-]+\b")
PARA_OPENERS = re.compile(r"^\s*(таким образом|итак|в итоге|в целом|подводя|кроме того|более того|также|помимо этого|вместе с тем|при этом|однако|важно|стоит|следует)\b", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
LATIN_WORD = re.compile(r"\b[A-Za-z]{3,}\b")
BOLD_MD = re.compile(r"\*\*[^*\n]+\*\*")
BOLD_COLON_LIST = re.compile(r"^\s*[-*•]\s*\*\*[^*\n]+:?\*\*\s*:?", re.M)
HEADING_COLON = re.compile(r"^#{1,6}\s+[^\n:]{2,60}:\s+\S", re.M)
STRAIGHT_QUOTES = re.compile(r'"[^"\n]{2,}"')
HYPHEN_AS_DASH = re.compile(r"(?<=[А-Яа-яЁё,])\s-\s(?=[А-Яа-яЁё])")
RHETORIC = re.compile(r"\?\s+(Это значит|Ответ|Потому что|Да,|Нет,|Конечно|Очевидно)", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[«\"A-ZА-ЯЁ0-9])")
WORD = re.compile(r"[А-Яа-яЁёA-Za-z][\w-]*")
# Слово для счёта объёма: всё между пробелами, где есть буква или цифра (см. описание модуля).
COUNT_WORD = re.compile(r"\S*[^\W_]\S*")
DIGIT_GROUPS = re.compile(r"(?<![\d,.])\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?![\d])")
MD_ORDERED_MARKER = re.compile(r"(?m)^(\s*(?:>\s*)*)\d+[.)](?=\s)")

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
URL = re.compile(r"https?://\S+")
MD_LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


# ---------------------------------------------------------------- ввод
def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    p = Path(path)
    if p.suffix.lower() == ".docx":
        return docx_text(p)
    return p.read_text(encoding="utf-8")


def docx_text(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    namespaces = (
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}",
        "{http://purl.oclc.org/ooxml/wordprocessingml/main}",
    )
    ns = next((n for n in namespaces if root.tag == n + "document"), None)
    if ns is None:
        raise ValueError("Неподдерживаемый корневой элемент DOCX document.xml")
    out = []
    for para in root.iter(ns + "p"):
        parts = []
        for node in para.iter():
            if node.tag == ns + "t":
                parts.append(node.text or "")
            elif node.tag == ns + "tab":
                parts.append("\t")
            elif node.tag in (ns + "br", ns + "cr"):
                parts.append("\n")
        out.append("".join(parts))
    return "\n\n".join(out)


def _blank(m: re.Match) -> str:
    """Заменить совпадение пробелами, сохранив переводы строк (номера строк не съезжают)."""
    return re.sub(r"[^\n]", " ", m.group(0))


def _keep(text: str, spans: list[tuple[int, int]]) -> str:
    """Оставить только указанные участки, остальное заменить пробелами (строки не съезжают)."""
    out, pos = [], 0
    for a, b in spans:
        out.append(re.sub(r"[^\n]", " ", text[pos:a]))
        out.append(text[a:b])
        pos = b
    out.append(re.sub(r"[^\n]", " ", text[pos:]))
    return "".join(out)


def _overlay(a: str, b: str) -> str:
    """Склеить два слоя одинаковой длины: непробельный знак берётся из любого."""
    return "".join(y if x in " " else x for x, y in zip(a, b))


def markdown_layers(text: str, skip_quotes: bool = False) -> dict[str, str]:
    """Разделить Markdown на слои одинаковой длины с сохранением номеров строк.

    prose — видимый текст без кода, адресов ссылок и HTML-комментариев (стилевой анализ, объём);
    visible — видимый текст с адресами ссылок, но без кода и комментариев (технические следы);
    comments — только HTML-комментарии; code — только код: блоки и `строки`.
    """
    # Закрывающий fence той же породы, не короче открывающего.
    # Незакрытый блок продолжается до EOF; номера строк сохраняются.
    out, code = [], []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = FENCE.match(line.rstrip("\r\n"))
        blank = re.sub(r"[^\r\n]", " ", line)
        if fence is not None:
            out.append(blank)
            code.append(line)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker and not (marker[1][0] == "`" and "`" in marker[2]):
            fence = marker[1]
            out.append(blank)
            code.append(line)
        else:
            out.append(line)
            code.append(blank)
    text, code_layer = "".join(out), "".join(code)
    comments = _keep(text, [m.span() for m in HTML_COMMENT.finditer(text)])
    comments = re.sub(r"<!--|-->", lambda m: " " * len(m.group(0)), comments)  # для шаблонов с началом строки
    text = HTML_COMMENT.sub(_blank, text)
    code_layer = _overlay(code_layer, _keep(text, [m.span() for m in INLINE_CODE.finditer(text)]))
    text = INLINE_CODE.sub(_blank, text)
    visible = text
    text = MD_LINK_TARGET.sub(lambda m: "](" + " " * len(m.group(1)) + ")", text)
    text = URL.sub(_blank, text)
    if skip_quotes:
        text = re.sub(r"(?m)^\s*>.*$", _blank, text)
        visible = re.sub(r"(?m)^\s*>.*$", _blank, visible)
    return {"prose": text, "visible": visible, "comments": comments, "code": code_layer}


def strip_markdown(text: str, skip_quotes: bool = False) -> str:
    """Видимый текст Markdown без кода, адресов ссылок и HTML-комментариев."""
    return markdown_layers(text, skip_quotes=skip_quotes)["prose"]


def count_words(text: str, markdown: bool = False) -> tuple[int, int]:
    """Вернуть (слова по правилу модуля, все токены между пробелами)."""
    if markdown:
        text = MD_ORDERED_MARKER.sub(lambda m: m.group(1), text)
    joined = DIGIT_GROUPS.sub(lambda m: re.sub(r"[ \u00a0\u202f]", "", m.group(0)), text)
    return len(COUNT_WORD.findall(joined)), len(joined.split())


# ---------------------------------------------------------------- анализ
def split_paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text)]
    return [p for p in paras if p and not p.startswith("---") and not p.startswith("|")]


def split_sentences(para: str) -> list[str]:
    flat = re.sub(r"\s+", " ", para).strip()
    return [s for s in SENT_SPLIT.split(flat) if len(WORD.findall(s)) >= 2]


def cv(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    return statistics.pstdev(values) / mean if mean else 0.0


def fmt_int(n: int) -> str:
    """4812 -> «4 812»."""
    return f"{n:,}".replace(",", " ")


def _context(line: str, m: re.Match) -> str:
    start, end = max(0, m.start() - 35), min(len(line), m.end() + 35)
    return line[start:end].strip()


def analyze(text: str, genre: str = "general", raw_text: str | None = None,
            max_chars: int | None = None, max_words: int | None = None,
            min_words: int | None = None, layers: dict[str, str] | None = None,
            chat: bool = False) -> dict:
    """text — видимый текст для стилевого анализа; layers — слои Markdown (markdown_layers).

    Без layers весь text считается видимым: технические следы в нём блокируют сдачу.
    chat — текст является сообщением в чат, а не документом: обращение и реплики чата не блокируют.
    """
    g = GENRES[genre]
    raw = text if raw_text is None else raw_text
    lines = text.splitlines()
    paras = split_paragraphs(text)
    sentences = [s for p in paras for s in split_sentences(p)]
    words = WORD.findall(text)
    lexical = len(words)
    denom = lexical or 1
    n_words, ws_tokens = count_words(text, markdown=layers is not None)
    sent_lens = [len(WORD.findall(s)) for s in sentences]
    para_lens = [len(WORD.findall(p)) for p in paras]

    findings: list[dict] = []
    for key, (title, patterns) in STOP_GROUPS.items():
        for pat in patterns:
            rx = re.compile(pat, re.I | re.M)
            for i, line in enumerate(lines, 1):
                for m in rx.finditer(line):
                    findings.append({"group": key, "title": title, "line": i,
                                     "match": m.group(0).strip(), "context": _context(line, m),
                                     "quiet": key in g["quiet"], "where": "text"})

    # Исходник: технические следы в видимом тексте (с адресами ссылок), комментариях и коде.
    def scan(layer: str, where: str, rules: list[tuple[str, str, re.Pattern]]) -> None:
        for i, line in enumerate(layer.splitlines(), 1):
            for key, title, rx in rules:
                for m in rx.finditer(line):
                    findings.append({"group": key, "title": title, "line": i,
                                     "match": m.group(0).strip(), "context": _context(line, m),
                                     "quiet": False, "where": where})

    tech = [("tech_leak", TECH_TITLE, TECH_LEAK)]
    scan(layers["visible"] if layers else text, "text", tech)
    if layers:
        hidden = tech + [(key, STOP_GROUPS[key][0], re.compile(pat, re.I | re.M))
                         for key in ("agent_leak", "placeholder") for pat in STOP_GROUPS[key][1]]
        scan(layers["comments"], "comment", hidden)
        scan(layers["code"], "code", tech)

    nominal = [w for w in words if len(w) > 6 and is_nominal(w)]
    copula = COPULA.findall(text)
    triads = TRIAD.findall(text)
    opener_hits = [p[:60] for p in paras if PARA_OPENERS.match(p)]
    bold = BOLD_MD.findall(text)
    bold_lists = BOLD_COLON_LIST.findall(text)
    head_colon = HEADING_COLON.findall(text)
    emoji = EMOJI.findall(text)
    latin = LATIN_WORD.findall(text)
    straight = STRAIGHT_QUOTES.findall(text)
    hyphen_dash = HYPHEN_AS_DASH.findall(text)
    rhetoric = RHETORIC.findall(text)
    dashes = text.count("—")
    mid_share = (sum(1 for n in sent_lens if 12 <= n <= 24) / len(sent_lens)) if sent_lens else 0.0

    metrics = {
        "words": n_words, "lexical_words": lexical, "whitespace_tokens": ws_tokens,
        "sentences": len(sentences), "paragraphs": len(paras),
        "chars_with_spaces": len(raw.strip()), "chars_no_spaces": len(re.sub(r"\s", "", raw)),
        "sentence_len_mean": round(statistics.mean(sent_lens), 1) if sent_lens else 0,
        "sentence_len_cv": round(cv(sent_lens), 2),
        "sentence_mid_share": round(mid_share, 2),
        "paragraph_len_cv": round(cv(para_lens), 2),
        "nominal_per_100": round(100 * len(nominal) / denom, 1),
        "copula_count": len(copula), "copula_per_100": round(100 * len(copula) / denom, 2),
        "triads": len(triads), "triads_per_1000": round(1000 * len(triads) / denom, 1),
        "paragraph_formula_openers": len(opener_hits),
        "em_dash_per_100": round(100 * dashes / denom, 1),
        "hyphen_as_dash": len(hyphen_dash),
        "bold_spans": len(bold), "bold_colon_list_items": len(bold_lists),
        "headings_with_colon": len(head_colon), "emoji": len(emoji),
        "latin_words": len(latin), "latin_share": round(len(latin) / denom, 2),
        "straight_quote_spans": len(straight), "rhetorical_qa": len(rhetoric),
    }

    # Обязательные проверки сдачи: блокируют отправку.
    def where_lines(hits: list[dict]) -> str:
        return ", ".join(str(h["line"]) for h in hits[:8]) + ("…" if len(hits) > 8 else "")

    def kinds(hits: list[dict]) -> str:
        seen = list(dict.fromkeys(h["match"] for h in hits))
        return "; ".join(seen[:4]) + ("; …" if len(seen) > 4 else "")

    mandatory: list[tuple[str, str]] = []
    notes: list[str] = []
    hidden_notes: list[tuple[str, str]] = []
    chat_notes: list[tuple[str, str]] = []
    for key in sorted(IMMEDIATE_RED):
        hits = [f for f in findings if f["group"] == key and f["where"] == "text"]
        if hits and chat and key == "agent_leak":
            chat_notes.append(("yellow", f"Реплики чата: {len(hits)} (стр. {where_lines(hits)}). В сообщении обращение по правилам "
                                         "окружения допустимо; проверь, нет ли лишних предложений услуг и реплик, не нужных читателю."))
        elif hits:
            mandatory.append(("red", f"{STOP_GROUPS[key][0]}: {len(hits)} (стр. {where_lines(hits)}). Убери до отправки."))
        hits = [f for f in findings if f["group"] == key and f["where"] == "comment"]
        if hits and key == "agent_leak":
            mandatory.append(("red", f"Служебные реплики агента в скрытом HTML-комментарии: {len(hits)} (стр. {where_lines(hits)}). "
                                     "Комментарий уйдёт адресату вместе с файлом — убери."))
        elif hits:
            hidden_notes.append(("yellow", f"Черновые пометки в HTML-комментариях: {len(hits)} (стр. {where_lines(hits)}). "
                                           "Проверь, должны ли они уйти адресату вместе с файлом."))
    for where, label in (("text", ""), ("comment", " в скрытом HTML-комментарии")):
        hits = [f for f in findings if f["group"] == "tech_leak" and f["where"] == where]
        if hits:
            mandatory.append(("red", f"{TECH_TITLE}{label}: {len(hits)} (стр. {where_lines(hits)}): {kinds(hits)}. "
                                     "Убери маркер и сверь утверждение рядом с источником."))
    hits = [f for f in findings if f["group"] == "tech_leak" and f["where"] == "code"]
    if hits:
        notes.append(f"Технические маркеры внутри кода или примера: {len(hits)} (стр. {where_lines(hits)}). "
                     "Сдачу не блокируют; убедись, что это намеренный пример.")
    chars = metrics["chars_with_spaces"]
    if max_chars is not None and chars > max_chars:
        mandatory.append(("red", f"Объём: {fmt_int(chars)} знаков с пробелами при лимите {fmt_int(max_chars)} (+{fmt_int(chars - max_chars)})"))
    if max_words is not None and n_words > max_words:
        mandatory.append(("red", f"Объём: {fmt_int(n_words)} слов при лимите {fmt_int(max_words)} (+{fmt_int(n_words - max_words)})"))
    if min_words is not None and n_words < min_words:
        mandatory.append(("red", f"Объём: {fmt_int(n_words)} слов при минимуме {fmt_int(min_words)} (-{fmt_int(min_words - n_words)})"))
    limits = {k: v for k, v in (("max_chars", max_chars), ("max_words", max_words), ("min_words", min_words)) if v is not None}

    # Стилевые сигналы: советы по правке.
    flags: list[tuple[str, str]] = []
    if g["cv_red"] is not None and len(sent_lens) >= 6 and metrics["sentence_len_cv"] < g["cv_red"]:
        flags.append(("red", f"Длина предложений почти одинакова (CV={metrics['sentence_len_cv']}, средняя {metrics['sentence_len_mean']} слов). Перечитай подряд: мешает ли однообразие читать? В перечне, инструкции и определениях ровный ритм — норма."))
    elif g["cv_red"] is None and len(sent_lens) >= 6 and metrics["sentence_len_cv"] < 0.3:
        flags.append(("yellow", f"Ровный ритм (CV={metrics['sentence_len_cv']}); для этого жанра это норма — правь, только если читать трудно."))
    if len(sent_lens) >= 6 and mid_share > 0.8:
        flags.append(("yellow", f"{int(mid_share * 100)} % предложений длиной 12–24 слова. Проверь, не теряется ли главное в одинаковых фразах."))
    if len(para_lens) >= 4 and metrics["paragraph_len_cv"] < 0.3:
        flags.append(("yellow", "Абзацы почти одинаковой длины. Проверь, не собраны ли они по одной схеме."))
    # Плотность на коротком тексте ничего не значит: доли считаются от 40 слов, счётчики — от трёх случаев.
    nr = g["nominal_red"]
    if lexical < 40:
        pass
    elif metrics["nominal_per_100"] > nr:
        flags.append(("red", f"Слова с суффиксами отвлечённых существительных: {metrics['nominal_per_100']} на 100 слов (порог жанра {nr}). Проверь, не спрятаны ли за ними действие и деятель; термины не трогай."))
    elif metrics["nominal_per_100"] > nr - 2:
        flags.append(("yellow", f"Отвлечённые существительные: {metrics['nominal_per_100']} на 100 слов (порог жанра {nr}). Проверь цепочки, где неясно, кто что делает."))
    if len(copula) >= 3 and metrics["copula_per_100"] > g["copula"]:
        flags.append(("yellow", f"«Является»: {len(copula)}. В определении и официальной формуле связка уместна; проверь места, где она только удлиняет фразу."))
    if metrics["triads_per_1000"] > 6 and len(triads) >= 3:
        flags.append(("yellow", f"Тройки «X, Y и Z»: {len(triads)}. Проверь, все ли три элемента нужны по смыслу."))
    if len(opener_hits) >= 3:
        flags.append(("yellow", f"{len(opener_hits)} абзацев начинаются с формульного зачина ({'; '.join(o.split()[0] for o in opener_hits[:4])}…)."))
    if len(bold) > max(3, len(paras) // 2):
        flags.append(("yellow", f"Жирный шрифт: {len(bold)}. Для прозы много; в инструкции и справке проверь, помогает ли он искать нужное."))
    if bold_lists:
        sev = "red" if g["bold_lists_red"] else "yellow"
        flags.append((sev, f"Список с жирными заголовками: {len(bold_lists)} пунктов. Уместно в инструкции, в прозе — признак шаблона."))
    if head_colon:
        flags.append(("yellow", f"Заголовки вида «X: Y»: {len(head_colon)}."))
    if len(emoji) > g["emoji"]:
        flags.append(("yellow", f"Эмодзи: {len(emoji)} (для жанра — не больше {g['emoji']}). Уместны как интонация, не как маркеры."))
    if g["latin_share"] is not None and len(latin) >= 10 and metrics["latin_share"] > g["latin_share"]:
        flags.append(("yellow", f"Много латиницы: {len(latin)} слов ({int(metrics['latin_share'] * 100)} %). Проверь, нет ли русских соответствий."))
    if straight:
        flags.append(("yellow", f"Прямые кавычки \"…\": {len(straight)}. В русском тексте — «ёлочки»."))
    if hyphen_dash:
        flags.append(("yellow", f"Дефис вместо тире между словами: {len(hyphen_dash)}. Нужно «—»."))
    if rhetoric:
        flags.append(("yellow", f"Риторический вопрос с немедленным ответом: {len(rhetoric)}."))
    if dashes >= 3 and metrics["em_dash_per_100"] > 2.5:
        flags.append(("yellow", f"Тире: {dashes} ({metrics['em_dash_per_100']} на 100 слов). Проверь, где тире держит смысл, а где стоит ради «удара»."))
    prio = [f for f in findings if f["group"] in PRIORITY_GROUPS and not f["quiet"]]
    if len(prio) >= 3:
        flags.append(("red", f"Шаблонных оборотов из приоритетных групп: {len(prio)}. Перечитай эти места: есть ли за оборотом мысль или факт."))

    style = flags + hidden_notes + chat_notes
    all_flags = mandatory + style
    return {"version": VERSION, "genre": genre, "chat": chat, "metrics": metrics, "findings": findings,
            "limits": limits, "mandatory": mandatory, "style": style, "flags": all_flags,
            "notes": notes,
            "red": any(s == "red" for s, _ in all_flags), "blocking": bool(mandatory)}


# ---------------------------------------------------------------- вывод
def render(report: dict, path: str) -> str:
    m = report["metrics"]
    mode = ", сообщение в чат" if report.get("chat") else ""
    out = [f"Проверка текста: {path} (жанр: {report['genre']}{mode})",
           f"Слов {m['words']} (токенов между пробелами {m['whitespace_tokens']}), предложений {m['sentences']}, абзацев {m['paragraphs']}; "
           f"знаков с пробелами {m['chars_with_spaces']}, без пробелов {m['chars_no_spaces']}.",
           f"Средняя длина предложения {m['sentence_len_mean']} слов, разброс CV={m['sentence_len_cv']}; "
           f"отвлечённых существительных {m['nominal_per_100']}/100; «является» {m['copula_count']}; троек {m['triads']}; "
           f"тире {m['em_dash_per_100']}/100; жирного {m['bold_spans']}; эмодзи {m['emoji']}; латиницы {m['latin_words']}.",
           ""]
    out.append("Обязательно перед сдачей:")
    if report["mandatory"]:
        for sev, msg in report["mandatory"]:
            out.append(f"  [{'КРАСНЫЙ' if sev == 'red' else 'жёлтый'}] {msg}")
    else:
        lim = report.get("limits", {})
        ok = ("технических следов нет, плейсхолдеров нет" if report.get("chat")
              else "служебных реплик нет, технических следов нет, плейсхолдеров нет")
        parts = []
        if "max_chars" in lim:
            parts.append(f"{fmt_int(m['chars_with_spaces'])} знаков")
        if "max_words" in lim or "min_words" in lim:
            parts.append(f"{fmt_int(m['words'])} слов")
        if parts:
            ok += f", объём {' и '.join(parts)} в пределах лимита"
        out.append(f"  Обязательные проверки пройдены: {ok}.")
    out.append("")
    if report["style"]:
        out.append("Стилевые сигналы: места для перечитывания, не оценка качества.")
        for sev, msg in report["style"]:
            out.append(f"  [{'КРАСНЫЙ' if sev == 'red' else 'жёлтый'}] {msg}")
    else:
        out.append("Стилевые сигналы: нет.")
    out.append("")
    if report.get("notes"):
        out.append("Справочно:")
        out.extend(f"  {n}" for n in report["notes"])
        out.append("")
    if report["findings"]:
        out.append(f"Находки по строкам ({len(report['findings'])}):")
        by_group: dict[str, list[dict]] = {}
        suffix = {"comment": " (в HTML-комментарии)", "code": " (в коде или примере — не блокирует)"}
        for f in report["findings"]:
            title = f["title"] + suffix.get(f.get("where", "text"), "")
            by_group.setdefault(title + (" (для жанра — справочно)" if f["quiet"] else ""), []).append(f)
        for title, items in by_group.items():
            out.append(f"  {title} — {len(items)}")
            for f in items[:12]:
                out.append(f"    стр. {f['line']}: «{f['match']}» … {f['context']}")
            if len(items) > 12:
                out.append(f"    … ещё {len(items) - 12}")
        out.append("")
    else:
        out.append("Шаблонных оборотов не найдено.")
        out.append("")
    out.append("Скрипт не видит: выдуманные факты, источник, который не подтверждает утверждение, пустые обобщения, "
               "потерянные оговорки. Это проверяется чтением и сверкой с источниками. Совпадения и метрики — повод "
               "перечитать, а не оценка качества и не доказательство ИИ-генерации.")
    return "\n".join(out)


def non_negative_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"нужно целое число, получено «{value}»")
    if n < 0:
        raise argparse.ArgumentTypeError("число не может быть отрицательным")
    return n


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Редакторская проверка русского текста; не детектор ИИ. "
                    "Отчёт: «Обязательно перед сдачей» (служебные реплики, технические следы вставки, "
                    "плейсхолдеры, объём) и «Стилевые сигналы» (места для перечитывания).",
        epilog="Счёт слов: слово — последовательность знаков между пробелами, в которой есть буква или цифра; "
               "число с разделителями разрядов — одно слово; отдельные тире и знаки не считаются. "
               "В Markdown не считаются код, адреса ссылок, HTML-комментарии и номера пунктов списка. "
               "Знаки с пробелами — по исходному тексту вместе с разметкой.")
    ap.add_argument("path", help="файл .txt/.md/.docx или «-» для stdin")
    ap.add_argument("--genre", choices=sorted(GENRES), default="general", help="жанровые пороги (по умолчанию general)")
    ap.add_argument("--markdown", action="store_true", help="разбирать как Markdown (для stdin и файлов без .md)")
    ap.add_argument("--keep-code", action="store_true", help="не исключать код, ссылки и HTML-комментарии в Markdown")
    ap.add_argument("--skip-quotes", action="store_true", help="исключить цитаты (строки, начинающиеся с >)")
    ap.add_argument("--json", action="store_true", help="вывод в JSON")
    ap.add_argument("--strict", action="store_true", help="код выхода 1 при любом красном сигнале, включая стилевые")
    ap.add_argument("--fail-on-blocking", action="store_true",
                    help="код выхода 1 только при непройденной обязательной проверке; стилевые сигналы на код не влияют")
    ap.add_argument("--chat", action="store_true",
                    help="текст — сообщение в чат, а не документ: обращение и реплики чата не блокируют сдачу")
    ap.add_argument("--max-chars", type=non_negative_int, metavar="N", help="лимит знаков с пробелами; превышение — обязательная красная проверка")
    ap.add_argument("--max-words", type=non_negative_int, metavar="N", help="лимит слов; превышение — обязательная красная проверка")
    ap.add_argument("--min-words", type=non_negative_int, metavar="N", help="минимум слов; недобор — обязательная красная проверка")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args()
    if args.min_words is not None and args.max_words is not None and args.min_words > args.max_words:
        ap.error("--min-words больше --max-words")
    try:
        raw = read_text(args.path)
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, KeyError, ET.ParseError, ValueError) as e:
        print(f"Ошибка чтения {args.path}: {e}", file=sys.stderr)
        return 2
    text = raw
    layers = None
    is_md = args.markdown or args.path.lower().endswith((".md", ".markdown"))
    if is_md and not args.keep_code:
        layers = markdown_layers(raw, skip_quotes=args.skip_quotes)
        text = layers["prose"]
    elif args.skip_quotes:
        text = re.sub(r"(?m)^\s*>.*$", _blank, raw)
    report = analyze(text, genre=args.genre, raw_text=raw, max_chars=args.max_chars,
                     max_words=args.max_words, min_words=args.min_words, layers=layers, chat=args.chat)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report, args.path))
    if (args.strict and report["red"]) or (args.fail_on_blocking and report["blocking"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
