#!/usr/bin/env python3
from pathlib import Path
import argparse
import shutil

DEFAULT_INPUT = Path('Sqex03DataMessage.txt')
DEFAULT_OUT_DIR = Path('split_en')
DEFAULT_PARTS = 160
DEFAULT_PREFIX = 'Sqex03DataMessage_part_'


def read_lines_preserve_newlines(path: Path) -> list[str]:
    """Read text as lines while preserving original line endings."""
    return path.read_text(encoding='utf-8').splitlines(keepends=True)


def balanced_ranges(total: int, parts: int) -> list[tuple[int, int]]:
    """
    Return contiguous [start, end) ranges distributed as evenly as possible.

    Example: 16878 lines / 160 parts => first 78 files have 106 lines,
    remaining 82 files have 105 lines.
    """
    if parts <= 0:
        raise ValueError('parts must be greater than 0')
    if total == 0:
        return [(0, 0) for _ in range(parts)]

    base, extra = divmod(total, parts)
    ranges: list[tuple[int, int]] = []
    start = 0
    for i in range(parts):
        size = base + (1 if i < extra else 0)
        end = start + size
        ranges.append((start, end))
        start = end
    return ranges


def split_file(
    input_path: Path,
    out_dir: Path,
    parts: int,
    prefix: str,
    suffix: str,
    clean: bool,
) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f'Input file not found: {input_path}')

    lines = read_lines_preserve_newlines(input_path)

    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pad = max(3, len(str(parts)))
    ranges = balanced_ranges(len(lines), parts)

    for index, (start, end) in enumerate(ranges, start=1):
        part_name = f'{prefix}{index:0{pad}d}{suffix}'
        part_path = out_dir / part_name
        part_path.write_text(''.join(lines[start:end]), encoding='utf-8')

    # Safety check: concatenating the split files in sorted order must recreate the input exactly.
    rebuilt = ''.join((out_dir / f'{prefix}{i:0{pad}d}{suffix}').read_text(encoding='utf-8') for i in range(1, parts + 1))
    original = input_path.read_text(encoding='utf-8')
    if rebuilt != original:
        raise RuntimeError('Verification failed: split files do not reconstruct the original file exactly.')

    min_lines = min(end - start for start, end in ranges)
    max_lines = max(end - start for start, end in ranges)
    print(f'Done: created {parts} files in {out_dir}/')
    print(f'Total lines: {len(lines)}')
    print(f'Lines per file: {min_lines}-{max_lines}')
    print('Verification: OK, sorted concatenation recreates the original file exactly.')
    print('For translated files, save them as split_it/Sqex03DataMessage_part_001_it.txt, etc.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Split Sqex03DataMessage.txt into numbered parts compatible with tools_pipeline.py.'
    )
    parser.add_argument('-i', '--input', type=Path, default=DEFAULT_INPUT, help='Input .txt file')
    parser.add_argument('-o', '--out-dir', type=Path, default=DEFAULT_OUT_DIR, help='Output directory for split English files')
    parser.add_argument('-n', '--parts', type=int, default=DEFAULT_PARTS, help='Number of parts to create')
    parser.add_argument('--prefix', default=DEFAULT_PREFIX, help='Output filename prefix')
    parser.add_argument('--suffix', default='.txt', help='Output filename suffix')
    parser.add_argument('--no-clean', action='store_true', help='Do not delete the output directory before writing')
    args = parser.parse_args()

    split_file(
        input_path=args.input,
        out_dir=args.out_dir,
        parts=args.parts,
        prefix=args.prefix,
        suffix=args.suffix,
        clean=not args.no_clean,
    )


if __name__ == '__main__':
    main()
