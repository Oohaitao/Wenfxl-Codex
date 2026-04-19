@echo off

setlocal

cd /d "%~dp0"



echo Stopping Wenfxl Codex Manager...

powershell -NoProfile -ExecutionPolicy Bypass -File ".\stop.ps1"

if errorlevel 1 exit /b %errorlevel%

echo Done.

