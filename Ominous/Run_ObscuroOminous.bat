@echo off
title Obscuro Ominous
set "OO_DESKTOP_LAUNCH=1"
call "%~dp0run.cmd" %*
set "OO_EXIT_CODE=%errorlevel%"
echo.
if "%OO_EXIT_CODE%"=="0" (
	echo Obscuro Ominous has closed normally.
) else (
	echo Obscuro Ominous stopped with exit code %OO_EXIT_CODE%.
)
pause
exit /b %OO_EXIT_CODE%
