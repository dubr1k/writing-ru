"""Verify public package and exercise README's exact install block."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_twelve_skills_and_relative_links(self):
        skills = list((ROOT / 'skills/writing-ru').glob('*/SKILL.md'))
        self.assertEqual(len(skills), 12)
        for p in skills:
            text = p.read_text(encoding='utf-8')
            self.assertIn('name: ' + p.parent.name + '\n', text)
            self.assertIn('license: MIT\n', text)
        for p in ROOT.rglob('*.md'):
            if '.git' in p.parts:
                continue
            for target in re.findall(r'\]\(([^)]+)\)', p.read_text(encoding='utf-8')):
                if target.startswith(('https://', 'http://', '#')):
                    continue
                self.assertTrue((p.parent / target.split('#')[0]).exists(), (p, target))

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
            self.assertEqual(len(list(installed.glob('*/SKILL.md'))), 12)
            for source in (ROOT / 'skills/writing-ru').rglob('*'):
                if source.is_file() and '__pycache__' not in source.parts:
                    self.assertEqual(source.read_bytes(), (installed / source.relative_to(ROOT / 'skills/writing-ru')).read_bytes())
            second = run()
            self.assertEqual(second.returncode, 1)
            self.assertEqual(sentinel.read_text(), 'keep')
            installed.rename(home / 'writing-ru-backup')
            self.assertFalse(installed.exists())
            self.assertEqual(run().returncode, 0)
            installed.rename(home / 'writing-ru-removed')
            self.assertEqual(sentinel.read_text(), 'keep')
            # Dangling symlink is also a collision, never a destination to follow.
            installed.symlink_to(home / 'absent')
            self.assertEqual(run().returncode, 1)
            self.assertFalse((home / 'absent').exists())

    def test_no_private_key_in_distributed_skills(self):
        forbidden = ('BEGIN PRIVATE KEY',)
        for base in ('skills', 'examples'):
            for p in (ROOT / base).rglob('*'):
                if p.suffix in ('.md', '.py'):
                    text = p.read_text(encoding='utf-8')
                    for marker in forbidden:
                        self.assertNotIn(marker, text, str(p))


if __name__ == '__main__':
    unittest.main()
