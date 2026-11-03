@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "PYTHON=%CD%\.venv\Scripts\python.exe"
set "STAGE=%CD%\build\licensing-prompt-20261102"
set "ISCC_EXE="
set "PYTHONPATH=%CD%"

if not exist "%PYTHON%" (
  echo Project virtual environment not found: %PYTHON%
  exit /b 1
)
if not exist "tesseract\tesseract.exe" (
  echo Bundled Tesseract was not found. The existing installer will not be changed.
  exit /b 1
)

"%PYTHON%" -c "from app.desktop import run_desktop; from app.scanora_licensing.client import LicenceClient; print('Desktop licensing imports OK')"
if errorlevel 1 (
  echo Desktop licensing imports failed. The existing installer was not changed.
  exit /b 1
)

for /f "delims=" %%I in ('where iscc 2^>nul') do if not defined ISCC_EXE set "ISCC_EXE=%%I"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE (
  echo Inno Setup 6 compiler was not found. The existing installer will not be changed.
  exit /b 1
)

if not exist "%STAGE%\dist" mkdir "%STAGE%\dist"
if not exist "%STAGE%\work" mkdir "%STAGE%\work"
if not exist "%STAGE%\spec" mkdir "%STAGE%\spec"

echo Building the licensing-enabled desktop executable in an isolated staging folder...
"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name SmartImageSearch ^
  --distpath "%STAGE%\dist" ^
  --workpath "%STAGE%\work" ^
  --specpath "%STAGE%\spec" ^
  --icon "%CD%\logo.ico" ^
  --add-data "%CD%\tesseract;tesseract" ^
  --add-data "%CD%\logo.ico;." ^
  --collect-all fastapi ^
  --collect-all pytesseract ^
  --collect-all pymupdf ^
  --collect-all PyQt6 ^
  --collect-all cryptography ^
  run.py
if errorlevel 1 (
  echo Executable build failed. The existing installer was not changed.
  exit /b 1
)

echo Compiling a separate licensing-enabled installer...
"%ISCC_EXE%" installer\SmartImageSearch.Licensed.iss
if errorlevel 1 (
  echo Installer build failed. The existing installer was not changed.
  exit /b 1
)

if not exist "dist\installer\SmartImageSearch-Licensing-Setup.exe" (
  echo Expected installer output was not created.
  exit /b 1
)

echo.
echo New installer: dist\installer\SmartImageSearch-Licensing-Setup.exe
echo The previous SmartImageSearch-Setup.exe was preserved.