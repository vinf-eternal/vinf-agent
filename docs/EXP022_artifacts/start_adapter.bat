@echo off
rem ============================================================
rem sl0-mcp Streamable HTTP adapter launcher
rem Usage:
rem   start_adapter.bat                      -> default (threshold auto/calibration)
rem   start_adapter.bat --summon-threshold 0 -> ablation runs
rem   start_adapter.bat --port 18742         -> any mcp_http_adapter.py args pass through
rem ============================================================
cd /d D:\wayne\Twincosmos\SiliconLifeOS\projects\v_os\sl0_mcp_deploy\mcp
python -u mcp_http_adapter.py --host 127.0.0.1 --port 18741 %*
