param([string]$Url = "http://localhost:8090")

# 智展研究院设计开发管理系统 - 桌面快捷方式创建脚本（PowerShell）
# 生成真正的 .lnk 快捷方式：
#  - TargetPath 直接填 URL → Windows shell 原生用默认浏览器打开（与 .url 同样可靠）
#  - IconLocation 指向 logo.ico → 系统 Logo 图标可靠显示（.url 方案图标会被浏览器图标覆盖）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File create-shortcut.ps1 -Url "http://服务器IP"

$Name = "智展研究院设计开发管理系统"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Icon = Join-Path $Dir "logo.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $Desktop "$Name.lnk"

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $Url
$lnk.IconLocation = "$Icon,0"
$lnk.Description = $Name
$lnk.Save()

Write-Host "已在桌面创建快捷方式: $Name.lnk"
Write-Host "打开地址: $Url"
Write-Host "图标: $Icon"
