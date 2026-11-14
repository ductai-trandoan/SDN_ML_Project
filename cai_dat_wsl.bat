@echo off
title Cai dat moi truong Mininet va Ryu SDN tren WSL
color 0E

echo =======================================================================
echo     CAI DAT MOI TRUONG MININET VA RYU SDN CHO UBUNTU-22.04 (WSL)
echo =======================================================================
echo.
echo Qua trinh nay se cai vao WSL:
echo   - Mininet va Open vSwitch
echo   - iperf, iproute2, net-tools
echo   - Ryu SDN Controller va cac thu vien Python
echo.
pause

wsl -d Ubuntu-22.04 -u root bash -c "cd /mnt/d/Project/SDN_ML_Project && bash setup_ubuntu.sh"

echo.
echo =======================================================================
echo [OK] DA CAI DAT XONG! Ban co the chay 'start.bat'.
echo =======================================================================
echo.
pause
