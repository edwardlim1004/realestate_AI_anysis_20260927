@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 "r2_windows_sync.py" sync --max-mb 256 --rate-kbps 2048
exit /b %errorlevel%
