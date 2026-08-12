param([string]$Url = "http://localhost:8090")

# 智展研究院设计开发管理系统 - 桌面快捷方式创建脚本（PowerShell）
# 生成真正的 .lnk 快捷方式，图标可靠显示系统 Logo（.url 方案图标会被浏览器图标覆盖）
# 用 rundll32 url.dll,FileProtocolHandler 打开 URL → 始终走系统默认浏览器
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File create-shortcut.ps1 -Url "http://服务器IP"

$Name = "智展研究院设计开发管理系统"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Icon = Join-Path $Dir "logo.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $Desktop "$Name.lnk"

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = "$env:SystemRoot\System32\rundll32.exe"
$lnk.Arguments = "url.dll,FileProtocolHandler,$Url"
$lnk.IconLocation = "$Icon,0"
$lnk.Description = $Name
$lnk.Save()

Write-Host "已在桌面创建快捷方式: $Name.lnk"
Write-Host "打开地址: $Url"
Write-Host "图标: $Icon"
