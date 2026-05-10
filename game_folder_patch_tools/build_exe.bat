@echo off
setlocal

REM Build dell'applicatore GUI in EXE standalone.
REM Requisito:
REM     pip install pyinstaller

pyinstaller --onefile --windowed --name PatchGame patch_app_gui.py

echo.
echo Build completata.
echo Copia la cartella diff accanto a dist\PatchGame.exe
echo Esempio:
echo   dist\PatchGame.exe
echo   dist\diff\manifest.json
echo   dist\diff\data\...
pause
