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

REM Verifier que le venv fonctionne (pyvenv.cfg peut pointer vers un Python absent)
"%~dp0venv\Scripts\python.exe" --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [AVERTISSEMENT] L'environnement virtuel est corrompu ou lie a un autre Python.
    echo Reconstruction automatique du venv...
    echo.
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERREUR] Python introuvable dans le PATH. Lancez install.bat.
        pause
        exit /b 1
    )
    rmdir /s /q venv
    python -m venv venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de recreer l'environnement virtuel.
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERREUR] L'installation des dependances a echoue.
        pause
        exit /b 1
    )
    echo.
    echo [OK] Environnement virtuel reconstruit avec succes.
    echo.
    goto :launch
)

REM Activer le venv et lancer le script
call venv\Scripts\activate.bat

:launch
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
