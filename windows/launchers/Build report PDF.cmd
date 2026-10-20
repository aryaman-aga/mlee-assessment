@echo off
rem Runs the analysis, typesets the PDF report (offline TeX) and checks it.
rem Pass "nopause" to skip opening the PDF and waiting for a key.
setlocal
call "%~dp0_env.cmd"
title MLEE Assessment - build report PDF
"%MLEE_PY%" -s -X utf8 build.py --compare
set "RC=%ERRORLEVEL%"
if /i "%~1"=="nopause" exit /b %RC%
if "%RC%"=="0" start "" "%MLEE_APP%\output\MLEE_Assessment_Report.pdf"
echo.
pause
exit /b %RC%
