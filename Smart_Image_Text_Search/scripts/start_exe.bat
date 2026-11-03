@echo off
setlocal
cd /d "%~dp0.."

if not exist "dist\SmartImageSearch\SmartImageSearch.exe" (
  echo EXE not found. Build it first with scripts\build_windows.bat
  pause
  exit /b 1
)

start "" "dist\SmartImageSearch\SmartImageSearch.exe"
