@echo off
rem Runs all four tasks and compares the numbers with the reference run.
rem Pass "nopause" to skip opening the figures and waiting for a key.
setlocal
call "%~dp0_env.cmd"
title MLEE Assessment - run analysis
"%MLEE_PY%" -s -X utf8 build.py --analysis-only --compare
set "RC=%ERRORLEVEL%"
if /i "%~1"=="nopause" exit /b %RC%
if "%RC%"=="0" start "" "%MLEE_APP%\report\figures"
echo.
pause
exit /b %RC%
