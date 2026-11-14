@echo off
title SDN Mininet & AI Dashboard - Khoi dong he thong
color 0A

echo =======================================================================
echo          KHOI DONG TOAN BO HE THONG SDN MININET & AI DASHBOARD
echo =======================================================================
echo.

echo [*] 1/6. Don dep phien cu va khoi dong lai dich vu Open vSwitch...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Where-Object { $_.CommandLine -match 'dashboard|test_mock_system' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
wsl -d Ubuntu-22.04 -u root bash -c "killall -9 ryu-manager python3 iperf iperf3 2>/dev/null || true"
wsl -d Ubuntu-22.04 -u root bash -c "rm -f /tmp/sdn_qos.db* /mnt/d/Project/SDN_ML_Project/database/sdn_qos.db-wal /mnt/d/Project/SDN_ML_Project/database/sdn_qos.db-shm 2>/dev/null || true"
wsl -d Ubuntu-22.04 -u root bash -c "mn -c >/dev/null 2>&1"
wsl -d Ubuntu-22.04 -u root bash -c "service openvswitch-switch restart >/dev/null 2>&1"

echo [*] 2/6. Kiem tra mo hinh AI (.pkl) va dat lai trang thai Database ve K1 (P1)...
wsl -d Ubuntu-22.04 -u root bash -c "cd /mnt/d/Project/SDN_ML_Project && ([ -f ml_engine/qos_model_rf.pkl ] || python3 ml_model.py) && python3 -c \"from database.db_manager import DatabaseManager; db=DatabaseManager(); db.clear_metrics(); db.set_system_status('active_path','P1'); db.set_system_status('force_reset_path','P1'); db.set_system_status('current_scenario','K1'); db.set_system_status('ml_risk','8.4'); db.set_system_status('ml_pred','0'); db.set_system_status('system_status','NORMAL'); db.set_system_status('collect_mode','0'); db.set_system_status('netem_degraded','0'); db.set_system_status('link_s2_s6_down','0')\""

echo.
echo [*] 3/6. Khoi dong Ryu Controller tai port 6653...
start "SDN Ryu Controller" wsl -d Ubuntu-22.04 -u root bash -c "cd /mnt/d/Project/SDN_ML_Project && ryu-manager controller.py || read -p 'Loi Ryu Controller! Nhan Enter de dong...'"

echo [*] Cho Ryu Controller khoi dong va lang nghe o port 6653...
wsl -d Ubuntu-22.04 -u root python3 -c "import socket, time; [exit(0) if socket.socket().connect_ex(('127.0.0.1', 6653)) == 0 else time.sleep(1) for _ in range(20)]"

echo [*] Ryu Controller da san sang tai port 6653!
echo.

echo [*] 4/6. Khoi dong Web Dashboard tai port 5000...
start "SDN Web Dashboard" wsl -d Ubuntu-22.04 -u root bash -c "cd /mnt/d/Project/SDN_ML_Project && python3 dashboard/app.py || read -p 'Loi Web Dashboard! Nhan Enter de dong...'"

echo [*] Cho Web Dashboard san sang...
wsl -d Ubuntu-22.04 -u root python3 -c "import socket, time; [exit(0) if socket.socket().connect_ex(('127.0.0.1', 5000)) == 0 else time.sleep(1) for _ in range(20)]"

echo [*] Web Dashboard da san sang tai http://127.0.0.1:5000!
echo.

echo [*] 5/6. Tu dong mo trinh duyet Web Dashboard...
start http://127.0.0.1:5000

echo.
echo =======================================================================
echo   [*] 6/6. DANG KHOI TAO TOPOLOGY 6 SWITCH: topology.py
echo =======================================================================
echo   Tren giao dien Dashboard (http://127.0.0.1:5000):
echo     - Quan sat 3 tuyen duong P1, P2, P3
echo     - Bam nut K1-K6 de bom luong iperf that tren mang Mininet
echo     - Theo doi do thi Telemetry va canh bao AI thoi gian thuc
echo.
echo   Cac lenh thu trong mininet:
echo     - pingall           : Kiem tra thong mang toan bo host
echo     - h1 ping -c 4 h2   : Ping tu h1 sang h2
echo     - iperf h1 h2       : Do bang thong thuc te
echo.
echo   DE THOAT HE THONG AN TOAN: Go lenh 'exit'
echo =======================================================================
echo.

wsl -d Ubuntu-22.04 -u root bash -c "cd /mnt/d/Project/SDN_ML_Project && python3 topology.py"

echo.
echo =======================================================================
echo [*] Da thoat Mininet. Dang tu dong don dep an toan toan bo he thong...
echo =======================================================================
wsl -d Ubuntu-22.04 -u root bash -c "mn -c >/dev/null 2>&1"
wsl -d Ubuntu-22.04 -u root bash -c "killall -9 ryu-manager python3 iperf iperf3 2>/dev/null || true"
taskkill /FI "WINDOWTITLE eq SDN Ryu Controller*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq SDN Web Dashboard*" /F >nul 2>&1
echo [*] Don dep hoan tat! Toan bo tien trinh da duoc tat an toan.
pause
