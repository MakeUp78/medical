@echo off
echo ====================================
echo FacialMed Pro - Auth Server
echo ====================================
echo.

REM Attiva virtual environment
call venv\Scripts\activate.bat

REM Verifica dipendenze
echo Installazione dipendenze...
pip install -r requirements_auth.txt

echo.
echo Avvio Auth Server su porta 5000...
echo.

REM Avvia server
python auth_server.py

pause
