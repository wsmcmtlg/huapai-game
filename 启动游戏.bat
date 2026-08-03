@echo off
chcp 65001 >nul
title 湖北花牌 - 本地服务器启动
echo.
echo   ═══════════════════════════════
echo     湖北花牌 本地服务器已启动
echo   ═══════════════════════════════
echo.
echo   游戏地址: http://127.0.0.1:8765/step5-hu.html
echo.
echo   浏览器会自动打开，关闭此窗口即停止服务
echo   ═══════════════════════════════
echo.

cd /d "%~dp0"
start http://127.0.0.1:8765/step5-hu.html
"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\python-env\python.exe" -m http.server 8765 --bind 127.0.0.1
pause