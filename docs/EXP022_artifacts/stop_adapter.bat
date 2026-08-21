@echo off
rem ============================================================
rem sl0-mcp adapter stopper
rem Kills EVERY python process listening on 18741.
rem Reason: Windows SO_REUSEADDR lets multiple adapters co-bind
rem the same port silently (EXP-022 incident 2026-08-21), so a
rem naive single-PID kill leaves stale listeners behind.
rem ============================================================
set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :18741 ^| findstr LISTENING') do (
    echo Killing PID %%p
    taskkill /F /PID %%p >nul 2>&1
    set FOUND=1
)
if %FOUND%==0 echo No listener on 18741.
