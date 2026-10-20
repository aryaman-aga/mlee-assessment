@echo off
rem Shared settings for the MLEE launchers. The other .cmd files CALL this.
set "MLEE_HOME=%~dp0"
set "MLEE_HOME=%MLEE_HOME:~0,-1%"
set "MLEE_APP=%MLEE_HOME%\app"
set "MLEE_PY=%MLEE_HOME%\python\python.exe"
set "MLEE_TECTONIC=%MLEE_HOME%\tectonic\tectonic.exe"
set "MLEE_TEXCACHE=%MLEE_HOME%\texcache"
set "PATH=%MLEE_HOME%\python;%MLEE_HOME%\tectonic;%PATH%"
set "PYTHONUTF8=1"
set "PYTHONNOUSERSITE=1"
cd /d "%MLEE_APP%"
