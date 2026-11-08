#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Редакторские сигналы: шаблонные обороты и монотонность.

Только стандартная библиотека. Вход: .txt, .md, .docx (или stdin при «-»).
Выход: отчёт на русском; --json — машинный вывод; --strict — код 1 при красных находках.

Это эвристики для ручной проверки, не определение авторства или ИИ-генерации.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------- стоп-фразы
# Группы соответствуют references/ru-ai-patterns.md. Регексы без учёта регистра.
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
        r"\bцифров\w+ сред[аыеу]\b", r"\bвызов(ы|ов|ам)\b", r"\bтренд",
    ]),
    "kancelyarit": ("Канцелярит", [
        r"\bданн(ый|ая|ое|ые|ого|ой|ых|ым|ому)\b", r"\bв рамках\b", r"\bв целях\b", r"\bосуществл\w+",
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
        r"\bвполне возможно, что\b", r"\bотличный вопрос\b", r"\bвы абсолютно правы\b", r"\bнадеюсь, это поможет\b",
        r"\bесли нужно, могу\b", r"\bи это нормально\b", r"\bне стоит переживать\b", r"\bвы не одиноки\b",
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
}

# Приоритетные группы: три совпадения дают красный сигнал (не вердикт).
RED_GROUPS = {"zachin", "znachimost", "itog", "ssylki", "hedging"}

NOMINAL_SUFFIX = re.compile(r"\w+(ение|ание|яние|тие|ость|есть|ация|яция|изация|ние)\b", re.I)
NOMINAL_STOP = {"время", "мнение", "знание", "решение", "значение", "отношение", "новость", "область",
                "возможность", "ценность", "сущность", "честность", "скорость", "часть", "жизнь"}
COPULA = re.compile(r"\b(является|являются|являлся|являлась|являлись|являться)\b", re.I)
TRIAD = re.compile(r"\b[\w-]+,\s+[\w-]+\s+и\s+[\w-]+\b")
PARA_OPENERS = re.compile(r"^\s*(таким образом|итак|в итоге|в целом|подводя|кроме того|более того|также|помимо этого|вместе с тем|при этом|однако|важно|стоит|следует)\b", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF]")
LATIN_WORD = re.compile(r"\b[A-Za-z]{3,}\b")
BOLD_MD = re.compile(r"\*\*[^*\n]+\*\*")
BOLD_COLON_LIST = re.compile(r"^\s*[-*•]\s*\*\*[^*\n]+:?\*\*\s*:?", re.M)
HEADING_COLON = re.compile(r"^#{1,6}\s+[^\n:]{2,60}:\s+\S", re.M)
STRAIGHT_QUOTES = re.compile(r'"[^"\n]{2,}"')
RHETORIC = re.compile(r"\?\s+(Это значит|Ответ|Потому что|Да,|Нет,|Конечно|Очевидно)", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[«\"A-ZА-ЯЁ0-9])")
WORD = re.compile(r"[А-Яа-яЁёA-Za-z][\w-]*")


# ---------------------------------------------------------------- ввод
def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    p = Path(path)
    if p.suffix.lower() == ".docx":
        return docx_text(p)
    return p.read_text(encoding="utf-8", errors="replace")


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


# ---------------------------------------------------------------- анализ
def split_paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text)]
    return [p for p in paras if p and not p.startswith("---") and not p.startswith("|")]


def split_sentences(para: str) -> list[str]:
    flat = re.sub(r"\s+", " ", para).strip()
    parts = SENT_SPLIT.split(flat)
    return [s for s in parts if len(WORD.findall(s)) >= 2]


def cv(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    return statistics.pstdev(values) / mean if mean else 0.0


def analyze(text: str) -> dict:
    lines = text.splitlines()
    paras = split_paragraphs(text)
    sentences = [s for p in paras for s in split_sentences(p)]
    words = WORD.findall(text)
    n_words = len(words) or 1
    sent_lens = [len(WORD.findall(s)) for s in sentences]
    para_lens = [len(WORD.findall(p)) for p in paras]

    findings: list[dict] = []
    for key, (title, patterns) in STOP_GROUPS.items():
        for pat in patterns:
            rx = re.compile(pat, re.I)
            for i, line in enumerate(lines, 1):
                for m in rx.finditer(line):
                    start = max(0, m.start() - 35)
                    end = min(len(line), m.end() + 35)
                    findings.append({"group": key, "title": title, "line": i,
                                     "match": m.group(0), "context": line[start:end].strip()})

    nominal = [w for w in words if NOMINAL_SUFFIX.fullmatch(w) and w.lower() not in NOMINAL_STOP and len(w) > 6]
    copula = COPULA.findall(text)
    triads = TRIAD.findall(text)
    opener_hits = [p[:60] for p in paras if PARA_OPENERS.match(p)]
    bold = BOLD_MD.findall(text)
    bold_lists = BOLD_COLON_LIST.findall(text)
    head_colon = HEADING_COLON.findall(text)
    emoji = EMOJI.findall(text)
    latin = LATIN_WORD.findall(text)
    straight = STRAIGHT_QUOTES.findall(text)
    rhetoric = RHETORIC.findall(text)
    dashes = text.count("—")

    mid_share = (sum(1 for n in sent_lens if 12 <= n <= 24) / len(sent_lens)) if sent_lens else 0.0

    metrics = {
        "words": len(words), "sentences": len(sentences), "paragraphs": len(paras),
        "sentence_len_mean": round(statistics.mean(sent_lens), 1) if sent_lens else 0,
        "sentence_len_cv": round(cv(sent_lens), 2),
        "sentence_mid_share": round(mid_share, 2),
        "paragraph_len_cv": round(cv(para_lens), 2),
        "nominal_per_100": round(100 * len(nominal) / n_words, 1),
        "copula_count": len(copula), "copula_per_100": round(100 * len(copula) / n_words, 2),
        "triads": len(triads), "triads_per_1000": round(1000 * len(triads) / n_words, 1),
        "paragraph_formula_openers": len(opener_hits),
        "em_dash_per_100": round(100 * dashes / n_words, 1),
        "bold_spans": len(bold), "bold_colon_list_items": len(bold_lists),
        "headings_with_colon": len(head_colon), "emoji": len(emoji),
        "latin_words": len(latin), "straight_quote_spans": len(straight),
        "rhetorical_qa": len(rhetoric),
    }

    flags: list[tuple[str, str]] = []  # (severity, message)
    if sent_lens and len(sent_lens) >= 6 and metrics["sentence_len_cv"] < 0.35:
        flags.append(("red", f"Монотонный ритм: разброс длины предложений низкий (CV={metrics['sentence_len_cv']}, средняя {metrics['sentence_len_mean']} слов). Добавь короткие и длинные."))
    if sent_lens and mid_share > 0.8 and len(sent_lens) >= 6:
        flags.append(("yellow", f"{int(mid_share*100)} % предложений длиной 12–24 слова — проверь разнообразие ритма."))
    if len(para_lens) >= 4 and metrics["paragraph_len_cv"] < 0.3:
        flags.append(("yellow", "Абзацы почти одинаковой длины."))
    if metrics["nominal_per_100"] > 6:
        flags.append(("red", f"Слова с суффиксами отвлечённых существительных: {metrics['nominal_per_100']} на 100 слов. Эвристический порог 6; проверь жанр и контекст."))
    elif metrics["nominal_per_100"] > 4:
        flags.append(("yellow", f"Отглагольные существительные: {metrics['nominal_per_100']} на 100 слов."))
    if metrics["copula_per_100"] > 0.6:
        flags.append(("yellow", f"«Является» встречается {len(copula)} раз. Замени тире, «это», «есть»."))
    if metrics["triads_per_1000"] > 6 and len(triads) >= 3:
        flags.append(("yellow", f"Тройки «X, Y и Z»: {len(triads)}. Проверь, не ради ли симметрии."))
    if len(opener_hits) >= 3:
        flags.append(("yellow", f"{len(opener_hits)} абзацев начинаются с формульного зачина ({'; '.join(o.split()[0] for o in opener_hits[:4])}…)."))
    if len(bold) > max(3, len(paras) // 2):
        flags.append(("yellow", f"Жирный шрифт {len(bold)} раз — много для прозы."))
    if bold_lists:
        flags.append(("red", f"Список с жирными заголовками: {len(bold_lists)} пунктов. Проверь уместность для жанра; в инструкции это может быть полезно."))
    if head_colon:
        flags.append(("yellow", f"Заголовки вида «X: Y»: {len(head_colon)}."))
    if emoji and len(emoji) > 2:
        flags.append(("yellow", f"Эмодзи: {len(emoji)}. Уместны как интонация, не как маркеры."))
    if straight:
        flags.append(("yellow", f"Прямые кавычки \"…\": {len(straight)}. В русском тексте — «ёлочки»."))
    if rhetoric:
        flags.append(("yellow", f"Риторический вопрос с немедленным ответом: {len(rhetoric)}."))
    if metrics["em_dash_per_100"] > 2.5:
        flags.append(("yellow", f"Тире {dashes} раз ({metrics['em_dash_per_100']} на 100 слов) — проверь, не ради ли «удара»."))

    red_findings = [f for f in findings if f["group"] in RED_GROUPS]
    if len(red_findings) >= 3:
        flags.append(("red", f"Стоп-фраз из красных групп: {len(red_findings)}."))

    return {"metrics": metrics, "findings": findings, "flags": flags,
            "red": any(s == "red" for s, _ in flags)}


# ---------------------------------------------------------------- вывод
def render(report: dict, path: str) -> str:
    m = report["metrics"]
    out = [f"Проверка текста: {path}",
           f"Слов {m['words']}, предложений {m['sentences']}, абзацев {m['paragraphs']}; "
           f"средняя длина предложения {m['sentence_len_mean']} слов, разброс CV={m['sentence_len_cv']}.",
           f"Отглагольных существительных {m['nominal_per_100']}/100 слов; «является» {m['copula_count']}; "
           f"троек {m['triads']}; формульных зачинов абзацев {m['paragraph_formula_openers']}; "
           f"тире {m['em_dash_per_100']}/100 слов; жирного {m['bold_spans']}; эмодзи {m['emoji']}; латиницы {m['latin_words']}.",
           ""]
    if report["flags"]:
        out.append("Сигналы:")
        for sev, msg in report["flags"]:
            out.append(f"  [{'КРАСНЫЙ' if sev == 'red' else 'жёлтый'}] {msg}")
        out.append("")
    if report["findings"]:
        out.append(f"Стоп-фразы ({len(report['findings'])}):")
        by_group: dict[str, list[dict]] = {}
        for f in report["findings"]:
            by_group.setdefault(f["title"], []).append(f)
        for title, items in by_group.items():
            out.append(f"  {title} — {len(items)}")
            for f in items[:12]:
                out.append(f"    стр. {f['line']}: «{f['match']}» … {f['context']}")
            if len(items) > 12:
                out.append(f"    … ещё {len(items) - 12}")
        out.append("")
    else:
        out.append("Стоп-фраз не найдено.")
        out.append("")
    out.append("Что скрипт не видит: отсутствие автора, выдуманные факты, пустые обобщения, "
               "переводной синтаксис. Это проверяется чтением (см. ru-ai-patterns.md, группа 15).")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Редакторская проверка русского текста; не детектор ИИ.")
    ap.add_argument("path", help="файл .txt/.md/.docx или «-» для stdin")
    ap.add_argument("--json", action="store_true", help="вывод в JSON")
    ap.add_argument("--strict", action="store_true", help="код выхода 1 при красных сигналах")
    args = ap.parse_args()
    text = read_text(args.path)
    report = analyze(text)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report, args.path))
    return 1 if (args.strict and report["red"]) else 0


if __name__ == "__main__":
    sys.exit(main())
