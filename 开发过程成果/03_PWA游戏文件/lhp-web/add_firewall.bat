@echo off
netsh advfirewall firewall add rule name="HuapaGame" dir=in action=allow protocol=tcp localport=8765
echo.
echo Firewall rule added successfully! Press any key to close...
pause >nul
