@echo off
cd /d "%~dp0\.."
echo Building StreamTracker executable...
echo.

REM Install PyInstaller if not already installed
python -m pip install pyinstaller

REM Clean previous builds
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Build the executable using python -m
python -m PyInstaller streamtracker.spec

if exist "dist\StreamTracker.exe" (
    echo.
    echo Build successful! Executable created at: dist\StreamTracker.exe
    echo.
    echo You can now distribute the entire 'dist' folder to users.
    echo They just need to run StreamTracker.exe to start the application.
) else (
    echo.
    echo Build failed! Check the output above for errors.
)

pause
