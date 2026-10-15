# 课程 Deadline 哨兵 —— 一键启动脚本（Windows PowerShell）
# 用法：在本文件所在目录执行  powershell -ExecutionPolicy Bypass -File run.ps1
# 作用：检查 Python -> 加载 .env -> 启动网页应用 -> 自动打开浏览器

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "== 课程 Deadline 哨兵 ==" -ForegroundColor Cyan

# 1) 检查 Python
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) {
  Write-Host "未找到 python，请先安装 Python 3.10+ 并加入 PATH。" -ForegroundColor Red
  Read-Host "按回车退出"; exit 1
}
Write-Host ("Python: " + (& python --version 2>&1))
$env:PYTHONIOENCODING = "utf-8"

# 2) 读取 .env（如果存在），设置所有键（含 BASE_URL/API_KEY/MODEL 与 DEMO_*）
if (Test-Path ".env") {
  Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
      $k, $v = $line.Split("=", 2)
      [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
    }
  }
  Write-Host "已加载 .env 配置。" -ForegroundColor Green
} else {
  Write-Host "未发现 .env，将以纯规则（离线）模式运行。"
}

# 3) 报告 AI 可用性
$demoOk = $env:DEMO_BASE_URL -and $env:DEMO_API_KEY -and $env:DEMO_MODEL
$myOk   = $env:BASE_URL -and $env:API_KEY -and $env:MODEL
if ($demoOk) { Write-Host "AI：演示 API 已配置（网页会自动选中）。" -ForegroundColor Green }
elseif ($myOk) { Write-Host "AI：我的 API 已配置。" -ForegroundColor Green }
else { Write-Host "AI：未配置，将以离线规则模式运行（功能照常）。" -ForegroundColor Yellow }

# 4) 启动网页
Write-Host "启动中…… 浏览器将打开 http://127.0.0.1:8000" -ForegroundColor Cyan
Start-Process "http://127.0.0.1:8000"
& python webapp.py