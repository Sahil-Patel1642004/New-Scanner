@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==========================================================
echo Smart Image Search - SELF-CONTAINED EXE BUILD
echo ==========================================================

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Python 3.11+ is required.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip.
  if not defined CI pause
  exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install project dependencies.
  if not defined CI pause
  exit /b 1
)

set "TESS_INSTALLER=tesseract-ocr-w64-setup-5.5.0.20241111.exe"
set "TESS_URL=https://github.com/tesseract-ocr/tesseract/releases/download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
set "CACHE=%CD%\build_tools"
set "BUNDLED=%CD%\tesseract"

if not exist "%BUNDLED%\tesseract.exe" (
  if not exist "%CACHE%" mkdir "%CACHE%"

  if not exist "%CACHE%\%TESS_INSTALLER%" (
    echo.
    echo Downloading Tesseract OCR 5.5.0 Windows 64-bit...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%TESS_URL%' -OutFile '%CACHE%\%TESS_INSTALLER%'"
    if errorlevel 1 (
      echo Failed to download Tesseract.
      if not defined CI pause
      exit /b 1
    )
  )

  echo Installing Tesseract temporarily for packaging...
  "%CACHE%\%TESS_INSTALLER%" /S

  set "SYS_TESS=C:\Program Files\Tesseract-OCR"
  if not exist "%SYS_TESS%\tesseract.exe" set "SYS_TESS=C:\Program Files (x86)\Tesseract-OCR"

  if not exist "%SYS_TESS%\tesseract.exe" (
    echo Tesseract installation was not found.
    if not defined CI pause
    exit /b 1
  )

  echo Copying Tesseract engine and language data into project...
  if exist "%BUNDLED%" rmdir /s /q "%BUNDLED%"
  mkdir "%BUNDLED%"
  xcopy "%SYS_TESS%\*" "%BUNDLED%\" /E /I /H /Y >nul
) else (
  echo Using existing bundled Tesseract files.
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building self-contained EXE...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name SmartImageSearch ^
  --icon "%CD%\logo.ico" ^
  --add-data "tesseract;tesseract" ^
  --add-data "logo.ico;." ^
  --collect-all pymupdf ^
  run.py

if errorlevel 1 (
  echo PyInstaller build failed.
  if not defined CI pause
  exit /b 1
)

echo.
echo SUCCESS:
echo dist\SmartImageSearch\SmartImageSearch.exe
echo.
echo Copy the entire SmartImageSearch folder to the client PC.
echo The client does not need Python or Tesseract installed.
if not defined CI pause
