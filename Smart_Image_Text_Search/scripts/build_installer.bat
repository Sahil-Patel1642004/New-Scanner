@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==========================================================
echo Smart Image Search - WINDOWS INSTALLER BUILD
echo ==========================================================

set "ISCC_EXE="
for /f "delims=" %%I in ('where iscc 2^>nul') do if not defined ISCC_EXE set "ISCC_EXE=%%I"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
  echo Inno Setup compiler was not found.
  echo Install Inno Setup 6, or add ISCC.exe to PATH.
  echo Download: https://jrsoftware.org/isinfo.php
  pause
  exit /b 1
)

call scripts\build_onefile.bat
if errorlevel 1 exit /b 1
if not exist "dist\SmartImageSearch.exe" (
  echo One-file executable was not created.
  exit /b 1
)

echo Creating installer...
rem Compile outside the project folder first. OneDrive sync and antivirus scanners
rem can lock Setup.exe while Inno Setup is embedding the installer icon.
set "INSTALLER_STAGE=%TEMP%\SmartImageSearch-installer-build"
if not exist "%INSTALLER_STAGE%" mkdir "%INSTALLER_STAGE%"
"%ISCC_EXE%" /O"%INSTALLER_STAGE%" installer\SmartImageSearch.iss
if errorlevel 1 (
  echo Installer build failed.
  pause
  exit /b 1
)

if not exist "dist\installer" mkdir "dist\installer"
copy /y "%INSTALLER_STAGE%\SmartImageSearch-Setup.exe" "dist\installer\SmartImageSearch-Setup.exe" >nul
if errorlevel 1 (
  echo Installer was compiled, but could not be copied to dist\installer.
  echo Staged installer: %INSTALLER_STAGE%\SmartImageSearch-Setup.exe
  pause
  exit /b 1
)

echo.
echo SUCCESS:
echo dist\installer\SmartImageSearch-Setup.exe
echo.
pause
