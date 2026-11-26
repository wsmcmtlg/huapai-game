@echo off
chcp 65001 >nul
title 公安花牌 - 本地启动（PWA，无需 Python）
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1" -Port 8765 -Bind 127.0.0.1 -OpenUrl "step5-hu.html?v=%RANDOM%%RANDOM%"
pause
