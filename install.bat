@echo off
REM ============================================================
REM  IMG Dataset Refiner v4.1 Pro - Installation
REM  Installe Python (verification) + dependances dans un venv local
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   IMG Dataset Refiner - Installation
echo ============================================================
echo.

REM 1. Verifier que Python est present
where python >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo.
    echo Solution :
    echo   1. Telechargez Python 3.10 ou superieur depuis :
    echo      https://www.python.org/downloads/
    echo   2. IMPORTANT : cochez "Add Python to PATH" pendant l'installation.
    echo   3. Relancez ce script.
    echo.
    pause
    exit /b 1
)

REM Afficher la version Python detectee
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Python detecte : %PYVER%

REM 2. Creer le venv si absent
if not exist "venv\Scripts\python.exe" (
    echo.
    echo [1/3] Creation de l'environnement virtuel "venv"...
    python -m venv venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement virtuel.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Environnement virtuel "venv" deja present, reutilisation.
)

REM 3. Activer le venv
call venv\Scripts\activate.bat

REM 4. Mettre a jour pip et installer les dependances
echo.
echo [2/3] Mise a jour de pip...
python -m pip install --upgrade pip --quiet

echo.
echo [3/3] Installation des dependances (peut prendre quelques minutes)...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERREUR] L'installation des dependances a echoue.
    echo Verifiez votre connexion internet et reessayez.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Installation terminee avec succes !
echo ============================================================
echo.
echo Pour lancer IMG Dataset Refiner, double-cliquez sur :
echo    start.bat
echo.
pause
