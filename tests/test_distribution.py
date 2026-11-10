"""Reproducible export and platform bundle consumer contracts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ('openclaw', 'codex', 'claude-code', 'pi', 'oh-my-pi')


class DistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='.build-test-', dir=ROOT)
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.out = Path(cls.tmp.name) / 'first'
        cls.build(cls.out)

    @classmethod
    def build(cls, out):
        p = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/build.py'), '--output', str(out)],
                           text=True, capture_output=True)
        if p.returncode:
            raise AssertionError(p.stderr)

    def test_reproducible_archives_and_checksums(self):
        second = Path(self.tmp.name) / 'second'
        self.build(second)
        first_files = {p.name: p.read_bytes() for p in self.out.iterdir()}
        self.assertEqual(first_files, {p.name: p.read_bytes() for p in second.iterdir()})
        for line in (self.out / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ')
            self.assertEqual(hashlib.sha256((self.out / name).read_bytes()).hexdigest(), digest)

    def test_each_platform_complete_portable_and_linked(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform), zipfile.ZipFile(self.out / f'writing-ru-{platform}.zip') as z:
                names = z.namelist()
                prefix = f'writing-ru-{platform}/'
                skill_files = [n for n in names if re.fullmatch(re.escape(prefix) + r'skills/[^/]+/SKILL.md', n)]
                self.assertEqual(len(skill_files), 19)
                for name in names:
                    self.assertNotIn('private', Path(name).parts)
                    self.assertFalse(stat.S_ISLNK(z.getinfo(name).external_attr >> 16))
                    if not name.endswith('.md'): continue
                    text = z.read(name).decode()
                    if name in skill_files:
                        fm = text.split('---', 2)[1]
                        self.assertEqual(set(re.findall(r'^([\w-]+):', fm, re.M)),
                                         {'name', 'description', 'license', 'compatibility'})
                        self.assertNotRegex(text, r'skill_view|terminal\(command=|metadata:\s*\n\s+hermes:')
                    for link in re.findall(r'\]\(([^)\s]+)\)', text):
                        if link.startswith(('https:', 'http:', '#', 'mailto:')): continue
                        # POSIX normalize without following a filesystem symlink.
                        parts = list(Path(name).parent.parts)
                        for part in link.split('#')[0].split('/'):
                            if part == '..': parts.pop()
                            elif part not in ('', '.'): parts.append(part)
                        self.assertIn('/'.join(parts), names, (name, link))
                for required in ('LICENSE', 'CREDITS.md', 'README.md', 'scripts/install.py',
                                 'tests/test_checker.py', 'tests/test_bundle.py',
                                 'skills/russian-text-craft/references/editorial-triage.md'):
                    self.assertIn(prefix + required, names)

    def test_current_core_references_and_checker_in_every_bundle(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform), zipfile.ZipFile(self.out / f'writing-ru-{platform}.zip') as z:
                prefix = f'writing-ru-{platform}/'
                core = prefix + 'skills/russian-text-craft/'
                text = z.read(core + 'SKILL.md').decode()
                readme = z.read(prefix + 'README.md').decode()
                for flag in ('--max-chars', '--max-words', '--min-words'):
                    self.assertIn(flag, text)
                    self.assertIn(flag, readme)
                for reference in ('editorial-triage.md', 'evaluation-protocol.md'):
                    relative = 'russian-text-craft/references/' + reference
                    self.assertEqual(z.read(prefix + 'skills/' + relative),
                                     (ROOT / 'skills/writing-ru' / relative).read_bytes())
                self.assertIn('Обязательно перед сдачей', text)
                self.assertIn('Стилевые сигналы', text)
                checker = 'russian-text-craft/scripts/ru_text_check.py'
                self.assertEqual(z.read(prefix + 'skills/' + checker),
                                 (ROOT / 'skills/writing-ru' / checker).read_bytes())
                destination = Path(self.tmp.name) / ('checker-' + platform)
                z.extractall(destination)
                command = [sys.executable, '-I', '-B', str(destination / core / 'scripts/ru_text_check.py'),
                           '-', '--genre', 'technical', '--max-words', '1', '--strict', '--json']
                result = subprocess.run(command, input='По данным отчёта всё работает.',
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                report = json.loads(result.stdout)
                self.assertTrue(report['blocking'])
                self.assertIn('mandatory', report)
                self.assertIn('style', report)

    def test_reference_whitelists_match_actual_public_references(self):
        spec = importlib.util.spec_from_file_location('installer_reference_check', ROOT / 'scripts/install.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        prefix = 'skills/writing-ru/russian-text-craft/references/'
        declared = json.loads((ROOT / 'export-files.json').read_text())
        exported = {name.removeprefix(prefix) for name in declared if name.startswith(prefix)}
        actual = {p.name for p in (ROOT / prefix).iterdir() if p.is_file()}
        self.assertEqual(exported, set(module.REFERENCES))
        self.assertEqual(exported, actual)

    def test_exports_only_declared_public_files(self):
        spec = importlib.util.spec_from_file_location('build_distribution', ROOT / 'scripts/build.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        staging = Path(self.tmp.name) / 'public-source'
        staging.mkdir()
        declared = json.loads((ROOT / 'export-files.json').read_text())
        for name in declared:
            p = staging / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, p)
        # Synthetic canaries; nothing from a user's real private directory is read.
        canary = hashlib.sha256(b'exclusion-probe').hexdigest().encode()
        for name in ('.env', 'auth.json', '.git/config', 'skills/writing-ru/russian-text-craft/references/private/profile.md',
                     'docs/token.txt', 'tests/__pycache__/cache.pyc'):
            p = staging / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(canary)
        (staging / 'unlisted-link').symlink_to(ROOT / 'README.md')
        exported = module.source_files(staging)
        self.assertEqual(set(exported), set(declared))
        self.assertFalse(any(canary in data for data in exported.values()))
        victim = staging / 'README.md'
        victim.unlink()
        victim.symlink_to(ROOT / 'README.md')
        with self.assertRaises(ValueError): module.source_files(staging)

    def test_patch_applies_to_baseline_and_reconstructs_source(self):
        baseline = '81e0618eb01f2fb8ae5802815ec1fa7ab108399f'
        staging = Path(self.tmp.name) / 'baseline'
        staging.mkdir()
        tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline], cwd=ROOT, text=True).splitlines()
        for name in tracked:
            p = staging / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(subprocess.check_output(['git', 'show', f'{baseline}:{name}'], cwd=ROOT))
        patch = self.out / 'writing-ru.patch'
        isolated_env = {'PATH': '/usr/bin:/bin', 'HOME': str(staging / 'isolated-home'),
                        'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CEILING_DIRECTORIES': str(staging.parent)}
        check = subprocess.run(['git', 'apply', '--check', str(patch)], cwd=staging, env=isolated_env, capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        applied = subprocess.run(['git', 'apply', str(patch)], cwd=staging, env=isolated_env, capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        with zipfile.ZipFile(self.out / 'writing-ru-source.zip') as z:
            for name in z.namelist():
                relative = name.removeprefix('writing-ru-source/')
                self.assertEqual((staging / relative).read_bytes(), z.read(name), relative)

    def test_extracted_bundles_run_their_own_tests(self):
        destination = Path(self.tmp.name) / 'extracted'
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                with zipfile.ZipFile(self.out / f'writing-ru-{platform}.zip') as z:
                    z.extractall(destination)  # Our builder emits validated relative paths only.
                bundle = destination / f'writing-ru-{platform}'
                result = subprocess.run([sys.executable, '-I', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                        cwd=bundle, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_source_zip_rebuilds_identical_platforms_without_git(self):
        destination = Path(self.tmp.name) / 'source-extract'
        with zipfile.ZipFile(self.out / 'writing-ru-source.zip') as z:
            z.extractall(destination)
        source = destination / 'writing-ru-source'
        result = subprocess.run([sys.executable, '-I', 'scripts/build.py', '--packages-only'],
                                cwd=source, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((source / 'dist/writing-ru.patch').exists())
        for platform in PLATFORMS:
            name = f'writing-ru-{platform}.zip'
            self.assertEqual((source / 'dist' / name).read_bytes(), (self.out / name).read_bytes())


if __name__ == '__main__':
    unittest.main()
