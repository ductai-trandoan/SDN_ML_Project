@echo off
chcp 65001 > nul
title Cài đặt môi trường Mininet & Ryu SDN trên WSL
color 0E

echo =======================================================================
echo     CÀI ĐẶT MÔI TRƯỜNG MININET & RYU SDN CHO UBUNTU-22.04 (WSL)
echo =======================================================================
echo.
echo Script này sẽ tự động cài vào WSL:
echo   1. Mininet & Open vSwitch
echo   2. iperf, iproute2, net-tools
echo   3. Ryu SDN Controller & các thư viện Python
echo.
echo Bấm phím bất kỳ để bắt đầu cài đặt...
pause > nul

echo.
echo [*] Đang cài đặt gói hệ thống (sẽ mất khoảng 1-2 phút tùy tốc độ mạng)...
wsl -d Ubuntu-22.04 -u root bash -c "cd /mnt/d/Project/SDN_ML_Project && bash setup_ubuntu.sh"

echo.
echo =======================================================================
echo [OK] ĐÃ CÀI ĐẶT XONG! Bạn có thể chạy file 'start_mininet.bat'.
echo =======================================================================
echo.
pause
