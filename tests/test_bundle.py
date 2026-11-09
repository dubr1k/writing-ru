"""Consumer-visible installer safety checks; temporary targets only."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'skills/writing-ru'
if not SOURCE.exists():
    SOURCE = ROOT / 'skills'
INSTALL = ROOT / 'scripts/install.py'


class InstallTests(unittest.TestCase):
    def setUp(self):
        # Kept inside checkout/bundle; never create profile files.
        self.tmp = tempfile.TemporaryDirectory(prefix='.install-test-', dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.target = self.base / 'project with spaces' / 'skills'

    def run_cli(self, action='install', *args, source=SOURCE, target=None):
        return subprocess.run([sys.executable, '-I', str(INSTALL), action,
                               '--source', str(source), '--target', str(target or self.target), *args],
                              capture_output=True, text=True)

    def install(self):
        result = self.run_cli('install', '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dry_run_never_creates_parents(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target.parent.exists())

    def test_install_verify_remove_requires_apply(self):
        self.install()
        self.assertEqual(len(list(self.target.glob('*/SKILL.md'))), 19)
        self.assertEqual(self.run_cli('verify').returncode, 0)
        self.assertEqual(self.run_cli('remove').returncode, 0)
        self.assertTrue(self.target.exists())
        self.assertEqual(self.run_cli('remove', '--apply').returncode, 0)
        self.assertFalse(self.target.exists())

    def test_collision_preserves_existing_content(self):
        self.target.mkdir(parents=True)
        sentinel = self.target / 'keep'
        sentinel.write_text('foreign')
        self.assertNotEqual(self.run_cli('install', '--apply').returncode, 0)
        self.assertEqual(sentinel.read_text(), 'foreign')

    def test_modified_missing_foreign_files_and_directories_block_removal(self):
        for kind in ('modified', 'missing', 'foreign-file', 'foreign-dir', 'receipt'):
            with self.subTest(kind=kind):
                self.install()
                p = self.target / 'russian-text-craft/SKILL.md'
                original = p.read_bytes()
                if kind == 'modified': p.write_bytes(original + b'local')
                if kind == 'missing': p.unlink()
                if kind == 'foreign-file': (self.target / 'keep').write_text('foreign')
                if kind == 'foreign-dir': (self.target / 'empty').mkdir()
                if kind == 'receipt': (self.target / '.writing-ru-receipt.json').write_text('{}')
                self.assertNotEqual(self.run_cli('remove', '--apply').returncode, 0)
                self.assertTrue(self.target.exists())
                shutil.rmtree(self.target)

    def test_lexical_traversal_rejected(self):
        result = self.run_cli('install', '--apply', target=self.base / 'absent/../escape')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'escape').exists())
        self.assertNotEqual(self.run_cli(source=SOURCE / '../writing-ru').returncode, 0)

    def test_source_target_and_parent_symlinks_rejected(self):
        real = self.base / 'real'
        real.mkdir()
        link = self.base / 'link'
        link.symlink_to(real, target_is_directory=True)
        for target in (link, link / 'skills', self.base / 'dangling'):
            if target.name == 'dangling': target.symlink_to(self.base / 'absent')
            self.assertNotEqual(self.run_cli('install', '--apply', target=target).returncode, 0)
        source_link = self.base / 'source'
        source_link.symlink_to(SOURCE, target_is_directory=True)
        self.assertNotEqual(self.run_cli(source=source_link).returncode, 0)
        self.assertEqual(list(real.iterdir()), [])

    def test_symlink_in_source_and_installed_tree_rejected(self):
        source = self.base / 'source'
        shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('__pycache__'))
        p = source / 'russian-text-craft/SKILL.md'
        p.unlink()
        p.symlink_to(SOURCE / 'russian-text-craft/SKILL.md')
        self.assertNotEqual(self.run_cli(source=source).returncode, 0)
        self.install()
        installed = self.target / 'russian-text-craft/SKILL.md'
        installed.unlink()
        installed.symlink_to(SOURCE / 'russian-text-craft/SKILL.md')
        self.assertNotEqual(self.run_cli('remove', '--apply').returncode, 0)
        self.assertTrue(installed.is_symlink())

    def test_source_extra_files_cannot_be_exported(self):
        source = self.base / 'source'
        shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('__pycache__'))
        (source / 'russian-text-craft/.env').write_text('synthetic-not-a-secret')
        result = self.run_cli(source=source)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())

    def test_changed_source_cannot_authorize_removal(self):
        self.install()
        source = self.base / 'source'
        shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('__pycache__'))
        (source / 'russian-text-craft/SKILL.md').write_text('changed')
        self.assertNotEqual(self.run_cli('remove', '--apply', source=source).returncode, 0)
        self.assertTrue(self.target.exists())


if __name__ == '__main__':
    unittest.main()
