@echo off
:: substrate-iterate.bat — One-click substrate iteration (Windows)
::
:: Usage:
::   Double-click this file.
::   If there's a session capture on your clipboard, it gets ingested.
::   If not, it runs on existing captures.
::
:: Place this anywhere convenient — Desktop, taskbar, etc.
:: Just update the path below if your substrate-iteration folder moves.

setlocal

:: ── Config ──────────────────────────────────────────────────────────────
set ITER_DIR=%~dp0
:: If this .bat isn't in the substrate-iteration folder, set the path:
:: set ITER_DIR=C:\Users\User\substrate-iteration

:: ── Check Python ────────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Install Python 3.8+ and add to PATH.
    pause
    exit /b 1
)

:: ── Check for clipboard content ─────────────────────────────────────────
echo.
echo  ============================================
echo   SUBSTRATE ITERATION SYSTEM
echo  ============================================
echo.

:: Try to get clipboard — if it looks like a capture, pipe it in
powershell -Command "Get-Clipboard" > "%TEMP%\_clipboard_check.txt" 2>nul

findstr /i /c:"session capture" /c:"Goal:" /c:"Progress:" /c:"Momentum:" "%TEMP%\_clipboard_check.txt" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Found session capture on clipboard. Ingesting...
    echo.
    powershell -Command "Get-Clipboard" | python "%ITER_DIR%auto.py"
) else (
    echo  No capture on clipboard. Running on existing captures...
    echo.
    python "%ITER_DIR%auto.py" --skip-ingest
)

del "%TEMP%\_clipboard_check.txt" 2>nul

echo.
pause
