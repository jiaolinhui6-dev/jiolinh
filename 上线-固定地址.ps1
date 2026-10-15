# 固定地址（serveo）：重启也不变，地址形如 https://ddl-sentinel.serveo.net
# 首次使用：先按屏幕提示用 Google/GitHub 登录一次（注册本机 SSH key）即可。
# 用法：powershell -ExecutionPolicy Bypass -File .\上线-固定地址.ps1
Set-Location -Path $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$sub = "ddl-sentinel"

$listen = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $listen) {
  Write-Host "启动网站 webapp.py ..." -ForegroundColor Cyan
  Start-Process -WindowStyle Hidden python -ArgumentList "webapp.py" -WorkingDirectory $PSScriptRoot
  Start-Sleep -Seconds 3
}
Write-Host "启动 serveo 固定隧道： https://$sub.serveo.net" -ForegroundColor Cyan
Write-Host "（若提示未注册，请打开它给的链接用 Google/GitHub 登录一次）"
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R "${sub}:80:127.0.0.1:8000" serveo.net
