@echo off
title SDN Mininet - Don dep va Tat an toan
color 0C

echo =======================================================================
echo         TAT VA DON DEP TOAN BO HE THONG MININET, RYU & DASHBOARD
echo =======================================================================
echo.

echo [*] 1/4. Dung toan bo tien trinh Ryu, Dashboard, Mininet, iperf...
wsl -d Ubuntu-22.04 -u root bash -c "killall -9 ryu-manager python3 iperf iperf3 2>/dev/null || true"
taskkill /FI "WINDOWTITLE eq SDN Ryu Controller*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq SDN Web Dashboard*" /F >nul 2>&1
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Where-Object { $_.CommandLine -match 'dashboard|test_mock_system' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo [*] 2/4. Xoa sach cac switch ao va cong mang treo (mn -c)...
wsl -d Ubuntu-22.04 -u root bash -c "mn -c >/dev/null 2>&1"
wsl -d Ubuntu-22.04 -u root bash -c "rm -f /tmp/sdn_qos.db* /mnt/d/Project/SDN_ML_Project/database/sdn_qos.db-wal /mnt/d/Project/SDN_ML_Project/database/sdn_qos.db-shm 2>/dev/null || true"

echo [*] 3/4. Khoi dong lai dich vu Open vSwitch...
wsl -d Ubuntu-22.04 -u root bash -c "service openvswitch-switch restart >/dev/null 2>&1"

echo [*] 4/4. Giai phong hoan toan cong 6653 va 5000...
wsl -d Ubuntu-22.04 -u root bash -c "fuser -k 6653/tcp 5000/tcp 2>/dev/null || true"

echo.
echo =======================================================================
echo [OK] DA TAT VA DON DEP HOAN TOAN TOAN BO HE THONG!
echo      San sang cho lan khoi dong tiep theo.
echo =======================================================================
echo.
pause
