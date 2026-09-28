@echo off
cd /d "%~dp0"
python app.py
if errorlevel 1 (
    echo.
    echo O programa encontrou um erro.
    echo Verifique a mensagem acima.
    pause
)
