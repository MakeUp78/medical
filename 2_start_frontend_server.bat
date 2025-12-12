@echo off
echo ========================================
echo   FRONTEND SERVER (porta 3000)
echo ========================================
echo.

cd /d "%~dp0"

REM Attiva virtual environment e avvia Frontend
call venv\Scripts\activate.bat
python start_webapp.py

pause
