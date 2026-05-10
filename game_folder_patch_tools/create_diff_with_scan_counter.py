#!/usr/bin/env python3
"""
create_diff.py

Crea una cartella "diff" contenente solo i file diversi tra:
- cartella originale/pulita del gioco
- cartella modificata del gioco

La patch è binaria e sicura: non interpreta i .xxx.
Per ogni file modificato/aggiunto salva una copia compressa LZMA del file finale.
L'applicatore ricostruisce/sovrascrive i file nella cartella di destinazione.

Uso:
    python create_diff.py "C:\gioco_originale" "C:\gioco_modificato" --out diff

Solo file .xxx:
    python create_diff.py "C:\gioco_originale" "C:\gioco_modificato" --out diff --include "*.xxx"

Più pattern:
    python create_diff.py original modified --out diff --include "*.xxx" "*.ini" "*.txt"
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import lzma
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


MANIFEST_NAME = "manifest.json"
DATA_DIR_NAME = "data"
CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def rel_key(root: Path, path: Path) -> str:
    # Manifest sempre con slash '/', anche su Windows.
    return path.relative_to(root).as_posix()


def matches_include(rel: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    # Match sia sul path completo sia sul nome file.
    name = Path(rel).name
    return any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat) for pat in patterns)


def safe_patch_filename(index: int, rel: str) -> str:
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
    name = Path(rel).name.replace("/", "_").replace("\\", "_")
    return f"{index:06d}_{digest}_{name}.lzma"



def fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{n} B"


def compress_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as f_in, lzma.open(dst, "wb", preset=9 | lzma.PRESET_EXTREME) as f_out:
        shutil.copyfileobj(f_in, f_out, length=CHUNK_SIZE)


def build_patch(original_root: Path, modified_root: Path, diff_root: Path, includes: list[str] | None) -> None:
    original_root = original_root.resolve()
    modified_root = modified_root.resolve()
    diff_root = diff_root.resolve()

    if not original_root.is_dir():
        raise SystemExit(f"Cartella originale non valida: {original_root}")
    if not modified_root.is_dir():
        raise SystemExit(f"Cartella modificata non valida: {modified_root}")

    if diff_root.exists():
        shutil.rmtree(diff_root)
    data_root = diff_root / DATA_DIR_NAME
    data_root.mkdir(parents=True, exist_ok=True)

    print("Scansione cartelle...", flush=True)

    original_files = {
        rel_key(original_root, p): p
        for p in iter_files(original_root)
        if matches_include(rel_key(original_root, p), includes)
    }
    modified_files = {
        rel_key(modified_root, p): p
        for p in iter_files(modified_root)
        if matches_include(rel_key(modified_root, p), includes)
    }

    all_rels = sorted(set(original_files) | set(modified_files))
    total_found = len(all_rels)

    print(f"File totali da confrontare: {total_found}", flush=True)

    # Prima fase: trova solo i file realmente diversi.
    # Qui ora stampiamo il progresso, perché con file .xxx grandi lo SHA-256 può sembrare bloccato.
    pending_entries = []
    unchanged_count = 0

    print("Confronto file...", flush=True)

    for scan_idx, rel in enumerate(all_rels, start=1):
        original_path = original_files.get(rel)
        modified_path = modified_files.get(rel)

        size_info = ""
        if modified_path:
            size_info = f" ({fmt_bytes(modified_path.stat().st_size)})"
        elif original_path:
            size_info = f" ({fmt_bytes(original_path.stat().st_size)})"

        print(f"[confronto {scan_idx}/{total_found}] {rel}{size_info}", flush=True)

        if original_path and modified_path:
            # Ottimizzazione: se la dimensione è diversa, sappiamo già che è diverso.
            # Calcoliamo comunque gli hash perché servono al manifest/verifica.
            original_size = original_path.stat().st_size
            modified_size = modified_path.stat().st_size

            if original_size == modified_size:
                original_hash = sha256_file(original_path)
                modified_hash = sha256_file(modified_path)

                if original_hash == modified_hash:
                    unchanged_count += 1
                    continue
            else:
                original_hash = sha256_file(original_path)
                modified_hash = sha256_file(modified_path)

            pending_entries.append({
                "path": rel,
                "action": "replace",
                "original_path": original_path,
                "modified_path": modified_path,
                "base_sha256": original_hash,
                "new_sha256": modified_hash,
                "new_size": modified_path.stat().st_size,
            })

        elif modified_path and not original_path:
            modified_hash = sha256_file(modified_path)

            pending_entries.append({
                "path": rel,
                "action": "add",
                "original_path": None,
                "modified_path": modified_path,
                "base_sha256": None,
                "new_sha256": modified_hash,
                "new_size": modified_path.stat().st_size,
            })

        elif original_path and not modified_path:
            original_hash = sha256_file(original_path)

            pending_entries.append({
                "path": rel,
                "action": "delete",
                "original_path": original_path,
                "modified_path": None,
                "base_sha256": original_hash,
                "new_sha256": None,
                "new_size": 0,
            })

    total_different = len(pending_entries)
    print(f"File diversi trovati: {total_different}", flush=True)

    entries = []
    changed_count = 0
    added_count = 0
    deleted_count = 0

    # Seconda fase: genera fisicamente la cartella diff.
    for idx, pending in enumerate(pending_entries, start=1):
        rel = pending["path"]
        action = pending["action"]

        print(f"[patch {idx}/{total_different}] {action}: {rel}", flush=True)

        if action in ("replace", "add"):
            modified_path = pending["modified_path"]
            patch_name = safe_patch_filename(len(entries), rel)
            compress_file(modified_path, data_root / patch_name)
            payload = f"{DATA_DIR_NAME}/{patch_name}"
        else:
            payload = None

        entries.append({
            "path": rel,
            "action": action,
            "base_sha256": pending["base_sha256"],
            "new_sha256": pending["new_sha256"],
            "new_size": pending["new_size"],
            "payload": payload,
        })

        if action == "replace":
            changed_count += 1
        elif action == "add":
            added_count += 1
        elif action == "delete":
            deleted_count += 1

    manifest = {
        "format": "simple-game-folder-patch-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "notes": "Patch binaria: sovrascrive i file modificati senza interpretare il formato interno.",
        "include_patterns": includes or ["*"],
        "counts": {
            "changed": changed_count,
            "added": added_count,
            "deleted": deleted_count,
            "unchanged": unchanged_count,
            "total_patch_entries": len(entries),
        },
        "entries": entries,
    }

    with (diff_root / MANIFEST_NAME).open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Patch creata in: {diff_root}", flush=True)
    print(f"Modificati: {changed_count}", flush=True)
    print(f"Aggiunti:   {added_count}", flush=True)
    print(f"Eliminati:  {deleted_count}", flush=True)
    print(f"Invariati:  {unchanged_count}", flush=True)
    print(f"Voci patch: {len(entries)}", flush=True)



def main() -> None:
    parser = argparse.ArgumentParser(description="Crea una patch binaria tra due cartelle di gioco.")
    parser.add_argument("original", help="Cartella originale/pulita del gioco")
    parser.add_argument("modified", help="Cartella modificata del gioco")
    parser.add_argument("--out", default="diff", help="Cartella di output della patch, default: diff")
    parser.add_argument(
        "--include",
        nargs="*",
        default=None,
        help='Pattern da includere, es. --include "*.xxx". Se omesso include tutti i file.',
    )
    args = parser.parse_args()

    build_patch(
        original_root=Path(args.original),
        modified_root=Path(args.modified),
        diff_root=Path(args.out),
        includes=args.include,
    )


if __name__ == "__main__":
    main()
