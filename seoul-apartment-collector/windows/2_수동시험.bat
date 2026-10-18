@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 "r2_windows_sync.py" sync --max-mb 25 --rate-kbps 1024
echo Result exit code: %errorlevel%
pause
