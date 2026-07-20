@echo off
REM ============================================================
REM  Build do executável (Windows) — PyInstaller
REM
REM  Uso:    build_exe.bat
REM  Saída:  dist\MavisMusicGenerator\MavisMusicGenerator.exe
REM ============================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo [1/4] Verificando Python...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    exit /b 1
)
python --version

echo.
echo [2/4] Criando venv (se necessario)...
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar venv.
        exit /b 1
    )
)

echo.
echo [3/4] Instalando dependencias...
call "venv\Scripts\python.exe" -m pip install --upgrade pip
call "venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    exit /b 1
)

echo.
echo [4/4] Gerando executavel com PyInstaller...
call "venv\Scripts\pyinstaller.exe" ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "MavisMusicGenerator" ^
    --collect-all wx ^
    --collect-all requests ^
    --add-data ".env.example;." ^
    --hidden-import "wx.media" ^
    run_app.py
if errorlevel 1 (
    echo [ERRO] PyInstaller falhou.
    exit /b 1
)

echo.
echo ============================================================
echo  Build concluido!
echo  Executavel: dist\MavisMusicGenerator\MavisMusicGenerator.exe
echo ============================================================
echo.
echo  IMPORTANTE:
echo  - Coloque o arquivo .env ao lado do .exe (ou em %APPDATA%\MavisMusicGenerator\).
echo  - O token MiniMax vem de MINIMAX_API_KEY ou token_minimax no .env.
echo.

endlocal
exit /b 0
