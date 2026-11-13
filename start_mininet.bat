@echo off
chcp 65001 > nul
title SDN Mininet - Khởi động mạng ảo
color 0A

echo =======================================================================
echo          KHỞI ĐỘNG HỆ THỐNG MẠNG SDN MININET (UBUNTU WSL)
echo =======================================================================
echo.

:: 1. Kiểm tra môi trường Mininet trong WSL
echo [*] Đang kiểm tra môi trường trong WSL (Ubuntu-22.04)...
wsl -d Ubuntu-22.04 -u root bash -c "which mn >/dev/null 2>&1"
if %errorlevel% neq 0 (
    echo.
    echo [CANH BAO] Mininet chưa được cài đặt trong WSL!
    echo Vui lòng chạy file 'cai_dat_wsl.bat' trước để cài đặt tự động.
    echo.
    pause
    exit /b 1
)

:: 2. Khởi động dịch vụ Open vSwitch
echo [*] 1/4. Đang bật dịch vụ Open vSwitch...
wsl -d Ubuntu-22.04 -u root bash -c "service openvswitch-switch start >/dev/null 2>&1"

:: 3. Dọn dẹp switch rác trước khi chạy
echo [*] 2/4. Dọn dẹp các switch ảo còn sót lại từ lần trước (mn -c)...
wsl -d Ubuntu-22.04 -u root bash -c "mn -c >/dev/null 2>&1"

:: 4. Mở cửa sổ riêng cho Ryu Controller nếu có file controller.py
echo [*] 3/4. Đang khởi động Ryu Controller ở cửa sổ riêng biệt...
start "SDN Ryu Controller" cmd /k "wsl -d Ubuntu-22.04 -u root bash -c 'cd /mnt/d/Project/SDN_ML_Project && echo === RYU CONTROLLER DANG LANG NGHE TAI PORT 6653 === && ryu-manager --observe-links controller.py'"

:: Đợi 3 giây để Controller khởi động hoàn tất
echo [*] Đợi Controller sẵn sàng...
timeout /t 3 /nobreak > nul

:: 5. Khởi động Mininet Topology trong cửa sổ này
echo.
echo =======================================================================
echo   [*] 4/4. ĐANG BẬT MẠNG 6 SWITCH (topology.py)...
echo -----------------------------------------------------------------------
echo   Khi vào dấu nhắc 'mininet>', bạn có thể gõ:
echo     - pingall           : Kiểm tra thông mạng giữa tất cả các máy
echo     - h1 ping -c 4 h2   : Kiểm tra ping từ h1 sang h2
echo     - iperf h1 h2       : Đo băng thông thực tế đường truyền
echo.
echo   Để THOÁT Mininet an toàn: gõ lệnh 'exit'
echo =======================================================================
echo.

wsl -d Ubuntu-22.04 -u root bash -c "cd /mnt/d/Project/SDN_ML_Project && python3 topology.py"

:: 6. Tự động dọn dẹp sau khi thoát
echo.
echo =======================================================================
echo [*] Đã thoát Mininet. Đang tự động dọn dẹp hệ thống an toàn...
wsl -d Ubuntu-22.04 -u root bash -c "mn -c >/dev/null 2>&1; killall -9 ryu-manager iperf iperf3 2>/dev/null || true"
taskkill /FI "WINDOWTITLE eq SDN Ryu Controller*" /F >nul 2>&1
echo [*] Đã dọn dẹp sạch sẽ tài nguyên mạng ảo!
echo =======================================================================
pause
