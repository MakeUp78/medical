@echo off
echo ========================================
echo   WEBSOCKET SERVER (porta 8765)
echo ========================================
echo.

cd /d "%~dp0"

REM Attiva virtual environment e avvia WebSocket
call venv\Scripts\activate.bat
python face-landmark-localization-master\websocket_frame_api.py

pause
