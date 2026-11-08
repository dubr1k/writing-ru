"""Stdlib regression suite; all document contents are synthetic."""
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
spec = importlib.util.spec_from_file_location('checker', SCRIPT)
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CheckerTests(unittest.TestCase):
    def cli(self, path, *args, text=None):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), str(path), *args],
                              input=text, text=True, encoding='utf-8', capture_output=True)

    def test_txt_positive_json_strict(self):
        p = self.cli(ROOT / 'tests/fixtures/positive.txt', '--json', '--strict')
        self.assertEqual(p.returncode, 1, p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report['red'])
        self.assertTrue(any(f['group'] == 'zachin' and f['line'] == 1 for f in report['findings']))

    def test_default_exit_is_advisory(self):
        p = self.cli(ROOT / 'tests/fixtures/positive.txt')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('Сигналы:', p.stdout)

    def test_md_false_positives_are_not_authorship(self):
        p = self.cli(ROOT / 'tests/fixtures/false-positive.md', '--json', '--strict')
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        matches = {f['match'].lower() for f in report['findings']}
        # These are deliberate broad-rule matches, not errors in the prose.
        self.assertTrue({'данные', 'вызовы'} <= matches)
        self.assertFalse(report['red'])

    def test_unicode_case_yo_and_line_numbers(self):
        report = checker.analyze('Ёж спит.\nДАВАЙТЕ РАЗБЕРЁМСЯ, что он ест. 🦔')
        self.assertTrue(any(f['group'] == 'zachin' and f['line'] == 2 for f in report['findings']))
        self.assertEqual(report['metrics']['emoji'], 1)

    def test_stdin(self):
        p = self.cli('-', '--json', '--strict', text='Кот спит. Пёс ест.')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['metrics']['words'], 4)

    def test_empty_has_zero_words(self):
        self.assertEqual(checker.analyze('')['metrics']['words'], 0)

    def test_single_red_group_match_is_not_red_flag(self):
        self.assertFalse(checker.analyze('Важно отметить: кот спит.')['red'])

    def test_docx_entities_runs_breaks_and_namespace(self):
        # A minimal XML part tests extraction, not a rendered Office document.
        xml = '''<x:document xmlns:x="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><x:body><x:p><x:r><x:t>Ёж &amp; &lt;кот&gt; &#x451;</x:t><x:tab/><x:t>ест</x:t><x:br/><x:t>сыр</x:t></x:r></x:p><x:p><x:r><x:t>В современном </x:t></x:r><x:r><x:t>мире</x:t></x:r></x:p></x:body></x:document>'''
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'sample.docx'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', xml)
            self.assertEqual(checker.read_text(str(p)), 'Ёж & <кот> ё\tест\nсыр\n\nВ современном мире')
            result = self.cli(p, '--json')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(any(f['group'] == 'zachin' for f in json.loads(result.stdout)['findings']))

    def test_docx_standard_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'sample.docx'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Кот спит.</w:t></w:r></w:p></w:body></w:document>')
            self.assertEqual(checker.read_text(str(p)), 'Кот спит.')

    def test_missing_file_fails(self):
        p = self.cli(ROOT / 'tests/fixtures/absent.txt', '--json')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, '')

    def test_strict_ooxml_docx(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'strict.docx'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', '<w:document xmlns:w="http://purl.oclc.org/ooxml/wordprocessingml/main"><w:body><w:p><w:r><w:t>В современном мире важно отметить: будущее уже здесь.</w:t></w:r></w:p></w:body></w:document>')
            result = self.cli(p, '--json', '--strict')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(json.loads(result.stdout)['red'])

    def test_unknown_docx_namespace_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'unknown.docx'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', '<document xmlns="urn:unsupported"><p>Text</p></document>')
            result = self.cli(p, '--json')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
