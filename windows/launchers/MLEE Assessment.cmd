@echo off
rem MLEE Assessment test console (menu). Start-menu and desktop shortcut.
setlocal
call "%~dp0_env.cmd"
title MLEE Assessment
"%MLEE_PY%" -s -X utf8 mlee_menu.py
exit /b %ERRORLEVEL%
