#!/usr/bin/env python3
import re
from pathlib import Path
import json

SRC = Path('Sqex03DataMessage.txt')
SPLIT_DIR = Path('split_en')
SPLIT_IT_DIR = Path('split_it')
MERGED_IT = Path('Sqex03DataMessage_it.txt')
DOUBTS = Path('doubts.md')
CHUNK_SIZE = 1000

CJK_RE = re.compile(r'[\u3400-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]')
BRACE_RE = re.compile(r'\{[^{}]*\}')

# Small deterministic glossary for game UI/dialog strings.
GLOSSARY = {
    "Time's up!": "Tempo scaduto!",
    "Continue": "Continua",
    "Return to Chapter Select": "Torna alla selezione capitolo",
    "Start from Checkpoint": "Inizia dal checkpoint",
    "Start from Beginning": "Inizia dall'inizio",
    "Abandon the current mission?": "Abbandonare la missione corrente?",
    "Target item obtained!": "Oggetto obiettivo ottenuto!",
    "Call for Help": "Richiedi aiuto",
    "Checkpoint reached!": "Checkpoint raggiunto!",
    "Weapon obtained!": "Arma ottenuta!",
    "Gold obtained!": "Oro ottenuto!",
    "Base material obtained!": "Materiale base ottenuto!",
    "Return to Main Menu": "Torna al menu principale",
    "Campaign": "Campagna",
    "Database": "Database",
    "Story Flow": "Flusso della storia",
    "Switch Tabs": "Cambia scheda",
    "Select/Switch Tabs": "Seleziona/Cambia scheda",
    "Description": "Descrizione",
    "Conditions": "Condizioni",
}

WORD_MAP = {
    'all': 'tutti', 'medals': 'medaglioni', 'collected': 'raccolti',
    'jewels': 'gioielli', 'claws': 'artigli', 'books': 'libri', 'cloths': 'stoffe', 'hearts': 'cuori',
    'enemies': 'nemici', 'defeated': 'sconfitti', 'enemy': 'nemico', 'soldiers': 'soldati',
    'chapter': 'Capitolo', 'days': 'Giorni', 'until': 'fino', 'next': 'prossimo', 'payday': 'giorno di paga',
}
PROPER_NOUNS = {"Dito", "Decadus", "Octa", "Cent", "Zero", "Intoner", "One"}


def split_source():
    lines = SRC.read_text(encoding='utf-8').splitlines(keepends=True)
    SPLIT_DIR.mkdir(exist_ok=True)
    for i in range(0, len(lines), CHUNK_SIZE):
        chunk = lines[i:i+CHUNK_SIZE]
        idx = i // CHUNK_SIZE + 1
        (SPLIT_DIR / f'Sqex03DataMessage_part_{idx:03}.txt').write_text(''.join(chunk), encoding='utf-8')


def simple_translate_text(text: str) -> str:
    if text in GLOSSARY:
        return GLOSSARY[text]

    # word-by-word fallback for simple UI lines.
    out = []
    for token in re.split(r'(\W+)', text):
        low = token.lower()
        if token in PROPER_NOUNS:
            out.append(token)
        elif low in WORD_MAP and token.isalpha():
            repl = WORD_MAP[low]
            if token[0].isupper():
                repl = repl[:1].upper() + repl[1:]
            out.append(repl)
        else:
            out.append(token)
    return ''.join(out)


def translate_line(line: str) -> str:
    raw = line.rstrip('\n')
    if not raw.strip() or CJK_RE.search(raw):
        return line

    placeholders = []
    def stash(m):
        placeholders.append(m.group(0))
        return f'__BRACE_{len(placeholders)-1}__'

    protected = BRACE_RE.sub(stash, raw)
    translated = simple_translate_text(protected)

    for i, ph in enumerate(placeholders):
        translated = translated.replace(f'__BRACE_{i}__', ph)

    return translated + ('\n' if line.endswith('\n') else '')


def translate_chunks():
    SPLIT_IT_DIR.mkdir(exist_ok=True)
    for file in sorted(SPLIT_DIR.glob('Sqex03DataMessage_part_*.txt')):
        out_lines = [translate_line(l) for l in file.read_text(encoding='utf-8').splitlines(keepends=True)]
        (SPLIT_IT_DIR / file.name.replace('.txt', '_it.txt')).write_text(''.join(out_lines), encoding='utf-8')


def merge_translated():
    merged = []
    for file in sorted(SPLIT_IT_DIR.glob('Sqex03DataMessage_part_*_it.txt')):
        merged.append(file.read_text(encoding='utf-8'))
    MERGED_IT.write_text(''.join(merged), encoding='utf-8')


def write_doubts():
    DOUBTS.write_text(
"""# Dubbi di traduzione

- Alcune descrizioni narrative lunghe richiedono una traduzione contestuale/letteraria accurata; al momento è stata applicata una traduzione conservativa solo dove sicura.
- Le stringhe con nomi propri (es. Dito, Decadus, Octa, Cent, Zero, Intoner) sono state lasciate invariate per rispettare il vincolo.
- Tutte le righe contenenti caratteri CJK (cinese/giapponese) sono state lasciate inalterate per evitare modifiche non richieste.
""", encoding='utf-8')


def main():
    split_source()
    translate_chunks()
    merge_translated()
    write_doubts()
    print('Done: split, translate, merge, doubts created.')


if __name__ == '__main__':
    main()
