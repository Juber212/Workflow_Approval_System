@echo off
rem ============================================================
rem  智展研究院设计开发管理系统 - 桌面快捷方式创建脚本
rem
rem  双击运行后，自动在桌面创建系统快捷方式（带系统 Logo 图标）。
rem  图标 logo.ico 与本脚本同目录，分发时两个文件一起拷贝。
rem
rem  【部署后修改】把下面的 SYS_URL 改为实际访问地址，例如：
rem     set SYS_URL=http://192.168.1.50
rem  当前默认指向本地开发环境（前后端在本机运行时可用）。
rem ============================================================
set SYS_URL=http://localhost:8090
set SHORTCUT_NAME=智展研究院设计开发管理系统
set DESKTOP=%USERPROFILE%\Desktop
if not exist "%DESKTOP%" set DESKTOP=%USERPROFILE%\OneDrive\Desktop

echo [InternetShortcut] > "%DESKTOP%\%SHORTCUT_NAME%.url"
echo URL=%SYS_URL% >> "%DESKTOP%\%SHORTCUT_NAME%.url"
echo IconFile=%~dp0logo.ico >> "%DESKTOP%\%SHORTCUT_NAME%.url"

echo.
echo  已在桌面创建快捷方式：%SHORTCUT_NAME%.url
echo  访问地址：%SYS_URL%
echo.
pause
