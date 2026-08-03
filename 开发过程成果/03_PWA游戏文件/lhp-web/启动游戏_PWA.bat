@echo off
chcp 65001 >nul
title 公安花牌 - PWA本地服务器
echo.
echo  ╔════════════════════════════════════════╗
echo  ║     公安花牌 - 本地PWA服务器           ║
echo  ║     按 Ctrl+C 停止服务器               ║
echo  ╚════════════════════════════════════════╝
echo.
echo  桌面端访问: http://localhost:8765/step5-hu.html
echo.
echo  手机端访问步骤:
echo    1. 确保手机和电脑在同一WiFi下
echo    2. 查看本机IP: 在cmd中输入 ipconfig
echo    3. 手机浏览器访问: http://本机IP:8765/step5-hu.html
echo    4. Chrome浏览器: 点菜单"添加到主屏幕"即可安装为APP
echo    5. Safari浏览器: 点分享"添加到主屏幕"即可安装为APP
echo.
cd /d "%~dp0"
python -m http.server 8765 --bind 0.0.0.0
pause
