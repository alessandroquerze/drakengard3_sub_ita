#!/usr/bin/env python3
from pathlib import Path

SPLIT_IT_DIR = Path('split_beta')
MERGED_IT = Path('Sqex03DataMessage_it.txt')


def merge_translated_italian() -> None:
    merged = []
    for file in sorted(SPLIT_IT_DIR.glob('Sqex03DataMessage_part_*.txt')):
        merged.append(file.read_text(encoding='utf-8'))
    MERGED_IT.write_text(''.join(merged), encoding='utf-8')


def main() -> None:
    merge_translated_italian()
    print('Done: merged italian split files.')


if __name__ == '__main__':
    main()
