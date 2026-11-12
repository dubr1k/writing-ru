"""Stdlib regression suite for ru_text_check.py; all document contents are synthetic."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/writing-ru/russian-text-craft/scripts/ru_text_check.py'
if not SCRIPT.exists():
    SCRIPT = ROOT / 'skills/russian-text-craft/scripts/ru_text_check.py'
spec = importlib.util.spec_from_file_location('checker', SCRIPT)
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def groups(report):
    return {f['group'] for f in report['findings']}


class CliTests(unittest.TestCase):
    def cli(self, path, *args, text=None):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), str(path), *args],
                              input=text, text=True, encoding='utf-8', capture_output=True)

    def test_positive_txt_json_strict(self):
        p = self.cli(ROOT / 'tests/fixtures/positive.txt', '--json', '--strict')
        self.assertEqual(p.returncode, 1, p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report['red'])
        self.assertTrue(any(f['group'] == 'zachin' and f['line'] == 1 for f in report['findings']))

    def test_default_exit_is_advisory(self):
        p = self.cli(ROOT / 'tests/fixtures/positive.txt')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('Обязательно перед сдачей:', p.stdout)
        self.assertIn('Стилевые сигналы:', p.stdout)
        self.assertNotIn('\nСигналы:', p.stdout)

    def test_known_false_positives_not_flagged(self):
        p = self.cli(ROOT / 'tests/fixtures/false-positive.md', '--json', '--strict')
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        matches = {f['match'].lower() for f in report['findings']}
        self.assertFalse({'данные', 'вызовы', 'шеф', 'данным'} & matches, matches)
        self.assertFalse(report['red'])

    def test_po_dannym_not_flagged_but_dannym_sposobom_is(self):
        p = self.cli(ROOT / 'tests/fixtures/false-positive.md', '--json')
        self.assertEqual(p.returncode, 0, p.stderr)
        text = (ROOT / 'tests/fixtures/false-positive.md').read_text(encoding='utf-8')
        self.assertIn('По данным опроса', text)
        self.assertIn('Согласно данным отчёта', text)
        self.assertNotIn('kancelyarit', groups(json.loads(p.stdout)))
        p = self.cli('-', '--json', text='Данным способом пользуются редко.')
        found = [f['match'] for f in json.loads(p.stdout)['findings'] if f['group'] == 'kancelyarit']
        self.assertEqual(found, ['Данным'])

    def test_json_has_mandatory_style_and_flags_is_union(self):
        p = self.cli(ROOT / 'tests/fixtures/positive.txt', '--json')
        report = json.loads(p.stdout)
        self.assertIn('mandatory', report)
        self.assertIn('style', report)
        self.assertIn('blocking', report)
        self.assertTrue(report['style'])
        self.assertEqual(report['flags'], report['mandatory'] + report['style'])
        self.assertEqual(report['red'], any(s == 'red' for s, _ in report['flags']))

    def test_mandatory_section_in_text_report(self):
        p = self.cli('-', text='Босс, вот текст письма.')
        self.assertIn('Обязательно перед сдачей:', p.stdout)
        self.assertNotIn('Обязательные проверки пройдены', p.stdout)
        p = self.cli('-', '--max-chars', '100', text='Кот спит.')
        self.assertIn('Обязательные проверки пройдены: служебных реплик нет, технических следов нет, плейсхолдеров нет, объём 9 знаков в пределах лимита', p.stdout)
        p = self.cli('-', text='Кот спит.')
        self.assertIn('плейсхолдеров нет.', p.stdout)
        self.assertNotIn('объём', p.stdout.split('Стилевые')[0])

    def test_volume_limits_json_and_strict(self):
        text = 'Кот спит на окне. ' * 10  # 40 слов, 179 знаков после strip
        p = self.cli('-', '--json', '--strict', '--max-chars', '100', text=text)
        self.assertEqual(p.returncode, 1, p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report['blocking'])
        self.assertTrue(report['red'])
        self.assertEqual([m for _, m in report['mandatory']],
                         ['Объём: 179 знаков с пробелами при лимите 100 (+79)'])
        p = self.cli('-', '--json', '--max-words', '20', text=text)
        report = json.loads(p.stdout)
        self.assertEqual(p.returncode, 0)
        self.assertEqual([m for _, m in report['mandatory']], ['Объём: 40 слов при лимите 20 (+20)'])
        p = self.cli('-', '--json', '--strict', '--min-words', '60', text=text)
        report = json.loads(p.stdout)
        self.assertEqual(p.returncode, 1)
        self.assertEqual([m for _, m in report['mandatory']], ['Объём: 40 слов при минимуме 60 (-20)'])
        p = self.cli('-', '--json', '--strict', '--max-chars', '500', '--max-words', '100', '--min-words', '10', text=text)
        report = json.loads(p.stdout)
        self.assertFalse(report['blocking'])
        self.assertEqual(report['mandatory'], [])

    def test_no_volume_args_no_volume_check(self):
        report = json.loads(self.cli('-', '--json', text='Кот спит. ' * 5000).stdout)
        self.assertFalse(report['blocking'])
        self.assertEqual(report['limits'], {})

    def test_bad_volume_args_rejected(self):
        self.assertEqual(self.cli('-', '--max-chars', '-5', text='Кот.').returncode, 2)
        self.assertEqual(self.cli('-', '--min-words', '9', '--max-words', '3', text='Кот.').returncode, 2)

    def test_leak_is_mandatory_not_style(self):
        report = json.loads(self.cli('-', '--json', text='Босс, вот текст письма.').stdout)
        self.assertTrue(report['blocking'])
        self.assertTrue(any('Служебные реплики' in m for _, m in report['mandatory']))
        self.assertFalse(any('Служебные реплики' in m for _, m in report['style']))

    def test_fail_on_blocking_ignores_style_red_but_strict_does_not(self):
        fixture = ROOT / 'tests/fixtures/positive.txt'
        self.assertEqual(self.cli(fixture, '--strict').returncode, 1)
        p = self.cli(fixture, '--fail-on-blocking', '--json')
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report['red'])
        self.assertFalse(report['blocking'])
        self.assertEqual(self.cli('-', '--fail-on-blocking', text='Босс, вот текст письма.').returncode, 1)
        self.assertEqual(self.cli('-', '--fail-on-blocking', '--max-words', '1', text='Кот спит.').returncode, 1)
        self.assertEqual(self.cli('-', '--fail-on-blocking', '--strict', text='Кот спит.').returncode, 0)

    def test_tech_marker_blocks_plain_text_with_place_and_type(self):
        p = self.cli('-', '--json', '--fail-on-blocking', text='Кот спит.\nРезультат подтверждён. contentReference[oaicite:1]')
        self.assertEqual(p.returncode, 1, p.stderr)
        report = json.loads(p.stdout)
        hit = [f for f in report['findings'] if f['group'] == 'tech_leak']
        self.assertEqual([(f['line'], f['match'], f['where']) for f in hit], [(2, 'contentReference[oaicite:1]', 'text')])
        message = ' '.join(m for _, m in report['mandatory'])
        self.assertIn('стр. 2', message)
        self.assertIn('contentReference[oaicite:1]', message)
        self.assertNotRegex(p.stdout.lower(), r'написан\w* (ии|нейросет)|сгенерирован')

    def test_documented_marker_example_in_markdown_code_does_not_block(self):
        md = ('# Справка\n\nМаркер `contentReference[oaicite:1]` остаётся после вставки из чата.\n\n'
              '```text\nciteturn0search0\n```\n')
        p = self.cli('-', '--markdown', '--json', '--fail-on-blocking', '--strict', '--genre', 'technical', text=md)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = json.loads(p.stdout)
        self.assertFalse(report['blocking'])
        self.assertEqual({(f['line'], f['where']) for f in report['findings'] if f['group'] == 'tech_leak'},
                         {(3, 'code'), (6, 'code')})
        self.assertEqual(len(report['notes']), 1)
        self.assertIn('не блокируют', report['notes'][0])
        # Тот же маркер вне кода — уже мусор.
        p = self.cli('-', '--markdown', '--json', '--fail-on-blocking', text='Вывод подтверждён contentReference[oaicite:1].')
        self.assertEqual(p.returncode, 1)

    def test_hidden_comment_leak_blocks_and_draft_note_is_yellow(self):
        md = 'Текст публикации.\n\n<!-- Если хотите, могу подготовить ещё вариант. -->\n'
        p = self.cli('-', '--markdown', '--json', '--fail-on-blocking', text=md)
        self.assertEqual(p.returncode, 1, p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(any('скрытом HTML-комментарии' in m and 'стр. 3' in m for _, m in report['mandatory']))
        self.assertEqual([f['where'] for f in report['findings'] if f['group'] == 'agent_leak'], ['comment'])
        md = 'Текст публикации.\n\n<!-- TODO: добавить таблицу -->\n<!-- будущее уже здесь -->\n'
        p = self.cli('-', '--markdown', '--json', '--fail-on-blocking', text=md)
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        self.assertFalse(report['blocking'])
        self.assertTrue(any(s == 'yellow' and 'HTML-комментариях' in m for s, m in report['style']))
        self.assertEqual({f['group'] for f in report['findings']}, {'placeholder'})

    def test_chat_tracking_parameter_in_link_blocks_ordinary_utm_does_not(self):
        md = 'Источник: [отчёт](https://example.org/report?utm_source=chatgpt.com).\n'
        report = json.loads(self.cli('-', '--markdown', '--json', text=md).stdout)
        self.assertTrue(report['blocking'])
        md = 'Источник: [отчёт](https://example.org/report?utm_source=newsletter) и работы [1, 2].\n'
        report = json.loads(self.cli('-', '--markdown', '--json', text=md).stdout)
        self.assertFalse(report['blocking'])
        self.assertEqual(report['findings'], [])

    def test_stdin_and_markdown_flag(self):
        p = self.cli('-', '--json', '--markdown', text='Кот спит. `В современном мире` — это код.')
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        self.assertNotIn('zachin', groups(report))

    def test_missing_file_exit_2(self):
        p = self.cli(ROOT / 'tests/fixtures/absent.txt', '--json')
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, '')
        self.assertIn('Ошибка чтения', p.stderr)

    def test_chat_cli_and_read_errors(self):
        p = self.cli('-', '--chat', '--fail-on-blocking', text='Шеф, обновление выполнено.')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('сообщение в чат', p.stdout)
        self.assertIn('Обязательные проверки пройдены: технических следов нет, плейсхолдеров нет', p.stdout)
        self.assertEqual(self.cli('-', '--fail-on-blocking', text='Шеф, обновление выполнено.').returncode, 1)
        with tempfile.TemporaryDirectory() as d:
            missing = self.cli(Path(d) / 'missing.md', '--fail-on-blocking')
            self.assertEqual(missing.returncode, 2)
            self.assertIn('Ошибка чтения', missing.stderr)
            self.assertEqual(missing.stdout, '')
            broken = Path(d) / 'broken.docx'
            broken.write_bytes(b'not a zip archive')
            self.assertEqual(self.cli(broken, '--fail-on-blocking').returncode, 2)

    def test_invalid_genre_rejected(self):
        p = self.cli(ROOT / 'tests/fixtures/positive.txt', '--genre', 'poetry')
        self.assertNotEqual(p.returncode, 0)

    def test_docx_cli_and_strict_ooxml(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'strict.docx'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', '<w:document xmlns:w="http://purl.oclc.org/ooxml/wordprocessingml/main"><w:body><w:p><w:r><w:t>В современном мире важно отметить: будущее уже здесь.</w:t></w:r></w:p></w:body></w:document>')
            result = self.cli(p, '--json', '--strict')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(json.loads(result.stdout)['red'])

    def test_unknown_docx_namespace_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'unknown.docx'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', '<document xmlns="urn:unsupported"><p>Text</p></document>')
            result = self.cli(p, '--json')
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')


class AnalyzeTests(unittest.TestCase):
    def test_unicode_case_yo_and_line_numbers(self):
        report = checker.analyze('Ёж спит.\nДАВАЙТЕ РАЗБЕРЁМСЯ, что он ест. 🦔')
        self.assertTrue(any(f['group'] == 'zachin' and f['line'] == 2 for f in report['findings']))
        self.assertEqual(report['metrics']['emoji'], 1)

    def test_empty_text(self):
        report = checker.analyze('')
        self.assertEqual(report['metrics']['words'], 0)
        self.assertFalse(report['red'])

    def test_single_priority_match_is_not_red(self):
        self.assertFalse(checker.analyze('Важно отметить: кот спит.')['red'])

    def test_agent_leak_is_red_on_single_match(self):
        for text in ('Босс, вот текст письма.', 'Вот вариант: Уважаемый коллега!', 'Готово! Письмо ниже.',
                     'Надеюсь, это поможет при подготовке.', 'Если хотите, могу сократить.'):
            with self.subTest(text=text):
                report = checker.analyze(text)
                self.assertIn('agent_leak', groups(report))
                self.assertTrue(report['red'])

    def test_shef_as_ordinary_word_is_not_leak(self):
        report = checker.analyze('Шеф-повар ушёл. Шефство над школой продлили. Начальник — шеф отдела.\nГотово, когда все пункты проверены.')
        self.assertNotIn('agent_leak', groups(report))

    def test_placeholder_is_red(self):
        for text in ('Срок — [уточнить у автора: дата].', 'Подпись: <имя>.', 'TODO: дописать вывод.'):
            with self.subTest(text=text):
                report = checker.analyze(text)
                self.assertIn('placeholder', groups(report))
                self.assertTrue(report['red'])

    def test_fences_preserve_lines_and_do_not_close_on_inner_marker(self):
        md = '  ````python\nTODO\n```\nTODO\n  ````\nКот спит.\nTODO: конец.'
        cleaned = checker.strip_markdown(md)
        report = checker.analyze(cleaned)
        self.assertEqual([f['line'] for f in report['findings']], [7])
        self.assertEqual(len(cleaned.splitlines()), len(md.splitlines()))

    def test_unclosed_fence_ignores_remaining_code(self):
        self.assertEqual(checker.analyze(checker.strip_markdown('~~~text\nTODO'))['findings'], [])

    def test_multibacktick_inline_code_and_quote_scope(self):
        md = 'Команда ``print(`TODO`)`` готова.\n> TODO\nTODO'
        report = checker.analyze(checker.strip_markdown(md, skip_quotes=True))
        self.assertEqual([f['line'] for f in report['findings']], [3])

    def test_unmatched_inline_delimiter_keeps_prose(self):
        report = checker.analyze(checker.strip_markdown('Символ ` не закрыт. TODO'))
        self.assertIn('placeholder', groups(report))

    def test_literal_quote_can_be_red_but_is_not_an_authorship_verdict(self):
        report = checker.analyze('В диалоге сказано: «Вот вариант: кот спит».')
        self.assertTrue(report['red'])
        self.assertIn('agent_leak', groups(report))


    def test_known_tech_markers(self):
        markers = (':contentReference[oaicite:0]{index=0}', 'contentReference[oaicite:16]', '[oai_citation:0‡example.org]',
                   'citeturn0search0', 'turn0image4', 'citeturn1file0', '({"attribution":{"attributableIndex":"1009-1"}})',
                   '[cite_start]', '[cite: 2, 6]', '[span_1](start_span)', '<grok-card data-id="e8ff4f">',
                   'grok_render_citation_card_json', '【85†L261-269】', 'attached_file:1', 'ppl-ai-file-upload',
                   'https://example.org/?utm_source=openai', 'https://example.org/?a=1&utm_source=copilot.com',
                   'https://example.org/?referrer=grok.com')
        for marker in markers:
            with self.subTest(marker=marker):
                report = checker.analyze('Вывод подтверждён ' + marker + ' и описан.')
                found = [f for f in report['findings'] if f['group'] == 'tech_leak']
                self.assertEqual(len(found), 1, found)
                self.assertTrue(report['blocking'])
        for clean in ('В работах [1, 2] метод описан.', 'Функция return0 вызвана.', 'Адрес example.org/?utm_source=newsletter.',
                      'Значение utm_source=chatgpt.company не служебное.', 'Сноска † и скобки 【так】.'):
            with self.subTest(clean=clean):
                self.assertNotIn('tech_leak', groups(checker.analyze(clean)))

    def test_word_count_rule(self):
        cases = {
            'В 2024 году — 17 случаев и 3 проверки.': (8, 9),
            'Бюджет 10 000 рублей.': (3, 3),
            'Бюджет 10\u00a0000 рублей и 1 250 000 знаков.': (6, 6),
            'Рост 3,5 % за 2020–2024 годы.': (5, 6),
            'А. С. Пушкин и кто-то из научно-технического совета.': (8, 8),
            'Пункты 5 200 и 2024 123 разные.': (6, 6),
            '— № %': (0, 3),
            '': (0, 0),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                m = checker.analyze(text)['metrics']
                self.assertEqual((m['words'], m['whitespace_tokens']), expected)
        self.assertEqual(checker.analyze('В 2024 году — 17 случаев и 3 проверки.')['metrics']['lexical_words'], 5)

    def test_word_count_markdown_excludes_markup_code_links_and_list_numbers(self):
        md = ('# Итог\n\n1. Первый шаг\n2. Второй шаг: `retry_count = 3`\n\n'
              'См. [отчёт за 2024 год](https://example.org/very/long/path).\n\n```\nкод не считается\n```\n'
              '<!-- комментарий не считается -->\n')
        layers = checker.markdown_layers(md)
        m = checker.analyze(layers['prose'], raw_text=md, layers=layers)['metrics']
        # Итог | Первый шаг | Второй шаг: | См. отчёт за 2024 год
        self.assertEqual(m['words'], 10)
        report = checker.analyze(layers['prose'], raw_text=md, layers=layers, max_words=9)
        self.assertEqual(report['mandatory'], [('red', 'Объём: 10 слов при лимите 9 (+1)')])

    def test_layers_keep_length_and_line_numbers(self):
        md = 'Текст `код` тут.\n<!-- скрыто\nвторая -->\n```\nблок\n```\n[ссылка](https://example.org/x)\n'
        layers = checker.markdown_layers(md)
        for name, layer in layers.items():
            with self.subTest(layer=name):
                self.assertEqual(len(layer), len(md))
                self.assertEqual(layer.count('\n'), md.count('\n'))
        self.assertEqual(layers['prose'], checker.strip_markdown(md))
        self.assertIn('скрыто', layers['comments'])
        self.assertNotIn('скрыто', layers['prose'] + layers['visible'] + layers['code'])
        self.assertIn('код', layers['code'])
        self.assertIn('блок', layers['code'])
        self.assertIn('example.org', layers['visible'])
        self.assertNotIn('example.org', layers['prose'])

    def test_short_text_gets_no_density_verdicts(self):
        for text in ('Текст публикации.', 'Квадрат является прямоугольником. Круг является плоской фигурой.',
                     'В 2024 году — 17 случаев и 3 проверки.'):
            with self.subTest(text=text):
                self.assertEqual(checker.analyze(text)['style'], [])

    def test_style_messages_are_reading_questions_not_orders(self):
        monotone = ' '.join('Кот видит дом и спит у окна там.' for _ in range(8))
        copula = ' '.join('Этот объект является важной частью нашей общей системы.' for _ in range(8))
        nominals = ' '.join(f'Кот видит {w} и спит.' for w in
                            ['проведения', 'оценивания', 'выполнения', 'рассмотрения', 'согласования', 'обсуждения',
                             'заключения', 'развития', 'исполнения', 'утверждения', 'распределения', 'планирования'])
        messages = [m for text in (monotone, copula, nominals) for _, m in checker.analyze(text)['style']]
        joined = ' '.join(messages)
        self.assertIn('мешает ли однообразие', joined)
        self.assertIn('«Является»: 8', joined)
        self.assertIn('не спрятаны ли за ними действие', joined)
        for order in ('Добавь короткие', 'Переведи часть в глаголы', 'Замени тире'):
            self.assertNotIn(order, joined)

    def test_dannym_noun_vs_adjective(self):
        for text in ('Доступ к данным предоставляется после согласования.', 'По данным опроса, доля выросла.',
                     'Согласно данным отчёта, рост продолжился.', 'Ключи к данным хранятся отдельно.'):
            self.assertNotIn('kancelyarit', groups(checker.analyze(text)), text)
        for text, word in (('Документ соответствует данным требованиям.', 'данным'),
                           ('Порядок утверждён данным приказом.', 'данным'), ('Данный отчёт опубликован.', 'Данный')):
            found = [f['match'] for f in checker.analyze(text)['findings'] if f['group'] == 'kancelyarit']
            self.assertEqual(found, [word], text)

    def test_chat_mode_keeps_placeholders_and_traces_blocking(self):
        greeting = 'Босс, nginx обновлён до 1.28.0, сайт отвечает.'
        self.assertTrue(checker.analyze(greeting)['blocking'])
        chat = checker.analyze(greeting, chat=True)
        self.assertFalse(chat['blocking'])
        self.assertTrue(chat['chat'])
        self.assertTrue(any('Реплики чата' in msg for _, msg in chat['style']))
        self.assertTrue(checker.analyze(greeting + ' Срок: [уточнить].', chat=True)['blocking'])
        self.assertTrue(checker.analyze(greeting + ' contentReference[oaicite:1]', chat=True)['blocking'])
        self.assertTrue(checker.analyze(greeting, chat=True, raw_text=greeting, max_chars=10)['blocking'])

    def test_narrowed_patterns(self):
        report = checker.analyze('Данные лежат в файле. Журнал хранит вызовы инструментов и вызовы API.')
        self.assertEqual(report['findings'], [])
        report = checker.analyze('Данная статья посвящена тому, какие вызовы стоят перед школой.')
        self.assertEqual(groups(report), {'kancelyarit', 'landshaft'})

    def test_analyze_volume_arguments(self):
        report = checker.analyze('Кот спит.', raw_text='Кот спит.', max_chars=5)
        self.assertEqual(report['mandatory'], [('red', 'Объём: 9 знаков с пробелами при лимите 5 (+4)')])
        report = checker.analyze('Кот спит.', raw_text='Кот спит.')
        self.assertFalse(report['blocking'])

    def test_markdown_code_urls_and_comments_ignored_lines_preserved(self):
        md = ('# Заголовок\n\n```text\nВ современном мире важно отметить\n```\n\n'
              'Ссылка https://example.org/в-современном-мире и `данный код`.\n'
              '<!-- будущее уже здесь -->\n\nВ современном мире кот спит.\n')
        report = checker.analyze(checker.strip_markdown(md), raw_text=md)
        lines = [f['line'] for f in report['findings']]
        self.assertEqual(lines, [10], report['findings'])

    def test_skip_quotes(self):
        md = '> В современном мире важно отметить.\n\nКот спит.\n'
        self.assertIn('zachin', groups(checker.analyze(md)))
        self.assertNotIn('zachin', groups(checker.analyze(checker.strip_markdown(md, skip_quotes=True))))

    def test_genre_changes_thresholds_not_rules(self):
        nominals = ['проведения', 'оценивания', 'выполнения', 'рассмотрения', 'согласования',
                    'обсуждения', 'заключения', 'развития', 'исполнения', 'утверждения',
                    'распределения', 'планирования', 'ответственности']
        self.assertTrue(all(checker.is_nominal(w) for w in nominals))
        # 13 отвлечённых на 111 слов ≈ 11,7 на 100: выше порога general (10), ниже official (16).
        text = ' '.join(f'Кот видит {w} и спит у окна дома.' for w in nominals) + ' В рамках дня кот спит у окна.'
        general = checker.analyze(text, genre='general')
        official = checker.analyze(text, genre='official')
        self.assertTrue(any('отвлечённых' in m for s, m in general['flags'] if s == 'red'))
        self.assertFalse(any('отвлечённых' in m for s, m in official['flags'] if s == 'red'))
        self.assertIn('kancelyarit', groups(official))  # правило осталось, сменился порог

    def test_bold_list_red_in_prose_yellow_in_technical(self):
        md = '- **Скорость:** быстро\n- **Цена:** дёшево\n'
        self.assertTrue(checker.analyze(md, genre='general')['red'])
        self.assertFalse(checker.analyze(md, genre='technical')['red'])

    def test_char_metrics(self):
        report = checker.analyze('Кот спит.', raw_text='Кот спит.')
        self.assertEqual(report['metrics']['chars_with_spaces'], 9)
        self.assertEqual(report['metrics']['chars_no_spaces'], 8)

    def test_hyphen_as_dash(self):
        self.assertEqual(checker.analyze('Москва - столица России.')['metrics']['hyphen_as_dash'], 1)
        self.assertEqual(checker.analyze('Москва — столица, а кто-то спорит.')['metrics']['hyphen_as_dash'], 0)

    def test_docx_entities_runs_breaks_and_prefix(self):
        xml = f'''<x:document xmlns:x="{W}"><x:body><x:p><x:r><x:t>Ёж &amp; &lt;кот&gt; &#x451;</x:t><x:tab/><x:t>ест</x:t><x:br/><x:t>сыр</x:t></x:r></x:p><x:p><x:r><x:t>В современном </x:t></x:r><x:r><x:t>мире</x:t></x:r></x:p></x:body></x:document>'''
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'sample.docx'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', xml)
            self.assertEqual(checker.read_text(str(p)), 'Ёж & <кот> ё\tест\nсыр\n\nВ современном мире')


if __name__ == '__main__':
    unittest.main()
