# Vinf Agent 一键安装（Windows PowerShell）
# 用法：powershell -ExecutionPolicy Bypass -File install.ps1
#   或：& .\install.ps1
#
# 做三件事：
#   1. 检测 python >= 3.10
#   2. 创建 %LOCALAPPDATA%\bin\vinf-agent.cmd（bin/ 内的零安装启动器）
#   3. 加入用户 PATH（如需）
$ErrorActionPreference = "Stop"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[错误] 需要 python (>= 3.10)，请先安装：https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
$ver = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "[ok] python $ver" -ForegroundColor Green

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetDir = Join-Path $env:LOCALAPPDATA "bin"
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

$launcher = Join-Path $targetDir "vinf-agent.cmd"
@"
@echo off
setlocal
set "VINF_ROOT=$repo"
python "%VINF_ROOT%\run.py" %*
exit /b %ERRORLEVEL%
"@ | Set-Content -Path $launcher -Encoding ascii
Write-Host "[ok] 已创建 $launcher" -ForegroundColor Green

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$targetDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$targetDir", "User")
    Write-Host "[ok] 已把 $targetDir 加入用户 PATH（新开终端生效）" -ForegroundColor Green
} else {
    Write-Host "[ok] PATH 已包含 $targetDir" -ForegroundColor Green
}

Write-Host "完成。下一步（新开终端）：" -ForegroundColor Cyan
Write-Host "  Copy-Item -Recurse <repo>\config.example config" -ForegroundColor Yellow
Write-Host "  `$env:VINF_API_KEY = 'sk-...'" -ForegroundColor Yellow
Write-Host "  vinf-agent --web        # 启动本地 Web 版" -ForegroundColor Yellow
Write-Host "  vinf-agent              # 或 CLI 模式" -ForegroundColor Yellow