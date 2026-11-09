#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Редакторские сигналы для русского текста: шаблонные обороты, служебные следы, ритм.

Только стандартная библиотека, Python 3.10+. Вход: .txt, .md, .docx или «-» (stdin).
Выход: отчёт на русском; --json — машинный вывод; --strict — код 1 при красном сигнале.
Коды: 0 — анализ выполнен; 1 — --strict и есть красный сигнал; 2 — ошибка чтения или разбора.

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

VERSION = "2.0.0"

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
        r"\bданн(ый|ая|ое|ого|ой|ом|ым|ую)\b", r"\bв рамках\b", r"\bв целях\b", r"\bосуществл\w+",
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

FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]+`")
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


def strip_markdown(text: str, skip_quotes: bool = False) -> str:
    text = FENCE.sub(_blank, text)
    text = HTML_COMMENT.sub(_blank, text)
    text = INLINE_CODE.sub(_blank, text)
    text = MD_LINK_TARGET.sub(lambda m: "](" + " " * len(m.group(1)) + ")", text)
    text = URL.sub(_blank, text)
    if skip_quotes:
        text = re.sub(r"(?m)^\s*>.*$", _blank, text)
    return text


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


def analyze(text: str, genre: str = "general", raw_text: str | None = None) -> dict:
    g = GENRES[genre]
    raw = text if raw_text is None else raw_text
    lines = text.splitlines()
    paras = split_paragraphs(text)
    sentences = [s for p in paras for s in split_sentences(p)]
    words = WORD.findall(text)
    n_words = len(words)
    denom = n_words or 1
    sent_lens = [len(WORD.findall(s)) for s in sentences]
    para_lens = [len(WORD.findall(p)) for p in paras]

    findings: list[dict] = []
    for key, (title, patterns) in STOP_GROUPS.items():
        for pat in patterns:
            rx = re.compile(pat, re.I | re.M)
            for i, line in enumerate(lines, 1):
                for m in rx.finditer(line):
                    start, end = max(0, m.start() - 35), min(len(line), m.end() + 35)
                    findings.append({"group": key, "title": title, "line": i,
                                     "match": m.group(0).strip(), "context": line[start:end].strip(),
                                     "quiet": key in g["quiet"]})

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
        "words": n_words, "sentences": len(sentences), "paragraphs": len(paras),
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

    flags: list[tuple[str, str]] = []
    for key in sorted(IMMEDIATE_RED):
        hits = [f for f in findings if f["group"] == key]
        if hits:
            flags.append(("red", f"{STOP_GROUPS[key][0]}: {len(hits)} (стр. {', '.join(str(h['line']) for h in hits[:8])}). Убери до отправки."))
    if g["cv_red"] is not None and len(sent_lens) >= 6 and metrics["sentence_len_cv"] < g["cv_red"]:
        flags.append(("red", f"Монотонный ритм: разброс длины предложений низкий (CV={metrics['sentence_len_cv']}, средняя {metrics['sentence_len_mean']} слов). Добавь короткие и длинные."))
    elif g["cv_red"] is None and len(sent_lens) >= 6 and metrics["sentence_len_cv"] < 0.3:
        flags.append(("yellow", f"Ровный ритм (CV={metrics['sentence_len_cv']}); для этого жанра допустимо, но проверь читаемость."))
    if len(sent_lens) >= 6 and mid_share > 0.8:
        flags.append(("yellow", f"{int(mid_share * 100)} % предложений длиной 12–24 слова — проверь разнообразие ритма."))
    if len(para_lens) >= 4 and metrics["paragraph_len_cv"] < 0.3:
        flags.append(("yellow", "Абзацы почти одинаковой длины."))
    nr = g["nominal_red"]
    if metrics["nominal_per_100"] > nr:
        flags.append(("red", f"Слова с суффиксами отвлечённых существительных: {metrics['nominal_per_100']} на 100 слов (порог жанра {nr}). Переведи часть в глаголы."))
    elif metrics["nominal_per_100"] > nr - 2:
        flags.append(("yellow", f"Отвлечённые существительные: {metrics['nominal_per_100']} на 100 слов (порог жанра {nr})."))
    if metrics["copula_per_100"] > g["copula"]:
        flags.append(("yellow", f"«Является» встречается {len(copula)} раз. Замени тире, «это», «есть», где можно."))
    if metrics["triads_per_1000"] > 6 and len(triads) >= 3:
        flags.append(("yellow", f"Тройки «X, Y и Z»: {len(triads)}. Проверь, не ради ли симметрии."))
    if len(opener_hits) >= 3:
        flags.append(("yellow", f"{len(opener_hits)} абзацев начинаются с формульного зачина ({'; '.join(o.split()[0] for o in opener_hits[:4])}…)."))
    if len(bold) > max(3, len(paras) // 2):
        flags.append(("yellow", f"Жирный шрифт {len(bold)} раз — много для прозы."))
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
    if metrics["em_dash_per_100"] > 2.5:
        flags.append(("yellow", f"Тире {dashes} раз ({metrics['em_dash_per_100']} на 100 слов) — проверь, не ради ли «удара»."))
    prio = [f for f in findings if f["group"] in PRIORITY_GROUPS and not f["quiet"]]
    if len(prio) >= 3:
        flags.append(("red", f"Шаблонных оборотов из приоритетных групп: {len(prio)}."))

    return {"version": VERSION, "genre": genre, "metrics": metrics, "findings": findings,
            "flags": flags, "red": any(s == "red" for s, _ in flags)}


# ---------------------------------------------------------------- вывод
def render(report: dict, path: str) -> str:
    m = report["metrics"]
    out = [f"Проверка текста: {path} (жанр: {report['genre']})",
           f"Слов {m['words']}, предложений {m['sentences']}, абзацев {m['paragraphs']}; "
           f"знаков с пробелами {m['chars_with_spaces']}, без пробелов {m['chars_no_spaces']}.",
           f"Средняя длина предложения {m['sentence_len_mean']} слов, разброс CV={m['sentence_len_cv']}; "
           f"отвлечённых существительных {m['nominal_per_100']}/100; «является» {m['copula_count']}; троек {m['triads']}; "
           f"тире {m['em_dash_per_100']}/100; жирного {m['bold_spans']}; эмодзи {m['emoji']}; латиницы {m['latin_words']}.",
           ""]
    if report["flags"]:
        out.append("Сигналы:")
        for sev, msg in report["flags"]:
            out.append(f"  [{'КРАСНЫЙ' if sev == 'red' else 'жёлтый'}] {msg}")
        out.append("")
    if report["findings"]:
        out.append(f"Шаблонные обороты ({len(report['findings'])}):")
        by_group: dict[str, list[dict]] = {}
        for f in report["findings"]:
            by_group.setdefault(f["title"] + (" (для жанра — справочно)" if f["quiet"] else ""), []).append(f)
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
    out.append("Скрипт не видит: отсутствие автора, выдуманные факты, пустые обобщения, переводной синтаксис. "
               "Это проверяется чтением. Совпадения — повод перечитать, а не доказательство ИИ-генерации.")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Редакторская проверка русского текста; не детектор ИИ.")
    ap.add_argument("path", help="файл .txt/.md/.docx или «-» для stdin")
    ap.add_argument("--genre", choices=sorted(GENRES), default="general", help="жанровые пороги (по умолчанию general)")
    ap.add_argument("--markdown", action="store_true", help="разбирать как Markdown (для stdin и файлов без .md)")
    ap.add_argument("--keep-code", action="store_true", help="не исключать код, ссылки и HTML-комментарии в Markdown")
    ap.add_argument("--skip-quotes", action="store_true", help="исключить цитаты (строки, начинающиеся с >)")
    ap.add_argument("--json", action="store_true", help="вывод в JSON")
    ap.add_argument("--strict", action="store_true", help="код выхода 1 при красном сигнале")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args()
    try:
        raw = read_text(args.path)
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, KeyError, ET.ParseError, ValueError) as e:
        print(f"Ошибка чтения {args.path}: {e}", file=sys.stderr)
        return 2
    text = raw
    is_md = args.markdown or args.path.lower().endswith((".md", ".markdown"))
    if is_md and not args.keep_code:
        text = strip_markdown(raw, skip_quotes=args.skip_quotes)
    elif args.skip_quotes:
        text = re.sub(r"(?m)^\s*>.*$", _blank, raw)
    report = analyze(text, genre=args.genre, raw_text=raw)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report, args.path))
    return 1 if (args.strict and report["red"]) else 0


if __name__ == "__main__":
    sys.exit(main())
