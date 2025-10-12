@echo off
REM ===============================================
REM AVVIO ADMIN VOICE CONFIGURATOR - SYMMETRA
REM Tool per amministratori del sistema
REM ===============================================

echo.
echo =============================================
echo   ADMIN VOICE CONFIGURATOR - SYMMETRA
echo =============================================
echo.
echo 🔐 ACCESSO AMMINISTRATORE RICHIESTO
echo.
echo Credenziali di default:
echo   Username: admin
echo   Password: password
echo.
echo NOTA: Cambiare le credenziali predefinite
echo       dopo il primo accesso per sicurezza
echo.
echo =============================================
echo.

REM Verifica ambiente Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERRORE: Python non trovato nel PATH
    echo.
    echo Installare Python o aggiungere al PATH di sistema:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Verifica dipendenze
echo 🔍 Verifica dipendenze...
python -c "import tkinter, ttkbootstrap, json, os" >nul 2>&1
if errorlevel 1 (
    echo ❌ Dipendenze mancanti. Installazione...
    pip install ttkbootstrap
    if errorlevel 1 (
        echo ❌ Errore installazione dipendenze
        pause
        exit /b 1
    )
)

echo ✅ Dipendenze verificate
echo.

REM Avvia configuratore
echo 🚀 Avvio Admin Voice Configurator...
echo.
python admin_voice_configurator.py

REM Gestione codici di uscita
if errorlevel 1 (
    echo.
    echo ❌ Configuratore terminato con errori
) else (
    echo.
    echo ✅ Configuratore terminato correttamente
)

echo.
pause