@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0build_windows.ps1" %*
set "BUILD_RESULT=%ERRORLEVEL%"
echo.
echo Build exit code: %BUILD_RESULT%
pause
exit /b %BUILD_RESULT%
