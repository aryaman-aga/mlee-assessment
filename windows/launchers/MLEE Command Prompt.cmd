@echo off
rem Command prompt with the bundled Python and Tectonic on PATH.
call "%~dp0_env.cmd"
title MLEE Assessment - command prompt
echo.
echo   MLEE Assessment command prompt
echo   The bundled Python, Tectonic and the project folder are ready here.
echo.
echo     python build.py --analysis-only   run the four tasks
echo     python build.py                   analysis, PDF report and checks
echo     python mlee_assessment.py         the analysis script on its own
echo     python -m pip list                installed libraries
echo.
cmd /k
