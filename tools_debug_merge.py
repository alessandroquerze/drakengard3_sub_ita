#!/usr/bin/env python3
from pathlib import Path

SPLIT_IT_DIR = Path('split_it')
SPLIT_EN_DIR = Path('split_en')
DEBUG_DIR = Path('split_debug')


def build_debug_file(it_path: Path, en_path: Path, out_path: Path) -> None:
    it_lines = it_path.read_text(encoding='utf-8').splitlines()
    en_lines = en_path.read_text(encoding='utf-8').splitlines()

    debug_lines = []
    max_len = max(len(it_lines), len(en_lines))
    for idx in range(max_len):
        debug_lines.append(it_lines[idx] if idx < len(it_lines) else '')
        debug_lines.append(en_lines[idx] if idx < len(en_lines) else '')

    out_path.write_text('\n'.join(debug_lines) + '\n', encoding='utf-8')


def main() -> None:
    DEBUG_DIR.mkdir(exist_ok=True)

    for it_file in sorted(SPLIT_IT_DIR.glob('Sqex03DataMessage_part_*_it.txt')):
        en_name = it_file.name.replace('_it.txt', '.txt')
        en_file = SPLIT_EN_DIR / en_name
        out_file = DEBUG_DIR / it_file.name.replace('_it.txt', '_debug.txt')
        if en_file.exists():
            build_debug_file(it_file, en_file, out_file)

    print('Done: debug merge files created in split_debug/.')


if __name__ == '__main__':
    main()
