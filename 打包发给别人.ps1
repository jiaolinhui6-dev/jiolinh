# 课程 Deadline 哨兵 —— 打包脚本（场景B：把项目发给别人体验）
#
# 用法：在本文件所在目录执行
#     powershell -ExecutionPolicy Bypass -File 打包发给别人.ps1
#
# 说明：
#   * 会把当前项目打包成一个 zip，排除缓存、导出产物、你自己的 .env。
#   * 询问是否"内置演示 API"：
#       - 选 是：把 .env 里的 DEMO_* 一起写进包（别人开箱即用 AI，但会用你的演示额度）
#       - 选 否：不带任何 Key，别人只能离线体验（对方可自己填 API）
#   * 不会把 .env 原样复制（避免把你自己的 BASE_URL/API_KEY 泄露）。

Set-Location -Path $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$outName = "Deadline哨兵-$stamp.zip"
$outPath = Join-Path $PSScriptRoot $outName
$stage = Join-Path $env:TEMP ("ds_pack_" + $stamp)

Write-Host "== 打包 Deadline 哨兵 ==" -ForegroundColor Cyan

# 1) 询问是否内置演示 API
$demoBase = ""; $demoKey = ""; $demoModel = ""
if (Test-Path ".env") {
  Get-Content ".env" | ForEach-Object {
    $l = $_.Trim()
    if ($l -and -not $l.StartsWith("#") -and $l.Contains("=")) {
      $k, $v = $l.Split("=", 2)
      switch ($k.Trim()) {
        "DEMO_BASE_URL" { $demoBase = $v.Trim() }
        "DEMO_API_KEY"  { $demoKey  = $v.Trim() }
        "DEMO_MODEL"    { $demoModel = $v.Trim() }
      }
    }
  }
}
$hasDemo = $demoBase -and $demoKey -and $demoModel
$embed = $false
if ($hasDemo) {
  $ans = Read-Host "检测到演示 API 配置。是否打包进 zip（别人可直接体验AI，但消耗你的额度）？输入 y 确认 / 其他为不打包"
  $embed = ($ans -eq "y" -or $ans -eq "Y")
} else {
  Write-Host "未检测到 DEMO_* 配置，将打包为离线版（对方可自己填 API）。" -ForegroundColor Yellow
}

# 2) 准备临时目录（只复制需要的文件）
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$exclude = @("__pycache__", ".git", ".venv", "venv", "*.pyc", "unzip*", "*.zip", "export_*", ".env")
Get-ChildItem -Force | Where-Object {
  $name = $_.Name
  $skip = $false
  foreach ($e in $exclude) { if ($name -like $e) { $skip = $true } }
  -not $skip
} | ForEach-Object {
  Copy-Item $_.FullName -Destination $stage -Recurse -Force
}

# 3) 生成包内 .env
$envLines = @()
if ($embed) {
  $envLines += "# 演示 API（作者提供，供快速体验）"
  $envLines += "DEMO_BASE_URL=$demoBase"
  $envLines += "DEMO_API_KEY=$demoKey"
  $envLines += "DEMO_MODEL=$demoModel"
  $envLines += ""
}
$envLines += "# 我的 API（可留空；也可在网页设置里填写）"
$envLines += "BASE_URL="
$envLines += "API_KEY="
$envLines += "MODEL="
[System.IO.File]::WriteAllLines((Join-Path $stage ".env"), $envLines)

# 4) 压缩
if (Test-Path $outPath) { Remove-Item $outPath -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $outPath -Force
Remove-Item $stage -Recurse -Force

Write-Host ""
Write-Host ("打包完成：" + $outPath) -ForegroundColor Green
if ($embed) { Write-Host "已内置演示 API：对方打开即可体验 AI。" -ForegroundColor Green }
else { Write-Host "离线版：对方可离线使用，或自己在网页填 API。" -ForegroundColor Yellow }
Write-Host "提醒：请给演示用的 Key 在服务商后台设置额度上限，避免被刷爆。"