@echo off
cd /d "%~dp0\.."

start "" cmd /k "python -m uvicorn app.main:app --port 8000"

timeout /t 5 /nobreak >nul

set "UIFile="
for /r "%cd%" %%f in (movie_tracker_ui.html) do (
  set "UIFile=%%f"
  goto :found
)
:found

if defined UIFile (
  start "" "%UIFile%"
) else (
  echo Movie Tracker UI file not found. Ensure it exists in the project directory.
  pause
)
