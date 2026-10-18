@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3 must be installed. Open https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
py -3 -m pip install --user boto3 keyring
if errorlevel 1 (echo [ERROR] Python package setup failed. & pause & exit /b 1)
py -3 "r2_windows_sync.py" setup
echo.
echo [RESULT] Connection setup finished. Only read-only R2 credentials are permitted.
pause
