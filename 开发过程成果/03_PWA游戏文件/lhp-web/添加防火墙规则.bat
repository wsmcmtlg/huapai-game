@echo off
netsh advfirewall firewall add rule name="公安花牌HTTP服务器" dir=in action=allow protocol=tcp localport=8765
echo.
echo 防火墙规则添加完成！按任意键关闭...
pause >nul
