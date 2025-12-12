@echo off
echo ========================================
echo   API SERVER (porta 8001)
echo ========================================
echo.

cd /d "%~dp0"

REM Attiva virtual environment e avvia API
call venv\Scripts\activate.bat
python webapp\api\main.py

pause
