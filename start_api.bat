@echo off
echo 🚀 Avvio Medical Facial Analysis API...
echo.

cd /d "%~dp0"

:: Controlla se Python è disponibile
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python non trovato nel PATH
    echo Installa Python o aggiungi python.exe al PATH
    pause
    exit /b 1
)

:: Installa dipendenze se necessario
echo 📦 Controllo dipendenze...
pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo 📦 Installazione FastAPI...
    pip install fastapi uvicorn
)

:: Avvia l'API
echo 🌐 Avvio server API...
echo Premi Ctrl+C per fermare il server
echo.

python webapp\api\main.py

pause