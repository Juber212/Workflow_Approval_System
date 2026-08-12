@echo off
rem ============================================================
rem  智展研究院设计开发管理系统 - 桌面快捷方式创建脚本
rem
rem  双击运行后，自动在桌面创建系统快捷方式（带系统 Logo 图标）。
rem  需要同目录存在：create-shortcut.ps1 与 logo.ico
rem
rem  【部署后修改】把下面的 SYS_URL 改为实际访问地址，例如：
rem     set SYS_URL=http://192.168.1.50
rem  当前默认指向本地开发环境（前后端在本机运行时可用）。
rem ============================================================
set SYS_URL=http://localhost:5173

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create-shortcut.ps1" -Url "%SYS_URL%"

echo.
pause
