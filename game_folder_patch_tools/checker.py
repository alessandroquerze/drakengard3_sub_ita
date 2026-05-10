#!/usr/bin/env python3

from pathlib import Path
import filecmp
import hashlib
import sys


def file_hash(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()

    with path.open('rb') as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)

    return h.hexdigest()


def compare_dirs(dir1: Path, dir2: Path) -> None:
    files1 = {p.relative_to(dir1) for p in dir1.rglob('*') if p.is_file()}
    files2 = {p.relative_to(dir2) for p in dir2.rglob('*') if p.is_file()}

    only_in_dir1 = sorted(files1 - files2)
    only_in_dir2 = sorted(files2 - files1)
    common_files = sorted(files1 & files2)

    print('==============================')
    print('FILE SOLO NELLA PRIMA CARTELLA')
    print('==============================')

    for f in only_in_dir1:
        print(f)

    print()
    print('==============================')
    print('FILE SOLO NELLA SECONDA CARTELLA')
    print('==============================')

    for f in only_in_dir2:
        print(f)

    print()
    print('==============================')
    print('FILE DIFFERENTI')
    print('==============================')

    different = []

    for rel_path in common_files:
        file1 = dir1 / rel_path
        file2 = dir2 / rel_path

        # confronto veloce dimensione
        if file1.stat().st_size != file2.stat().st_size:
            different.append(rel_path)
            continue

        # confronto hash contenuto
        if file_hash(file1) != file_hash(file2):
            different.append(rel_path)

    for f in different:
        print(f)

    print()
    print('==============================')
    print('FILE IDENTICI')
    print('==============================')

    identical = sorted(set(common_files) - set(different))

    for f in identical:
        print(f)

    print()
    print('Totale identici   :', len(identical))
    print('Totale differenti :', len(different))
    print('Solo cartella 1   :', len(only_in_dir1))
    print('Solo cartella 2   :', len(only_in_dir2))


def main():
    if len(sys.argv) != 3:
        print('Uso:')
        print('python diff_dirs.py cartella1 cartella2')
        sys.exit(1)

    dir1 = Path(sys.argv[1])
    dir2 = Path(sys.argv[2])

    if not dir1.is_dir():
        print(f'Errore: {dir1} non è una cartella valida')
        sys.exit(1)

    if not dir2.is_dir():
        print(f'Errore: {dir2} non è una cartella valida')
        sys.exit(1)

    compare_dirs(dir1, dir2)


if __name__ == '__main__':
    main()