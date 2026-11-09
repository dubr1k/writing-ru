"""Public canonical skills contract; generated bundles have separate tests."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / 'skills/writing-ru'
EXPECTED = {
    'russian-text-craft', 'ru-academic-article', 'ru-grant-proposal', 'ru-analytical-note',
    'ru-expert-commentary', 'ru-telegram-post', 'ru-popular-explainer', 'ru-teaching-materials',
    'ru-speech-and-scenario', 'ru-review-and-feedback', 'ru-business-correspondence', 'ru-knowledge-note',
    'ru-agent-report', 'ru-technical-docs', 'ru-transcript-editing', 'ru-translation',
    'ru-presentation-text', 'ru-official-documents', 'ru-short-copy',
}


class PackageTests(unittest.TestCase):
    def test_family_metadata_and_hermes_compatibility(self):
        skills = {p.parent.name: p for p in FAMILY.glob('*/SKILL.md')}
        self.assertEqual(set(skills), EXPECTED)
        for name, p in skills.items():
            with self.subTest(skill=name):
                text = p.read_text(encoding='utf-8')
                self.assertTrue(text.startswith('---\n'))
                fm = text.split('---', 2)[1]
                self.assertEqual(re.search(r'^name: (.+)$', fm, re.M)[1], name)
                self.assertIn('license: MIT', fm)
                self.assertIn('  hermes:', fm)
                related = re.search(r'related_skills: \[([^]]*)\]', fm)
                self.assertTrue({s.strip() for s in related[1].split(',')} <= EXPECTED)

    def test_public_relative_links_resolve(self):
        for name in json.loads((ROOT / 'export-files.json').read_text()):
            if not name.endswith('.md'): continue
            p = ROOT / name
            for target in re.findall(r'\]\(([^)\s]+)\)', p.read_text(encoding='utf-8')):
                if target.startswith(('https://', 'http://', '#', 'mailto:')): continue
                with self.subTest(file=name, target=target):
                    self.assertTrue((p.parent / target.split('#')[0]).exists())


if __name__ == '__main__':
    unittest.main()
