# 固定地址（serveo）：本机 SSH key 已注册，地址重启也不变。
#   固定地址： https://ddl-sentinel.serveousercontent.com
# 想换更好记的子域名：改下面 $sub 变量（需先在 console.serveo.net 用同一 key 登记该名字）。
# 用法：powershell -ExecutionPolicy Bypass -File .\上线-固定地址.ps1
Set-Location -Path $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$sub = "ddl-sentinel"

$listen = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $listen) {
  Write-Host "启动网站 webapp.py ..." -ForegroundColor Cyan
  Start-Process -WindowStyle Hidden python -ArgumentList "webapp.py" -WorkingDirectory $PSScriptRoot
  Start-Sleep -Seconds 3
} else {
  Write-Host "网站已在运行： http://127.0.0.1:8000"
}

Write-Host ""
Write-Host "固定地址： https://$sub.serveousercontent.com" -ForegroundColor Green
Write-Host "（关掉本窗口或按 Ctrl+C 即断开；重跑本脚本地址不变）"
Write-Host ""
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -R "${sub}:80:127.0.0.1:8000" serveo.net
