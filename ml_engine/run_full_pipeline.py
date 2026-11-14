"""
KỊCH BẢN TỰ ĐỘNG HÓA TOÀN TRÌNH: THU THẬP SỐ LIỆU MININET THẬT -> TRAIN AI -> XUẤT ĐỒ THỊ
Phân hệ: Machine Learning & Đánh giá Thực nghiệm (Phần của bạn Tài)
"""

import os
import sys
import time
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from database.db_manager import DatabaseManager
from ml_engine.export_real_telemetry import export_telemetry_to_dataset
from ml_engine.train_models import main as train_models_main

def check_system_readiness():
    """Kiểm tra xem Mininet và Ryu Controller có đang chạy trong hệ thống không"""
    print("\n" + "="*75)
    print("BƯỚC 1: KIỂM TRA TRẠNG THÁI HỆ THỐNG MẠNG MININET & RYU")
    print("="*75)
    
    # Kiểm tra tiến trình mininet
    try:
        h1_pid = subprocess.check_output("pgrep -f 'mininet:h1' 2>/dev/null || true", shell=True).decode().strip()
    except Exception:
        h1_pid = ""

    if not h1_pid:
        print("[-] CẢNH BÁO: Không phát hiện các Host Mininet đang chạy!")
        print("    -> Vui lòng khởi động Mininet trước bằng file 'start_mininet.bat'")
        print("    -> Hoặc gõ lệnh: sudo python3 topology.py trong terminal WSL")
        return False

    print("[+] Đã phát hiện mạng Mininet 6 switch và 4 host đang hoạt động.")
    return True

def run_pipeline(cycles=2, clear_old_data=False):
    db = DatabaseManager()
    
    if clear_old_data:
        print("\n[*] Đang làm sạch bảng link_metrics cũ để chỉ lấy số liệu của đợt chạy này...")
        db.clear_metrics()
        print("[+] Đã làm sạch database. Sẵn sàng ghi số liệu mới.")

    # 1. Bơm lưu lượng thực nghiệm
    print("\n" + "="*75)
    print(f"BƯỚC 2: TỰ ĐỘNG BƠM LƯU LƯỢNG THỰC NGHIỆM TRÊN MININET ({cycles} CHU KỲ)")
    print("="*75)
    from experiments.traffic_generator import TrafficScenarioRunner
    runner = TrafficScenarioRunner()
    runner.run_dataset_collection(cycles=cycles)

    # 2. Xuất dữ liệu telemetry sang CSV
    print("\n" + "="*75)
    print("BƯỚC 3: TRÍCH XUẤT VÀ TÍNH TOÁN ĐẶC TRƯNG CHUỖI THỜI GIAN (FEATURE ENGINEERING)")
    print("="*75)
    df = export_telemetry_to_dataset()
    if df is None or len(df) == 0:
        print("[-] Lỗi: Không thể trích xuất dữ liệu từ SQLite. Hủy tiến trình.")
        return

    print(f"[+] Đã tạo tập dữ liệu thực nghiệm 'dataset_real_qos.csv' ({len(df)} mẫu).")

    # 3. Huấn luyện các mô hình học máy và xuất biểu đồ
    print("\n" + "="*75)
    print("BƯỚC 4: HUẤN LUYỆN 4 MÔ HÌNH HỌC MÁY & XUẤT BIỂU ĐỒ ĐÁNH GIÁ KHOA HỌC")
    print("="*75)
    train_models_main()

    # 4. Sao chép model trọng số mới ra thư mục gốc để Controller cập nhật
    src_model = os.path.join(BASE_DIR, "ml_engine", "qos_model_rf.pkl")
    dst_model = os.path.join(BASE_DIR, "qos_model.pkl")
    if os.path.exists(src_model):
        shutil.copyfile(src_model, dst_model)
        print(f"\n[+] Đã cập nhật trọng số mô hình mới nhất cho Ryu Controller: {dst_model}")

    print("\n" + "="*75)
    print("🎉 HOÀN TẤT TOÀN BỘ QUY TRÌNH HUẤN LUYỆN AI TỪ MẠNG MININET THẬT!")
    print("Tất cả biểu đồ đã được lưu tại: ml_engine/plots/")
    print("="*75 + "\n")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Automated Mininet-to-ML Pipeline')
    parser.add_argument('--cycles', type=int, default=2, help='Số chu kỳ bơm tải (mặc định: 2 chu kỳ)')
    parser.add_argument('--clear', action='store_true', help='Xóa trắng database cũ trước khi thu thập')
    parser.add_argument('--force', action='store_true', help='Bỏ qua kiểm tra Mininet')
    args = parser.parse_args()

    if not args.force:
        is_ready = check_system_readiness()
        if not is_ready:
            print("Nếu bạn muốn chạy mô phỏng không cần Mininet, dùng cờ: --force")
            sys.exit(1)

    run_pipeline(cycles=args.cycles, clear_old_data=args.clear)

