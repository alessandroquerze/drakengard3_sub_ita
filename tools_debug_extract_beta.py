#!/usr/bin/env python3
from pathlib import Path

DEBUG_DIR = Path('split_debug')
OUT_DIR = Path('split_beta')


def unmd_code_line(line: str) -> str:
    """
    Rimuove il wrapping Markdown prodotto da md_code_line().

    Casi gestiti:
    - `testo`
    - `` testo ``
    - linee non wrappate, lasciate intatte
    """
    line = line.rstrip('\n\r')

    # Caso con doppi backtick: `` testo ``
    if line.startswith('`` ') and line.endswith(' ``'):
        return line[3:-3]

    # Caso normale: `testo`
    if len(line) >= 2 and line.startswith('`') and line.endswith('`'):
        return line[1:-1]

    return line


def extract_it_from_debug(debug_path: Path, out_path: Path) -> int:
    lines = debug_path.read_text(encoding='utf-8').splitlines()

    extracted = []
    idx = 0

    while idx < len(lines):
        # Il formato è:
        # 0: riga IT tra backtick
        # 1: riga EN normale
        # 2: riga vuota
        it_line = lines[idx]
        extracted.append(unmd_code_line(it_line))

        # Avanza alla prossima coppia.
        # Nel file generato dal tuo tool ci sono blocchi da 3 righe.
        # Se manca la riga vuota finale, funziona comunque.
        idx += 3

    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text('\n'.join(extracted) + '\n', encoding='utf-8')
    return len(extracted)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    debug_files = sorted(DEBUG_DIR.glob('Sqex03DataMessage_part_*_debug.md'))

    created = 0
    total_lines = 0

    for debug_file in debug_files:
        out_name = debug_file.name.replace('_debug.md', '.txt')
        out_file = OUT_DIR / out_name

        count = extract_it_from_debug(debug_file, out_file)
        total_lines += count
        created += 1

        print(f'Created: {out_file} ({count} lines)')

    print(f'Done: {created} files created in {OUT_DIR}. Extracted lines: {total_lines}.')


if __name__ == '__main__':
    main()
