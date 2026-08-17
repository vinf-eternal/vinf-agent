@echo off
rem Vinf Agent launcher (zero-install, Windows)
rem Usage: add this folder to PATH, then run `vinf-agent [args]` anywhere
setlocal
set "VINF_ROOT=%~dp0.."
python "%VINF_ROOT%\run.py" %*
exit /b %ERRORLEVEL%