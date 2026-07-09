@echo off
rem Care Manager launcher: copies the shared exe locally ONLY when the shared
rem copy is newer (xcopy /d), then starts the local copy. Point each PC's
rem desktop shortcut at this file (shortcut can use bowery-emblem.ico and
rem "Run: Minimized" so the console never shows).
rem
rem One-time per PC: set SHARE below to your shared folder, copy this file
rem anywhere local (e.g. C:\CareManager\launcher.bat), make the shortcut.

set "SHARE=\\SERVER\Share\CareManagerApp"
set "LOCAL=%LOCALAPPDATA%\CareManager"

if not exist "%LOCAL%" mkdir "%LOCAL%"
xcopy "%SHARE%\Care Manager.exe" "%LOCAL%\" /d /y >nul 2>&1
if not exist "%LOCAL%\Care Manager.exe" (
    echo Care Manager is not available yet. Check that %SHARE% is reachable.
    pause
    exit /b 1
)
start "" "%LOCAL%\Care Manager.exe"
