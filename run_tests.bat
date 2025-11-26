@echo off
echo Running OmniTrackr Test Suite...
echo.

REM Check if pytest is installed
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo pytest not found. Installing test dependencies...
    pip install -r requirements.txt
)

echo.
echo Running all tests...
python -m pytest tests/ -v --tb=short

echo.
echo Test run complete!
pause

