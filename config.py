"""
CẤU HÌNH HỆ THỐNG GIÁM SÁT QoS VÀ ĐIỀU PHỐI LƯU LƯỢNG MẠNG THÍCH ỨNG (SDN + ML)
Dựa theo Báo cáo định kỳ Đợt 1 - ĐATN
"""
import os

# Đường dẫn thư mục gốc dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cấu hình Cơ sở dữ liệu SQLite
# Nếu chạy trong WSL (Linux), lưu DB tại /tmp/sdn_qos.db để tránh lỗi disk I/O error của /mnt/d (9P filesystem)
if os.name != 'nt' and os.path.exists('/tmp'):
    DB_PATH = "/tmp/sdn_qos.db"
else:
    DB_PATH = os.path.join(BASE_DIR, "database", "sdn_qos.db")

# Cấu hình REST API / Dịch vụ
ML_SERVICE_HOST = "127.0.0.1"
ML_SERVICE_PORT = 5001
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
RYU_REST_PORT = 8080

# Chu kỳ thu thập số liệu giám sát (giây) theo Báo cáo mục 2.5.2 (Δt = 1s)
MONITOR_INTERVAL = 1.0

# Thời gian dự đoán nghẽn tương lai H (giây) theo Báo cáo mục 2.5.2 (H = 5s)
PREDICTION_HORIZON = 5.0

# Ngưỡng nghẽn mạng (Báo cáo mục 2.5.2)
CONGESTION_UTIL_THRESHOLD = 80.0  # Mức sử dụng >= 80% là nghẽn
CONGESTION_LOSS_THRESHOLD = 2.0    # Tỉ lệ mất gói >= 2% là nghẽn

# Tham số cơ chế chống dao động tuyến (Anti-flapping) - Báo cáo mục 2.4 (Công thức 2.1)
# Cost(P_mới) < (1 - DELTA) * Cost(P_hiện_tại) và (t - t_chuyển >= T_HOLD)
ANTI_FLAP_DELTA = 0.15     # Biên độ cải thiện tối thiểu 15%
ANTI_FLAP_T_HOLD = 10.0    # Thời gian giữ tối thiểu 10 giây giữa 2 lần chuyển

# Trọng số chọn đường đa tiêu chí QoS - Báo cáo mục 1.5.3 (Công thức 1.9)
# w(e) = w1 * (d/d_max) + w2 * (j/j_max) + w3 * (l/l_max) + w4 * u
QOS_WEIGHTS = {
    'w_delay': 0.30,        # w1: độ trễ (latency)
    'w_jitter': 0.20,       # w2: jitter
    'w_loss': 0.30,         # w3: mất gói (packet loss)
    'w_util': 0.20          # w4: mức sử dụng băng thông (utilization)
}

# Giá trị chuẩn hóa tối đa cho các chỉ số QoS
NORM_MAX = {
    'latency_ms': 100.0,
    'jitter_ms': 20.0,
    'loss_pct': 10.0,
    'utilization_pct': 100.0
}

# Cấu hình Topology 6 Switch theo Báo cáo mục 2.3 (Bảng 2.3 & Hình 2.2)
# Switch IDs: s1=1, s2=2, s3=3, s4=4, s5=5, s6=6
DPID_MAP = {
    's1': 1,
    's2': 2,
    's3': 3,
    's4': 4,
    's5': 5,
    's6': 6
}

# Đặc tính 3 đường song song giữa s1 và s6 (Bảng 2.3)
PATHS_CONFIG = {
    'P1': {
        'name': 'P1 (Đường ngắn nhất / Ưu tiên trễ thấp)',
        'path': [1, 2, 6],
        'switches': ['s1', 's2', 's6'],
        'links': [(1, 2), (2, 6)],
        'capacity_mbps': 10.0,
        'nominal_delay_ms': 10.0,  # 5ms + 5ms
        'hops': 2,
        'description': 'Ít chặng nhất, trễ thấp nhất (10ms), 10Mbps. Bị tải nền từ h3-h4 đi qua s2-s6.'
    },
    'P2': {
        'name': 'P2 (Đường băng thông cao, trễ lớn)',
        'path': [1, 3, 4, 6],
        'switches': ['s1', 's3', 's4', 's6'],
        'links': [(1, 3), (3, 4), (4, 6)],
        'capacity_mbps': 10.0,
        'nominal_delay_ms': 30.0,  # 10ms + 10ms + 10ms
        'hops': 3,
        'description': '3 chặng, trễ 30ms, băng thông 10Mbps.'
    },
    'P3': {
        'name': 'P3 (Đường ít chặng, băng thông trung bình)',
        'path': [1, 5, 6],
        'switches': ['s1', 's5', 's6'],
        'links': [(1, 5), (5, 6)],
        'capacity_mbps': 5.0,
        'nominal_delay_ms': 20.0,  # 10ms + 10ms
        'hops': 2,
        'description': '2 chặng, trễ 20ms, băng thông 5Mbps.'
    }
}

# Cấu hình Host khớp 100% với thứ tự addLink trong topology.py và controller.py
HOSTS_CONFIG = {
    'h1': {'ip': '10.0.0.1', 'mac': '00:00:00:00:00:01', 'switch': 1, 'port': 1, 'role': 'Nguồn luồng chính (VoIP/Video)'},
    'h2': {'ip': '10.0.0.2', 'mac': '00:00:00:00:00:02', 'switch': 6, 'port': 1, 'role': 'Đích luồng chính'},
    'h3': {'ip': '10.0.0.3', 'mac': '00:00:00:00:00:03', 'switch': 2, 'port': 1, 'role': 'Tạo tải nền gây nghẽn'},
    'h4': {'ip': '10.0.0.4', 'mac': '00:00:00:00:00:04', 'switch': 6, 'port': 2, 'role': 'Đích tải nền'}
}

# Các kịch bản thực nghiệm K1 đến K6 theo Báo cáo Bảng 1.5
SCENARIOS = {
    'K1': 'Mạng bình thường, tải nhẹ (iperf 1-3 Mbps)',
    'K2': 'Tải tăng dần (từ 2 Mbps đến 12 Mbps qua s2-s6)',
    'K3': 'Tải đột biến (burst spike lên 15 Mbps)',
    'K4': 'Nghẽn một liên kết s2-s6 (tải nền h3->h4)',
    'K5': 'Suy giảm chất lượng (tăng trễ 50ms, mất gói 5%)',
    'K6': 'Đứt liên kết s2-s6 (kiểm tra khôi phục và chuyển hướng)'
}
