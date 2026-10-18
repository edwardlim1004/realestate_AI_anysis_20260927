@echo off
chcp 65001 >nul
cd /d "%~dp0.."
git pull --ff-only
if errorlevel 1 (echo Git pull error. & pause & exit /b 1)
py -3 "seoul-apartment-collector\export_windows.py"
if errorlevel 1 (echo Export error. & pause & exit /b 1)
pause
