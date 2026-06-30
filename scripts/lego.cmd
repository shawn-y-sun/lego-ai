@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

if defined PYTHONPATH (
  set "PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%REPO_ROOT%"
)

if defined LEGO_PYTHON (
  "%LEGO_PYTHON%" -m Mindstorms.cli %*
  exit /b %ERRORLEVEL%
)

py -3 --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 -m Mindstorms.cli %*
  exit /b %ERRORLEVEL%
)

python --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python -m Mindstorms.cli %*
  exit /b %ERRORLEVEL%
)

echo Could not find Python. Set LEGO_PYTHON to a Python executable path.
exit /b 9009
