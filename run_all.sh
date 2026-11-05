#!/usr/bin/env bash
# ==============================================================================
# SCRIPT CHẠY TOÀN BỘ HỆ THỐNG SDN + ML QoS (UBUNTU VM)
# Tự động khởi động Controller, ML Service, Web Dashboard và Topology Mininet
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "================================================================================"
echo "KHỞI ĐỘNG HỆ THỐNG GIÁM SÁT QoS VÀ ĐIỀU PHỐI LƯU LƯỢNG MẠNG THÍCH ỨNG SDN"
echo "================================================================================"

# Dọn dẹp switch ảo Mininet còn sót
echo ">>> [1/5] Dọn dẹp môi trường Mininet cũ..."
sudo mn -c > /dev/null 2>&1 || true

# Khởi động dịch vụ học máy ML REST API
echo ">>> [2/5] Khởi động Dịch vụ Học máy (ML REST API) tại cổng 5001..."
python3 ml_engine/ml_service.py > /dev/null 2>&1 &
ML_PID=$!

# Khởi động Web Dashboard
echo ">>> [3/5] Khởi động Web Dashboard tại http://localhost:5000..."
python3 dashboard/app.py > /dev/null 2>&1 &
DASH_PID=$!

# Khởi động Ryu SDN Controller
echo ">>> [4/5] Khởi động Ryu Controller (OpenFlow 1.3)..."
ryu-manager --observe-links controller.py > /dev/null 2>&1 &
RYU_PID=$!

sleep 3

# Hàm dọn dẹp khi bấm Ctrl+C hoặc thoát
cleanup() {
    echo ""
    echo ">>> Đang tắt toàn bộ tiến trình hệ thống..."
    kill -9 $ML_PID 2>/dev/null || true
    kill -9 $DASH_PID 2>/dev/null || true
    kill -9 $RYU_PID 2>/dev/null || true
    sudo mn -c > /dev/null 2>&1 || true
    echo ">>> Đã dừng hệ thống thành công."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Khởi động Topology mạng Mininet 6 Switch
echo ">>> [5/5] Khởi động mạng Mininet 6 switch..."
echo "--------------------------------------------------------------------------------"
echo "Mở trình duyệt truy cập Web Dashboard: http://localhost:5000"
echo "Trên Mininet CLI, bạn có thể chạy kịch bản thử nghiệm: py exec(open('experiments/traffic_generator.py').read())"
echo "--------------------------------------------------------------------------------"
sudo python3 topology.py
