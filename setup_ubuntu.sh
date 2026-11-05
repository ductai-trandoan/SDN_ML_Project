#!/usr/bin/env bash
# ==============================================================================
# SCRIPT CÀI ĐẶT MÔI TRƯỜNG CHO HỆ THỐNG SDN + ML (UBUNTU VM)
# Cài đặt Mininet, Open vSwitch, Ryu SDN, Python dependencies
# ==============================================================================

set -e

echo "================================================================================"
echo "BẮT ĐẦU CÀI ĐẶT MÔI TRƯỜNG SDN VÀ HỌC MÁY TRÊN UBUNTU"
echo "================================================================================"

sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch openvswitch-testcontroller \
    iperf iproute2 net-tools git python3 python3-pip python3-dev build-essential

# Cài đặt các thư viện Python cần thiết
pip3 install --upgrade pip
pip3 install ryu eventlet==0.30.2 scikit-learn pandas numpy joblib flask

# Kiểm tra Mininet
echo ">>> Kiểm tra hoạt động Mininet..."
sudo mn --test pingall

echo "================================================================================"
echo "CÀI ĐẶT HOÀN TẤT! Bạn có thể khởi động hệ thống bằng: ./run_all.sh"
echo "================================================================================"
