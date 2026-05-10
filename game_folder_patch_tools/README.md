# Game Folder Patch Tools

Contiene:

1. `create_diff.py`  
   Crea la cartella `diff` confrontando una cartella originale e una cartella modificata.

2. `patch_app_gui.py`  
   Applicatore patch con GUI Tkinter. Può essere compilato in `.exe` standalone.

3. `build_exe.bat`  
   Script Windows per generare l'exe con PyInstaller.

## Creare la patch

Esempio generale:

```bat
python create_diff.py "C:\GIOCO_ORIGINALE" "C:\GIOCO_MODIFICATO" --out diff
```

Solo file `.xxx`:

```bat
python create_diff.py "C:\GIOCO_ORIGINALE" "C:\GIOCO_MODIFICATO" --out diff --include "*.xxx"
```

Verrà creata una cartella:

```text
diff/
  manifest.json
  data/
    000000_xxxxx_file.xxx.lzma
```

## Provare l'applicatore da Python

Metti `patch_app_gui.py` accanto alla cartella `diff`, poi:

```bat
python patch_app_gui.py
```

## Creare l'EXE standalone

Su Windows:

```bat
pip install pyinstaller
build_exe.bat
```

Dopo la build, copia `diff` dentro `dist` accanto all'exe:

```text
dist/
  PatchGame.exe
  diff/
    manifest.json
    data/
      ...
```

Poi distribuisci `PatchGame.exe` + cartella `diff`.

## Note importanti

- La patch è binaria: non interpreta i file `.xxx`.
- I file modificati vengono sovrascritti nella cartella scelta.
- L'opzione "Verifica hash file originali" evita di applicare la patch su una versione sbagliata.
- L'opzione "Forza sovrascrittura" applica comunque la patch anche se il file target non combacia con l'hash originale.
- Se devi distribuire una traduzione/mod, in genere è più sicuro distribuire solo patch/diff e non l'intero gioco.
