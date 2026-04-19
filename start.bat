@echo off

setlocal

cd /d "%~dp0"



if not exist ".venv\Scripts\python.exe" (

  echo [ERROR] Missing .venv\Scripts\python.exe

  echo Please create the virtual environment first.

  exit /b 1

)



echo Starting Wenfxl Codex Manager...

start "Wenfxl Codex Manager" cmd /k ".venv\Scripts\python.exe wfxl_openai_regst.py"

echo Project started in a new window.

echo URL: http://127.0.0.1:8000

echo Password: admin

