@echo off
REM ============================================================
REM  IMG Dataset Refiner v4.4.6 Pro - Lancement
REM  Active le venv et lance lora_manager.py
REM ============================================================

setlocal
cd /d "%~dp0"

REM Verifier que l'environnement virtuel existe
if not exist "venv\Scripts\python.exe" (
    echo.
    echo [ERREUR] L'environnement virtuel "venv" n'existe pas.
    echo.
    echo Lancez d'abord install.bat pour installer les dependances.
    echo.
    pause
    exit /b 1
)

REM Activer le venv et lancer le script
call venv\Scripts\activate.bat

echo.
echo ============================================================
echo   Lancement de IMG Dataset Refiner v4.4.6 Pro
echo   (le navigateur va s'ouvrir automatiquement)
echo ============================================================
echo.

"%~dp0venv\Scripts\python.exe" lora_manager.py

REM En cas de crash, garder la fenetre ouverte
if errorlevel 1 (
    echo.
    echo [Le programme s'est arrete avec une erreur.]
    pause
)
