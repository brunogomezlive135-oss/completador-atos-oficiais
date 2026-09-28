@echo off
title Detector de Atos Oficiais
cd /d "%~dp0"

echo ============================================================
echo        DETECTOR DE ATOS OFICIAIS
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao foi encontrado.
    echo Instale o Python 3 e marque "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo Verificando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERRO ao instalar as dependencias.
    echo.
    pause
    exit /b 1
)

echo.
echo Abrindo o programa...
echo.
python app.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo O programa encontrou um erro.
    echo ============================================================
    echo.
    pause
)
