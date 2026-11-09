#!/usr/bin/env python3
"""Build five portable skills-directory bundles and public source/patch. Stdlib only."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '81e0618eb01f2fb8ae5802815ec1fa7ab108399f'
FAMILY = 'skills/writing-ru/'
_spec = importlib.util.spec_from_file_location('portable_installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(installer)


def source_files(root: Path) -> dict[str, bytes]:
    root = installer.safe_path(root)
    declared = json.loads(installer.regular_bytes(root / 'export-files.json'))
    if not isinstance(declared, list) or len(set(declared)) != len(declared):
        raise ValueError('invalid export whitelist')
    result = {}
    for name in sorted(declared):
        if not isinstance(name, str):
            raise ValueError('non-string export path')
        path = PurePosixPath(name)
        if (path.is_absolute() or str(path) != name or '\\' in name
                or any(part in {'.git', 'private', 'dist', '__pycache__', '.env', 'auth.json'} for part in path.parts)
                or '..' in path.parts
                or not (name in {'.gitignore', 'LICENSE', 'CREDITS.md', 'README.md', 'CHANGELOG.md', 'export-files.json'}
                        or name.startswith(('skills/writing-ru/', 'scripts/', 'tests/', 'examples/', 'docs/', 'evidence/')))
                or path.suffix not in {'.md', '.py', '.txt', '.json', ''} and name != '.gitignore'):
            raise ValueError(f'unsafe export path: {name}')
        result[name] = installer.regular_bytes(root / name)
    if 'export-files.json' not in result:
        raise ValueError('whitelist must export itself')
    return result


def zip_bytes(files: dict[str, bytes], prefix: str = '') -> bytes:
    stream = io.BytesIO()
    # Stored entries avoid zlib-version differences; fixed order/time/mode.
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(prefix + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            z.writestr(info, data)
    return stream.getvalue()


def adapt_skill(data: bytes, name: str, platform: dict) -> bytes:
    text = data.decode('utf-8')
    if not text.startswith('---\n'):
        raise ValueError(f'missing frontmatter: {name}')
    fm, body = text[4:].split('\n---\n', 1)
    description = re.search(r'^description: (.+)$', fm, re.M)
    declared_name = re.search(r'^name: (.+)$', fm, re.M)
    if not description or not declared_name or declared_name[1] != name:
        raise ValueError(f'invalid skill metadata: {name}')
    desc = json.loads(description[1])
    header = ('---\nname: ' + name + '\ndescription: ' + json.dumps(desc, ensure_ascii=False)
              + '\nlicense: MIT\ncompatibility: "Python 3.10+ for optional local checker; file reading and shell access required."\n---\n')
    intro = platform['reading'] + '\n\n'
    if name != 'russian-text-craft':
        intro += 'До применения жанра прочитай [ядро](../russian-text-craft/SKILL.md) полностью; правила сохранности материала и режим правки действуют вместе с этим жанром.\n\n'
    else:
        old = '`terminal(command="python3 -I <skill_dir>/scripts/ru_text_check.py <файл> --genre <жанр>")`. `<skill_dir>` — поле `skill_dir` из ответа `skill_view`.'
        command = ('`python3 -I "' + platform['core_dir'] + '/scripts/ru_text_check.py" "<файл>" --genre <жанр>`. '
                   'Подставь реальный путь и жанр; угловые скобки — обозначения, не готовая команда. '
                   'Нет Python или разрешённого shell — сообщи, что проверка не выполнена.')
        if body.count(old) != 1:
            raise ValueError('canonical checker invocation changed; adapt explicitly')
        body = body.replace(old, command)
        body = body.replace('(`docx`/`mdtoword` для Word)', '(сборка Word — только доступным и разрешённым средством окружения)')
    if re.search(r'skill_view|terminal\(command=|<skill_dir>', body):
        raise ValueError('unadapted runtime invocation')
    return (header + '\n' + intro + body.lstrip()).encode()


def bundle_readme(platform: dict) -> bytes:
    title, target = platform['title'], platform['project_root']
    return f'''# writing-ru — {title}

Ядро и 18 жанров для написания и редактуры русского текста; локальный checker не определяет авторство.
Это portable skills-directory bundle, не plugin и не manifest. Модель/настройки/профили не меняются.

## Установка и проверка

Распакуйте ZIP в новую папку и просмотрите файлы. Команды ниже — из корня распакованного пакета, Python 3.10+.
`<проект>` замените реальным путём; `{target}` должен отсутствовать, включая пустой каталог.
Сначала dry-run (ничего не создаёт), затем только по вашему решению apply:

```bash
python3 -I scripts/install.py install --source skills --target "<проект>/{target}"
python3 -I scripts/install.py install --source skills --target "<проект>/{target}" --apply
python3 -I scripts/install.py verify --source skills --target "<проект>/{target}"
python3 -I -m unittest discover -s tests -v
```

Ожидается 19 файлов SKILL.md в target и успешная сверка байтов. Это не доказывает runtime discovery:
откройте новую сессию {title}, найдите `russian-text-craft` и жанр, проверьте пути победивших версий.
Явный вызов ядра: `{platform['invoke']}`. Попросите также прочитать полный `ru-business-correspondence/SKILL.md`;
одна slash-команда не означает загрузку всего семейства. Для другого жанра замените имя.

## Использование

Попросите: «Вычитай письмо, сохрани даты, суммы, цитаты и ссылки; сначала прочитай ядро и жанр деловой переписки».
{platform['reading']}
References и scripts разрешаются от каталога ядра; tools/permissions/sandbox — возможности runtime, не этого пакета.
Без shell/Python доступно ручное чтение, но нельзя заявлять запуск checker.

Проверка из этой папки:

```bash
python3 -I skills/russian-text-craft/scripts/ru_text_check.py tests/fixtures/positive.txt --genre technical --strict --json
```

Ожидаемый код **1**: синтетический пример содержит красные сигналы; это не ошибка установки.

## Обновление и удаление

Silent overwrite отсутствует: существующий target всегда вызывает отказ. Для обновления установите новый пакет в
новую staging-папку, проверьте его, сохраните старый target в backup вне discovery root, затем перенесите новую
проверенную папку на его место. Свои правки переносите вручную, с повторной проверкой; автоматического merge нет.
При уже существующем общем skills root не переносите чужие навыки автоматически: используйте отдельный тестовый
проект/документированный дополнительный discovery root платформы либо ручную установку после review коллизий.

Безопасное удаление требует **этой же версии исходного пакета**:

```bash
python3 -I scripts/install.py remove --source skills --target "<проект>/{target}"
python3 -I scripts/install.py remove --source skills --target "<проект>/{target}" --apply
```

При изменённых/пропавших/чужих файлах или symlink — отказ до удаления. Сохраните каталог вручную вне discovery,
если он содержит локальные правки. Installer не удаляет родительские каталоги и не трогает чужие профили.

Подробнее: [installer и privacy](docs/install.md), [официальные контракты](docs/platforms.md),
[аудит](docs/audit.md), [проверки и ограничения](docs/verification.md), [MIT](LICENSE), [credits](CREDITS.md).
'''.encode()


def platform_files(source: dict[str, bytes], platform: dict) -> dict[str, bytes]:
    result = {}
    for relative in installer.PUBLIC_FILES:
        data = source[FAMILY + relative]
        if relative.endswith('/SKILL.md'):
            data = adapt_skill(data, relative.split('/')[0], platform)
        result['skills/' + relative] = data
    for name in ('LICENSE', 'CREDITS.md', 'scripts/install.py', 'tests/test_bundle.py',
                 'tests/test_checker.py', 'tests/fixtures/positive.txt', 'tests/fixtures/false-positive.md',
                 'evidence/baseline.json', 'evidence/runtime.json',
                 'docs/install.md', 'docs/platforms.md', 'docs/audit.md', 'docs/verification.md'):
        result[name] = source[name]
    result['README.md'] = bundle_readme(platform)
    return result


def baseline_patch(source: dict[str, bytes], root: Path) -> bytes:
    # Reads only whitelisted public baseline blobs; never indexes unknown files.
    exists = subprocess.run(['git', 'cat-file', '-e', BASELINE + '^{commit}'], cwd=root, capture_output=True)
    if exists.returncode:
        raise ValueError('baseline commit unavailable; provide original Git checkout for patch build')
    entries = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE], cwd=root, text=True).splitlines()
    tracked = set(entries)
    patches = []
    for name, data in sorted(source.items()):
        before = subprocess.check_output(['git', 'show', BASELINE + ':' + name], cwd=root) if name in tracked else b''
        if before == data:
            continue
        header = f'diff --git a/{name} b/{name}\n'
        if name not in tracked:
            header += 'new file mode 100644\n'
        patches.append(header + ''.join(difflib.unified_diff(
            before.decode().splitlines(keepends=True), data.decode().splitlines(keepends=True),
            fromfile='a/' + name if name in tracked else '/dev/null', tofile='b/' + name)))
    return ''.join(patches).encode()


def build(output: Path, replace: bool = False, packages_only: bool = False) -> None:
    source = source_files(ROOT)
    output = installer.safe_path(output)
    if ROOT not in output.parents or output.relative_to(ROOT).parts[0] in {'skills', 'scripts', 'tests', 'docs', 'evidence', 'examples'}:
        raise ValueError('output must be a dedicated directory inside this repository, not a source directory')
    platforms = json.loads(source['scripts/platforms.json'])
    artifacts = {}
    for key, platform in platforms.items():
        artifacts[f'writing-ru-{key}.zip'] = zip_bytes(platform_files(source, platform), f'writing-ru-{key}/')
    artifacts['writing-ru-source.zip'] = zip_bytes(source, 'writing-ru-source/')
    if not packages_only:
        if not (ROOT / '.git').exists():
            raise ValueError('full delivery requires baseline Git checkout; use --packages-only without Git')
        artifacts['writing-ru.patch'] = baseline_patch(source, ROOT)
    inner_sums = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data in sorted(artifacts.items()))
    artifacts['writing-ru-all-in-one.zip'] = zip_bytes({**artifacts, 'SHA256SUMS': inner_sums.encode()})
    artifacts['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data in sorted(artifacts.items())).encode()
    # Preflight every destination, even when --replace is explicit.
    for name, data in artifacts.items():
        target = installer.safe_path(output / name)
        if target.exists() and (not replace or installer.regular_bytes(target) == data):
            if installer.regular_bytes(target) != data:
                raise ValueError(f'output exists: {name}; choose new --output or explicit --replace')
        elif target.exists() and not target.is_file():
            raise ValueError('output is not a regular file')
    output.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        path = output / name
        if path.exists() and installer.regular_bytes(path) == data:
            continue
        mode = 'wb' if replace else 'xb'
        with path.open(mode) as stream:
            stream.write(data)
    print(f'Built {len(platforms)} platform ZIPs, source, '
          f'{"no baseline patch, " if packages_only else "patch, "}all-in-one and SHA256SUMS in {output}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--replace', action='store_true', help='explicitly replace generated artifacts only')
    parser.add_argument('--packages-only', action='store_true', help='build portable bundles/source without Git baseline patch')
    args = parser.parse_args()
    try:
        build(args.output, args.replace, args.packages_only)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f'Build refused: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
