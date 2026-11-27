@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 launcher.py setup
goto result
:python
python launcher.py setup
:result
set "PCAI_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %PCAI_RESULT%
