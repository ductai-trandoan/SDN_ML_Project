@echo off
chcp 65001 > nul
title SDN Mininet - Dọn dẹp & Tắt an toàn
color 0C

echo =======================================================================
echo           TẮT VÀ DỌN DẸP AN TOÀN HỆ THỐNG MININET & RYU
echo =======================================================================
echo.

echo [*] 1/4. Dừng toàn bộ tiến trình Ryu, Mininet, iperf trong WSL...
wsl -d Ubuntu-22.04 -u root bash -c "killall -9 ryu-manager python3 iperf iperf3 2>/dev/null || true"

echo [*] 2/4. Xóa sạch các switch ảo, cổng veth bị treo (mn -c)...
wsl -d Ubuntu-22.04 -u root bash -c "mn -c >/dev/null 2>&1"

echo [*] 3/4. Khởi động lại dịch vụ Open vSwitch để làm sạch bảng luồng...
wsl -d Ubuntu-22.04 -u root bash -c "service openvswitch-switch restart >/dev/null 2>&1"

echo [*] 4/4. Đóng các cửa sổ console Ryu Controller trên Windows...
taskkill /FI "WINDOWTITLE eq SDN Ryu Controller*" /F >nul 2>&1

echo.
echo =======================================================================
echo [OK] ĐÃ DỌN DẸP HOÀN TOÀN! HỆ THỐNG ĐÃ SẴN SÀNG CHO LẦN CHẠY TIẾP THEO.
echo =======================================================================
echo.
pause
