@echo off
setlocal
cd /d "%~dp0.."

echo Creating virtual environment...
py -3 -m venv .venv
if errorlevel 1 (
  echo Python 3 was not found. Install Python 3.11+ and try again.
  pause
  exit /b 1
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

echo.
echo Setup completed.
echo IMPORTANT: OCR requires Tesseract OCR on Windows.
echo Install Tesseract, then run scripts\run_windows.bat
if not defined CI pause
