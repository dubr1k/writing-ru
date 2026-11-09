"""Verify the public package and exercise README's exact install block."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
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


def frontmatter(text):
    assert text.startswith('---\n')
    block = text[4:text.index('\n---\n', 4)]
    fields = {}
    for line in block.splitlines():
        m = re.match(r'^(\w+):\s*(.*)$', line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"')
    related = re.search(r'related_skills:\s*\[([^\]]*)\]', block)
    fields['related'] = [s.strip() for s in related.group(1).split(',')] if related else []
    return fields


class PackageTests(unittest.TestCase):
    def test_family_metadata(self):
        skills = {p.parent.name: p for p in FAMILY.glob('*/SKILL.md')}
        self.assertEqual(set(skills), EXPECTED)
        for name, p in skills.items():
            with self.subTest(skill=name):
                fm = frontmatter(p.read_text(encoding='utf-8'))
                self.assertEqual(fm['name'], name)
                self.assertEqual(fm['license'], 'MIT')
                self.assertEqual(fm['author'], 'writing-ru contributors')
                self.assertLessEqual(len(fm['description']), 60)
                self.assertTrue(fm['description'].endswith('.'))
                self.assertTrue(set(fm['related']) <= EXPECTED, fm['related'])

    def test_relative_links_resolve(self):
        for p in ROOT.rglob('*.md'):
            if '.git' in p.parts:
                continue
            for target in re.findall(r'\]\(([^)\s]+)\)', p.read_text(encoding='utf-8')):
                if target.startswith(('https://', 'http://', '#', 'mailto:')):
                    continue
                with self.subTest(file=str(p.relative_to(ROOT)), target=target):
                    self.assertTrue((p.parent / target.split('#')[0]).exists())

    def test_no_private_dir_and_no_personal_patterns(self):
        self.assertFalse(list(ROOT.rglob('private')), 'references/private must not be distributed')
        patterns = {
            'email': re.compile(r'[\w.+-]+@[\w-]+(\.[\w-]+)+'),
            'ipv4': re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
            'home path': re.compile(r'(?<![\w$])/(root|home/[\w.-]+|Users/[\w.-]+)/'),
            'telegram link': re.compile(r'\bt\.me/'),
            'private key': re.compile(r'BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY'),
        }
        for p in ROOT.rglob('*'):
            if '.git' in p.parts or not p.is_file() or p.suffix not in ('.md', '.py', '.txt', ''):
                continue
            if p.name == 'test_package.py':
                continue
            text = p.read_text(encoding='utf-8')
            for label, rx in patterns.items():
                with self.subTest(file=str(p.relative_to(ROOT)), pattern=label):
                    self.assertIsNone(rx.search(text))

    def test_readme_install_copy_collision_and_removal(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        block = next(b for b in re.findall(r'```bash\n(.*?)```', readme, re.S) if 'cp -R skills/writing-ru' in b)
        with tempfile.TemporaryDirectory(prefix='writing-ru-install-') as d:
            home = Path(d) / 'profile with spaces'
            (home / 'skills/other').mkdir(parents=True)
            sentinel = home / 'skills/other/keep.txt'
            sentinel.write_text('keep')
            env = dict(os.environ, TARGET_HOME=str(home))
            run = lambda: subprocess.run(['bash', '-c', block], cwd=ROOT, env=env, capture_output=True, text=True)
            first = run()
            self.assertEqual(first.returncode, 0, first.stderr)
            installed = home / 'skills/writing-ru'
            self.assertEqual(len(list(installed.glob('*/SKILL.md'))), len(EXPECTED))
            for source in FAMILY.rglob('*'):
                if source.is_file() and '__pycache__' not in source.parts:
                    self.assertEqual(source.read_bytes(), (installed / source.relative_to(FAMILY)).read_bytes())
            second = run()
            self.assertEqual(second.returncode, 1)
            self.assertEqual(sentinel.read_text(), 'keep')
            installed.rename(home / 'writing-ru-backup')
            self.assertEqual(run().returncode, 0)
            installed.rename(home / 'writing-ru-removed')
            self.assertEqual(sentinel.read_text(), 'keep')
            installed.symlink_to(home / 'absent')  # dangling symlink is a collision too
            self.assertEqual(run().returncode, 1)
            self.assertFalse((home / 'absent').exists())


if __name__ == '__main__':
    unittest.main()
