#!/usr/bin/env python3
from pathlib import Path

SPLIT_IT_DIR = Path('split_it')
SPLIT_EN_DIR = Path('split_en')
DEBUG_DIR = Path('split_debug')


def md_code_line(text: str) -> str:
    """
    Evidenzia una riga Markdown usando `.
    Se la riga contiene già backtick, usa un blocco inline più sicuro.
    """
    if '`' not in text:
        return f'`{text}`'

    # Markdown inline code con doppi backtick se il testo contiene `
    return f'`` {text} ``'


def build_debug_file(it_path: Path, en_path: Path, out_path: Path) -> None:
    it_lines = it_path.read_text(encoding='utf-8').splitlines()
    en_lines = en_path.read_text(encoding='utf-8').splitlines()

    debug_lines = []
    max_len = max(len(it_lines), len(en_lines))

    for idx in range(max_len):
        # Riga italiana/tradotta evidenziata con `
        it_line = it_lines[idx] if idx < len(it_lines) else ''
        debug_lines.append(md_code_line(it_line))

        # Riga inglese originale normale
        en_line = en_lines[idx] if idx < len(en_lines) else ''
        debug_lines.append(en_line)

        # Riga vuota tra coppie, opzionale ma rende l'MD più leggibile
        debug_lines.append('')

    out_path.write_text('\n'.join(debug_lines) + '\n', encoding='utf-8')
def main() -> None:
    #print("CIAO")
    DEBUG_DIR.mkdir(exist_ok=True)

    it_files = sorted(SPLIT_IT_DIR.glob('Sqex03DataMessage_part_*_it.txt'))

    created = 0
    skipped_existing = 0
    skipped_missing_en = 0

    for it_file in it_files:
        en_name = it_file.name.replace('_it.txt', '.txt')
        en_file = SPLIT_EN_DIR / en_name

        out_file = DEBUG_DIR / it_file.name.replace('_it.txt', '_debug.md')

        if out_file.exists():
            print(f'Skipped: debug file already exists: {out_file.name}')
            skipped_existing += 1
            continue

        if not en_file.exists():
            print(f'Skipped: missing EN file for {it_file.name}')
            skipped_missing_en += 1
            continue

        build_debug_file(it_file, en_file, out_file)
        created += 1

    print(
        f'Done: {len(it_files)} IT files found. '
        f'Created: {created}. '
        f'Skipped existing: {skipped_existing}. '
        f'Skipped missing EN: {skipped_missing_en}.'
    )
if __name__ == '__main__':
    main()