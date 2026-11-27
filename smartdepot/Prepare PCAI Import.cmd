@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 launcher.py prepare-import
goto result
:python
python launcher.py prepare-import
:result
set "PCAI_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %PCAI_RESULT%
