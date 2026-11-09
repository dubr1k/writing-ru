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
        self.assertIn('Сигналы:', p.stdout)

    def test_known_false_positives_not_flagged(self):
        p = self.cli(ROOT / 'tests/fixtures/false-positive.md', '--json', '--strict')
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        matches = {f['match'].lower() for f in report['findings']}
        self.assertFalse({'данные', 'вызовы', 'шеф'} & matches, matches)
        self.assertFalse(report['red'])

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


    def test_narrowed_patterns(self):
        report = checker.analyze('Данные лежат в файле. Журнал хранит вызовы инструментов и вызовы API.')
        self.assertEqual(report['findings'], [])
        report = checker.analyze('Данная статья посвящена тому, какие вызовы стоят перед школой.')
        self.assertEqual(groups(report), {'kancelyarit', 'landshaft'})

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
