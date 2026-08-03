@echo off
chcp 65001 >nul
title 公安花牌 - 本地服务器
echo.
echo  ======================================
echo    公安花牌 - 本地服务器
echo    按 Ctrl+C 停止服务器
echo  ======================================
echo.
cd /d "%~dp0"
start http://localhost:8765/step5-hu.html?v=194112
python -m http.server 8765 --bind 0.0.0.0
pause
