# 一键上线（临时地址）：启动网站 + Cloudflare 隧道，并打印公网地址
# 用法：右键本文件 -> 使用 PowerShell 运行；或在终端执行
#   powershell -ExecutionPolicy Bypass -File .\上线-临时地址.ps1
Set-Location -Path $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

$listen = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $listen) {
  Write-Host "启动网站 webapp.py ..." -ForegroundColor Cyan
  Start-Process -WindowStyle Hidden python -ArgumentList "webapp.py" -WorkingDirectory $PSScriptRoot
  Start-Sleep -Seconds 3
} else {
  Write-Host "网站已在运行： http://127.0.0.1:8000"
}

$log = Join-Path $PSScriptRoot "tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue
Write-Host "正在建立 Cloudflare 隧道 ..."
Start-Process -WindowStyle Hidden $cf -ArgumentList "tunnel", "--url", "http://127.0.0.1:8000", "--logfile", $log

$url = $null
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 1
  if (Test-Path $log) {
    $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value; break }
  }
}
if ($url) {
  Write-Host ""
  Write-Host "公网地址：$url" -ForegroundColor Green
  $url | Set-Content -Path (Join-Path $PSScriptRoot "当前公网地址.txt") -Encoding utf8
  Write-Host "（已保存到 当前公网地址.txt）"
} else {
  Write-Host "没抓到地址，请查看 tunnel.log" -ForegroundColor Yellow
}
