@echo off
setlocal

cd /d "%~dp0.."

echo ==========================================
echo Building Smart Image Search EXE
echo ==========================================

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Please run setup_windows.bat first.
    pause
    exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"

if not exist "tesseract\tesseract.exe" (
    echo.
    echo ERROR: Bundled Tesseract not found.
    echo.
    echo First run:
    echo scripts\build_windows.bat
    echo.
    pause
    exit /b 1
)

if exist build (
    rmdir /s /q build
)

if exist dist (
    rmdir /s /q dist
)

echo.
echo Creating ONE FILE EXE...
echo.

"%PYTHON%" -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name SmartImageSearch ^
    --icon "%CD%\logo.ico" ^
    --add-data "tesseract;tesseract" ^
    --add-data "logo.ico;." ^
    --collect-all fastapi ^
    --collect-all uvicorn ^
    --collect-all pytesseract ^
    --collect-all pymupdf ^
    --collect-all PyQt6 ^
    run.py

if errorlevel 1 (
    echo.
    echo ==========================================
    echo BUILD FAILED
    echo ==========================================
    pause
    exit /b 1
)

echo.
echo ==========================================
echo BUILD SUCCESSFUL
echo ==========================================
echo.
echo EXE:
echo.
echo dist\SmartImageSearch.exe
echo.
echo Copy ONLY this EXE to the client computer.
echo.
