#!/usr/bin/env python3
"""
patch_app_gui.py

Applicatore patch con GUI semplice.

Comportamento importante:
- Prima di applicare la patch, controlla che i file "replace"/"delete" esistano.
- Se l'utente seleziona la cartella sbagliata, NON crea PS3_GAME/USRDIR/... da zero.
- I file mancanti causano errore prima di qualunque scrittura.
- I file "add" possono invece essere creati, perché sono nuovi per definizione.

Build EXE standalone Windows:
    pip install pyinstaller
    pyinstaller --onefile --windowed --name PatchGame patch_app_gui.py

Dopo la build, copia la cartella "diff" accanto all'exe:
    dist/PatchGame.exe
    dist/diff/
"""

from __future__ import annotations

import hashlib
import json
import lzma
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


MANIFEST_NAME = "manifest.json"
CHUNK_SIZE = 1024 * 1024
MAX_MISSING_PREVIEW = 20


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_manifest(diff_root: Path) -> dict:
    manifest_path = diff_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest non trovato: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    if manifest.get("format") != "simple-game-folder-patch-v1":
        raise ValueError("Formato patch non supportato o manifest non valido.")

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Manifest non valido: campo 'entries' mancante o errato.")

    return manifest


def safe_target_path(game_root: Path, rel: str) -> Path:
    root = game_root.resolve()
    target = (root / rel).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"Percorso non sicuro nel manifest: {rel}")

    return target


def decompress_payload(payload_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_path.with_suffix(target_path.suffix + ".patch_tmp")

    with lzma.open(payload_path, "rb") as f_in, tmp.open("wb") as f_out:
        shutil.copyfileobj(f_in, f_out, length=CHUNK_SIZE)

    tmp.replace(target_path)


def validate_game_folder(game_root: Path, manifest: dict) -> None:
    """
    Controlla che la cartella scelta sembri davvero la root corretta del gioco.

    Regola:
    - per action replace/delete, il file target deve già esistere;
    - per action add, può non esistere.
    """
    if not game_root.is_dir():
        raise FileNotFoundError("La cartella gioco selezionata non esiste.")

    entries = manifest.get("entries", [])
    missing = []

    for entry in entries:
        action = entry.get("action")
        rel = entry.get("path")

        if not rel:
            raise ValueError("Manifest non valido: voce senza percorso.")

        if action in ("replace", "delete"):
            target = safe_target_path(game_root, rel)
            if not target.is_file():
                missing.append(rel)

    if missing:
        preview = "\n".join(f"- {p}" for p in missing[:MAX_MISSING_PREVIEW])
        extra = ""
        if len(missing) > MAX_MISSING_PREVIEW:
            extra = f"\n...e altri {len(missing) - MAX_MISSING_PREVIEW} file mancanti."

        raise FileNotFoundError(
            "La cartella selezionata non sembra essere la root corretta del gioco.\n\n"
            "Alcuni file da sostituire non sono stati trovati:\n"
            f"{preview}"
            f"{extra}\n\n"
            "Se il manifest contiene percorsi tipo PS3_GAME/USRDIR/..., devi selezionare "
            "la cartella che contiene direttamente PS3_GAME, non PS3_GAME stessa e non una cartella vuota."
        )


def validate_payloads(diff_root: Path, manifest: dict) -> None:
    missing_payloads = []

    for entry in manifest.get("entries", []):
        payload = entry.get("payload")
        action = entry.get("action")

        if action in ("replace", "add"):
            if not payload:
                missing_payloads.append(f"{entry.get('path')} -> payload mancante nel manifest")
                continue

            payload_path = diff_root / payload
            if not payload_path.is_file():
                missing_payloads.append(str(payload_path))

    if missing_payloads:
        preview = "\n".join(f"- {p}" for p in missing_payloads[:MAX_MISSING_PREVIEW])
        extra = ""
        if len(missing_payloads) > MAX_MISSING_PREVIEW:
            extra = f"\n...e altri {len(missing_payloads) - MAX_MISSING_PREVIEW} payload mancanti."

        raise FileNotFoundError(
            "La cartella diff è incompleta o corrotta.\n\n"
            "Payload mancanti:\n"
            f"{preview}"
            f"{extra}"
        )


def apply_patch(
    game_root: Path,
    diff_root: Path,
    *,
    verify_base_hash: bool = True,
    force_if_mismatch: bool = False,
    allow_missing_replace_targets: bool = False,
    log_callback=None,
    progress_callback=None,
) -> dict:
    manifest = load_manifest(diff_root)
    validate_payloads(diff_root, manifest)

    # Blocco anti-cartella-sbagliata.
    # Di default è False: non permette di creare da zero PS3_GAME/USRDIR/... per file replace/delete.
    if not allow_missing_replace_targets:
        validate_game_folder(game_root, manifest)

    entries = manifest.get("entries", [])

    stats = {
        "replaced": 0,
        "added": 0,
        "deleted": 0,
        "skipped": 0,
        "warnings": 0,
    }

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    total = max(len(entries), 1)

    for i, entry in enumerate(entries, start=1):
        rel = entry["path"]
        action = entry["action"]
        target = safe_target_path(game_root, rel)
        base_hash = entry.get("base_sha256")
        expected_new_hash = entry.get("new_sha256")

        if progress_callback:
            progress_callback(i, total)

        log(f"[{i}/{total}] {action}: {rel}")

        if action in ("replace", "delete"):
            if not target.is_file():
                raise FileNotFoundError(
                    f"File target mancante: {rel}\n\n"
                    "Patch interrotta per evitare di creare una struttura di cartelle nuova "
                    "su una destinazione sbagliata."
                )

        if action in ("replace", "delete") and verify_base_hash and base_hash:
            current_hash = sha256_file(target)
            if current_hash != base_hash:
                msg = (
                    f"  ATTENZIONE: hash base diverso per {rel}. "
                    f"Il file di destinazione non coincide con la versione attesa."
                )
                log(msg)
                stats["warnings"] += 1
                if not force_if_mismatch:
                    log("  Saltato. Attiva 'Forza sovrascrittura' per applicare comunque.")
                    stats["skipped"] += 1
                    continue

        if action == "replace":
            payload = diff_root / entry["payload"]
            decompress_payload(payload, target)

            if expected_new_hash and sha256_file(target) != expected_new_hash:
                raise RuntimeError(f"Verifica hash fallita dopo la scrittura: {rel}")

            stats["replaced"] += 1
            log("  OK sostituito.")

        elif action == "add":
            payload = diff_root / entry["payload"]

            # Per gli "add" è normale creare sottocartelle nuove.
            decompress_payload(payload, target)

            if expected_new_hash and sha256_file(target) != expected_new_hash:
                raise RuntimeError(f"Verifica hash fallita dopo la scrittura: {rel}")

            stats["added"] += 1
            log("  OK aggiunto.")

        elif action == "delete":
            target.unlink()
            stats["deleted"] += 1
            log("  OK eliminato.")

        else:
            raise ValueError(f"Azione sconosciuta nel manifest: {action}")

    return stats


class PatchGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Applicatore patch gioco")
        self.geometry("820x540")
        self.minsize(720, 440)

        self.game_path_var = tk.StringVar()
        self.force_var = tk.BooleanVar(value=False)
        self.verify_var = tk.BooleanVar(value=True)

        self.diff_root = app_dir() / "diff"

        self._build_ui()
        self._append_log(f"Cartella patch attesa: {self.diff_root}")
        if not (self.diff_root / MANIFEST_NAME).is_file():
            self._append_log("ATTENZIONE: manifest.json non trovato. Metti la cartella 'diff' accanto all'eseguibile.")

    def _build_ui(self) -> None:
        pad = 10

        frm = ttk.Frame(self, padding=pad)
        frm.pack(fill="both", expand=True)

        title = ttk.Label(frm, text="Applicatore patch", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w", pady=(0, 10))

        path_row = ttk.Frame(frm)
        path_row.pack(fill="x", pady=(0, 8))

        ttk.Label(path_row, text="Cartella gioco:").pack(side="left")
        entry = ttk.Entry(path_row, textvariable=self.game_path_var)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 8))

        browse = ttk.Button(path_row, text="Sfoglia...", command=self._browse)
        browse.pack(side="left")

        hint = ttk.Label(
            frm,
            text="Per giochi PS3: seleziona la cartella che contiene direttamente PS3_GAME.",
        )
        hint.pack(anchor="w", pady=(0, 8))

        opt_row = ttk.Frame(frm)
        opt_row.pack(fill="x", pady=(0, 8))

        ttk.Checkbutton(
            opt_row,
            text="Verifica hash file originali",
            variable=self.verify_var,
        ).pack(side="left")

        ttk.Checkbutton(
            opt_row,
            text="Forza sovrascrittura se hash diverso",
            variable=self.force_var,
        ).pack(side="left", padx=(20, 0))

        self.progress = ttk.Progressbar(frm, mode="determinate")
        self.progress.pack(fill="x", pady=(2, 8))

        self.log = tk.Text(frm, height=16, wrap="word")
        self.log.pack(fill="both", expand=True)

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill="x", pady=(10, 0))

        self.apply_button = ttk.Button(btn_row, text="Applica patch", command=self._start_patch)
        self.apply_button.pack(side="right")

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(title="Seleziona la cartella del gioco")
        if chosen:
            self.game_path_var.set(chosen)

    def _append_log(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.update_idletasks()

    def _set_progress(self, current: int, total: int) -> None:
        self.progress["maximum"] = total
        self.progress["value"] = current
        self.update_idletasks()

    def _start_patch(self) -> None:
        game_root = Path(self.game_path_var.get().strip())

        if not game_root.is_dir():
            messagebox.showerror("Errore", "Seleziona una cartella gioco valida.")
            return

        if not (self.diff_root / MANIFEST_NAME).is_file():
            messagebox.showerror(
                "Errore",
                "Cartella diff non trovata o manifest.json mancante.\n"
                "Metti la cartella 'diff' accanto all'eseguibile.",
            )
            return

        if self.force_var.get():
            ok = messagebox.askyesno(
                "Conferma",
                "La forzatura può sovrascrivere file non corrispondenti alla versione attesa.\n"
                "Non permette comunque di creare da zero file 'replace' mancanti.\n"
                "Continuare?",
            )
            if not ok:
                return

        self.apply_button.config(state="disabled")
        self._append_log("")
        self._append_log("Controllo cartella gioco e file patch...")

        def worker() -> None:
            try:
                stats = apply_patch(
                    game_root=game_root,
                    diff_root=self.diff_root,
                    verify_base_hash=self.verify_var.get(),
                    force_if_mismatch=self.force_var.get(),
                    allow_missing_replace_targets=False,
                    log_callback=lambda msg: self.after(0, self._append_log, msg),
                    progress_callback=lambda c, t: self.after(0, self._set_progress, c, t),
                )
                self.after(0, self._done, stats)
            except Exception as e:
                self.after(0, self._failed, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, stats: dict) -> None:
        self.apply_button.config(state="normal")
        msg = (
            "Patch completata.\n\n"
            f"Sostituiti: {stats['replaced']}\n"
            f"Aggiunti: {stats['added']}\n"
            f"Eliminati: {stats['deleted']}\n"
            f"Saltati: {stats['skipped']}\n"
            f"Avvisi: {stats['warnings']}"
        )
        self._append_log(msg.replace("\n\n", "\n"))
        messagebox.showinfo("Completato", msg)

    def _failed(self, error: str) -> None:
        self.apply_button.config(state="normal")
        self._append_log(f"ERRORE: {error}")
        messagebox.showerror("Errore", error)


def main() -> None:
    app = PatchGui()
    app.mainloop()


if __name__ == "__main__":
    main()
