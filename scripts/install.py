#!/usr/bin/env python3
"""Explicit source/target installer. Stdlib, no profile discovery, dry-run default.

Trust boundary: local, non-concurrently-mutated directories. Not a sandbox or
an authorization mechanism against a hostile process running as the same user.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

SKILLS = (
    'russian-text-craft', 'ru-academic-article', 'ru-agent-report',
    'ru-analytical-note', 'ru-business-correspondence', 'ru-expert-commentary',
    'ru-grant-proposal', 'ru-knowledge-note', 'ru-official-documents',
    'ru-popular-explainer', 'ru-presentation-text', 'ru-review-and-feedback',
    'ru-short-copy', 'ru-speech-and-scenario', 'ru-teaching-materials',
    'ru-technical-docs', 'ru-telegram-post', 'ru-transcript-editing', 'ru-translation',
)
REFERENCES = ('author-voice.md', 'editing-modes.md', 'ru-ai-patterns.md', 'editorial-triage.md', 'evaluation-protocol.md',
              'source-verification.md')
PUBLIC_FILES = tuple(sorted(
    [f'{name}/SKILL.md' for name in SKILLS]
    + [f'russian-text-craft/references/{name}' for name in REFERENCES]
    + ['russian-text-craft/scripts/ru_text_check.py']))
RECEIPT = '.writing-ru-receipt.json'


def safe_path(value: str | Path) -> Path:
    """Reject lexical traversal before normalization and every symlink ancestor."""
    p = Path(value)
    if '..' in p.parts:
        raise ValueError('path traversal: ..')
    p = Path(os.path.abspath(p))
    for part in (p, *p.parents):
        if part.is_symlink():
            raise ValueError(f'symlink: {part.name}')
    return p


def regular_bytes(path: Path) -> bytes:
    safe_path(path)
    # O_NONBLOCK avoids blocking on a FIFO; fstat rejects every special file.
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f'not a regular file: {path.name}')
        return stream.read()


def directories(files) -> set[str]:
    return {str(p) for name in files for p in Path(name).parents if str(p) != '.'}


def inventory(root: Path, *, allow_cache: bool = False) -> tuple[set[str], set[str]]:
    safe_path(root)
    if not root.is_dir():
        raise ValueError('directory required')
    files, dirs = set(), set()

    def walk(folder):
        for p in sorted(folder.iterdir()):
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                raise ValueError(f'symlink: {rel}')
            mode = p.lstat().st_mode
            if allow_cache and p.name == '__pycache__' and stat.S_ISDIR(mode):
                continue  # Never traverse or export interpreter caches.
            if stat.S_ISDIR(mode):
                dirs.add(rel)
                walk(p)
            elif stat.S_ISREG(mode):
                files.add(rel)
            else:
                raise ValueError(f'not a regular file: {rel}')
    walk(root)
    return files, dirs


def source_payload(source: Path) -> dict[str, bytes]:
    files, dirs = inventory(source, allow_cache=True)
    if files != set(PUBLIC_FILES) or dirs != directories(PUBLIC_FILES):
        raise ValueError('source differs from public whitelist (extra/missing files or directories)')
    return {name: regular_bytes(source / name) for name in PUBLIC_FILES}


def receipt(payload: dict[str, bytes]) -> bytes:
    return (json.dumps({'format': 1, 'files': {name: hashlib.sha256(data).hexdigest()
                                            for name, data in sorted(payload.items())}},
                       sort_keys=True, indent=2) + '\n').encode()


def verify_target(target: Path, payload: dict[str, bytes]) -> None:
    expected = {**payload, RECEIPT: receipt(payload)}
    files, dirs = inventory(target)
    if files != set(expected) or dirs != directories(expected):
        raise ValueError('target inventory changed: extra/missing files or directories')
    for name, data in expected.items():
        if regular_bytes(target / name) != data:
            raise ValueError(f'target modified: {name}')


def execute(action: str, source: Path, target: Path, apply: bool = False) -> None:
    source, target = safe_path(source), safe_path(target)
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('source/target overlap')
    if target == Path(target.anchor):
        raise ValueError('filesystem root is not a target')
    payload = source_payload(source)
    if action == 'install':
        if target.exists():
            raise ValueError('target already exists; use a new directory, no overwrite')
        if not apply:
            print(f'DRY-RUN install {len(payload)} files -> {target}')
            return
        # Exclusive creation; failures are visible, never remove a partial install
        # automatically (a user may have written into it in the meantime).
        target.parent.mkdir(parents=True, exist_ok=True)
        safe_path(target)
        target.mkdir()
        for name in sorted(directories(payload), key=lambda x: (x.count('/'), x)):
            (target / name).mkdir()
        for name, data in {**payload, RECEIPT: receipt(payload)}.items():
            with (target / name).open('xb') as stream:
                stream.write(data)
        verify_target(target, payload)
        print(f'INSTALLED {len(payload)} files -> {target}')
    else:
        verify_target(target, payload)  # Complete preflight before any deletion.
        if action == 'verify':
            print(f'VERIFIED {len(payload)} files')
        elif not apply:
            print(f'DRY-RUN remove {len(payload)} files -> {target}')
        else:
            for name in [*payload, RECEIPT]:
                (target / name).unlink()
            for name in sorted(directories(payload), key=lambda x: (-x.count('/'), x)):
                (target / name).rmdir()
            target.rmdir()  # Parent directories are never removed.
            print('REMOVED unchanged installation')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'verify', 'remove'))
    parser.add_argument('--source', type=Path, required=True, help='public skills directory, not a ZIP')
    parser.add_argument('--target', type=Path, required=True, help='exact new skills root; no default profile')
    parser.add_argument('--apply', action='store_true', help='explicitly permit install/remove')
    args = parser.parse_args()
    try:
        execute(args.action, args.source, args.target, args.apply)
    except (OSError, ValueError) as exc:
        print(f'Refused: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
