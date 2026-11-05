"""
BỘ SINH DỮ LIỆU HUẤN LUYỆN VÀ ĐÁNH GIÁ MÔ HÌNH HỌC MÁY (SDN QoS)
Tuân thủ thiết kế:
- Bảng 2.4: Cấu trúc bảng link_metrics
- Mục 2.5.2: Quy ước gán nhãn (label_now và label_pred với H = 5s)
- Mục 1.4.2: Đặc trưng tức thời và đặc trưng trượt theo thời gian
- Bảng 1.5: Sáu kịch bản thực nghiệm K1 đến K6
"""

import numpy as np
import pandas as pd
import os
import sys
from datetime import datetime, timedelta

# Import config và DatabaseManager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    DB_PATH, CONGESTION_UTIL_THRESHOLD, CONGESTION_LOSS_THRESHOLD, 
    PREDICTION_HORIZON, MONITOR_INTERVAL
)
from database.db_manager import DatabaseManager

def generate_scenario_telemetry(scenario_id, num_samples=600, base_time=None):
    """
    Sinh chuỗi dữ liệu đo đạc mô phỏng theo từng kịch bản cụ thể (Bảng 1.5)
    """
    if base_time is None:
        base_time = datetime.now() - timedelta(seconds=num_samples * MONITOR_INTERVAL)
        
    records = []
    # Liên kết thử nghiệm chính là s2 -> s6 (trên đường P1, dung lượng 10 Mbps)
    src_dpid, dst_dpid = 2, 6
    capacity_mbps = 10.0
    
    # Khởi tạo giá trị ban đầu
    current_tp = 2.0
    current_latency = 5.0
    current_jitter = 1.0
    current_loss = 0.0

    for i in range(num_samples):
        t = base_time + timedelta(seconds=i * MONITOR_INTERVAL)
        
        if scenario_id == 'K1':
            # K1: Mạng bình thường, tải nhẹ (iperf 1-3.5 Mbps)
            current_tp = np.clip(np.random.normal(2.5, 0.4), 0.5, 4.0)
            current_latency = np.clip(np.random.normal(5.2, 0.5), 4.5, 8.0)
            current_jitter = np.clip(np.random.normal(0.8, 0.2), 0.2, 2.0)
            current_loss = 0.0 if np.random.rand() > 0.02 else np.random.uniform(0.01, 0.1)

        elif scenario_id == 'K2':
            # K2: Tải tăng dần (từ 2 Mbps lên đến 12 Mbps)
            progress = i / float(num_samples)
            trend_tp = 2.0 + progress * 8.5 # tăng dần từ 2 lên ~10.5 Mbps
            current_tp = np.clip(np.random.normal(trend_tp, 0.3), 1.0, 11.0)
            # Khi tải vượt 80% (8Mbps), latency và loss bắt đầu tăng phi tuyến
            if current_tp >= 8.0:
                current_latency = np.clip(5.0 + (current_tp - 8.0) * 15.0 + np.random.normal(0, 3.0), 5.0, 75.0)
                current_loss = np.clip((current_tp - 8.0) * 1.5 + np.random.normal(0, 0.5), 0.0, 10.0)
                current_jitter = np.clip(1.0 + (current_tp - 8.0) * 3.0, 0.5, 12.0)
            else:
                current_latency = np.clip(np.random.normal(5.5, 0.5), 4.5, 9.0)
                current_loss = 0.0
                current_jitter = np.clip(np.random.normal(0.9, 0.2), 0.2, 2.5)

        elif scenario_id == 'K3':
            # K3: Tải đột biến (Spikes ngẫu nhiên trong khoảng ngắn 5-10s)
            in_spike = (150 <= i <= 180) or (350 <= i <= 375) or (500 <= i <= 520)
            if in_spike:
                current_tp = np.clip(np.random.normal(9.6, 0.4), 8.5, 10.8)
                current_latency = np.clip(np.random.normal(55.0, 8.0), 30.0, 95.0)
                current_loss = np.clip(np.random.normal(4.0, 1.0), 2.1, 8.5)
                current_jitter = np.clip(np.random.normal(9.0, 2.0), 4.0, 16.0)
            else:
                current_tp = np.clip(np.random.normal(2.8, 0.5), 1.0, 4.5)
                current_latency = np.clip(np.random.normal(5.3, 0.6), 4.5, 8.5)
                current_loss = 0.0
                current_jitter = np.clip(np.random.normal(0.8, 0.2), 0.2, 2.0)

        elif scenario_id == 'K4':
            # K4: Nghẽn một liên kết s2-s6 (tải nền h3->h4 đẩy tải lên 8.5 - 9.8 Mbps)
            current_tp = np.clip(np.random.normal(9.2, 0.4), 8.2, 10.2)
            current_latency = np.clip(np.random.normal(65.0, 10.0), 40.0, 110.0)
            current_loss = np.clip(np.random.normal(3.8, 1.2), 2.0, 9.5)
            current_jitter = np.clip(np.random.normal(8.5, 2.2), 3.5, 18.0)

        elif scenario_id == 'K5':
            # K5: Suy giảm chất lượng phi tải (tc netem làm trễ tăng 50ms, mất gói 3-6%)
            current_tp = np.clip(np.random.normal(4.5, 0.8), 2.0, 6.0) # Băng thông bình thường
            current_latency = np.clip(np.random.normal(58.0, 6.0), 45.0, 85.0) # Trễ cao
            current_loss = np.clip(np.random.normal(4.2, 1.0), 2.5, 7.8) # Mất gói cao
            current_jitter = np.clip(np.random.normal(7.5, 1.5), 3.0, 14.0)

        elif scenario_id == 'K6':
            # K6: Đứt liên kết tạm thời (link failure từ i=200 đến i=230)
            if 200 <= i <= 230:
                current_tp = 0.0
                current_latency = 999.0
                current_loss = 100.0
                current_jitter = 0.0
            else:
                current_tp = np.clip(np.random.normal(3.0, 0.5), 1.0, 5.0)
                current_latency = np.clip(np.random.normal(5.4, 0.6), 4.5, 8.0)
                current_loss = 0.0
                current_jitter = np.clip(np.random.normal(0.8, 0.2), 0.2, 2.0)

        utilization_pct = min(100.0, (current_tp / capacity_mbps) * 100.0)
        
        # Gán nhãn label_now theo mục 2.5.2
        label_now = 1 if (utilization_pct >= CONGESTION_UTIL_THRESHOLD or current_loss >= CONGESTION_LOSS_THRESHOLD) else 0

        records.append({
            'ts': t.strftime("%Y-%m-%d %H:%M:%S"),
            'src_dpid': src_dpid,
            'dst_dpid': dst_dpid,
            'capacity_mbps': capacity_mbps,
            'throughput_mbps': round(float(current_tp), 3),
            'utilization_pct': round(float(utilization_pct), 2),
            'latency_ms': round(float(current_latency), 2),
            'jitter_ms': round(float(current_jitter), 2),
            'loss_pct': round(float(current_loss), 2),
            'scenario_id': scenario_id,
            'label_now': label_now
        })

    df = pd.DataFrame(records)

    # Gán nhãn label_pred với H = 5s (mục 2.5.2)
    # label_pred(t) = 1 nếu tồn tại thời điểm nghẽn trong (t, t + H]
    H_steps = int(PREDICTION_HORIZON / MONITOR_INTERVAL)
    # Dùng rolling max đảo ngược (reversed) để xem tương lai
    future_congestion = df['label_now'].iloc[::-1].rolling(window=H_steps, min_periods=1).max().iloc[::-1]
    # Dịch chuyển 1 bước để không tính chính thời điểm t (trong khoảng (t, t + H])
    df['label_pred'] = future_congestion.shift(-1).fillna(0).astype(int)

    return df

def add_time_series_features(df, window_size=5):
    """
    Tạo các đặc trưng chuỗi thời gian (Rolling features) theo mục 1.4.2 của Báo cáo:
    - Trung bình trượt (rolling mean)
    - Độ lệch chuẩn trượt (rolling std)
    - Giá trị lớn nhất (rolling max)
    - Tốc độ thay đổi (difference)
    """
    df = df.copy()
    
    # 1. Trung bình trượt & Độ lệch chuẩn mức sử dụng
    df['util_rolling_mean'] = df['utilization_pct'].rolling(window=window_size, min_periods=1).mean()
    df['util_rolling_std'] = df['utilization_pct'].rolling(window=window_size, min_periods=1).std().fillna(0)
    df['util_rolling_max'] = df['utilization_pct'].rolling(window=window_size, min_periods=1).max()
    
    # 2. Tốc độ thay đổi mức sử dụng (diff)
    df['util_diff'] = df['utilization_pct'].diff().fillna(0)
    
    # 3. Đặc trưng trượt độ trễ và mất gói
    df['latency_rolling_mean'] = df['latency_ms'].rolling(window=window_size, min_periods=1).mean()
    df['latency_rolling_max'] = df['latency_ms'].rolling(window=window_size, min_periods=1).max()
    df['loss_rolling_mean'] = df['loss_pct'].rolling(window=window_size, min_periods=1).mean()
    
    return df

def generate_full_dataset(samples_per_scenario=600, save_to_db=True):
    """
    Sinh toàn bộ dữ liệu gồm 6 kịch bản K1 - K6 và lưu vào file CSV / SQLite DB
    """
    print(f">>> Đang sinh dữ liệu thực nghiệm cho 6 kịch bản K1 - K6 (mỗi kịch bản {samples_per_scenario} mẫu)...")
    all_dfs = []
    scenarios = ['K1', 'K2', 'K3', 'K4', 'K5', 'K6']
    
    base_time = datetime.now() - timedelta(seconds=samples_per_scenario * len(scenarios) * MONITOR_INTERVAL)
    
    for idx, sc in enumerate(scenarios):
        sc_time = base_time + timedelta(seconds=idx * samples_per_scenario * MONITOR_INTERVAL)
        df_sc = generate_scenario_telemetry(sc, num_samples=samples_per_scenario, base_time=sc_time)
        df_sc = add_time_series_features(df_sc)
        all_dfs.append(df_sc)
        print(f"  + Kịch bản {sc}: {len(df_sc)} mẫu, Nghẽn tức thời (label_now=1): {df_sc['label_now'].sum()}, Dự đoán nghẽn (label_pred=1): {df_sc['label_pred'].sum()}")

    full_df = pd.concat(all_dfs, ignore_index=True)
    
    # Lưu ra file CSV trong ml_engine
    out_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(out_dir, "dataset_qos.csv")
    full_df.to_csv(csv_path, index=False)
    print(f">>> Đã xuất bộ dữ liệu thành công: {csv_path} (Tổng cộng: {len(full_df)} dòng)")

    # Lưu vào SQLite Database nếu được yêu cầu
    if save_to_db:
        print(">>> Đang nạp dữ liệu vào cơ sở dữ liệu SQLite (bảng link_metrics)...")
        db = DatabaseManager()
        # Chèn các bản ghi theo cấu trúc Bảng 2.4
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for _, row in full_df.iterrows():
                cursor.execute('''
                    INSERT INTO link_metrics (ts, src_dpid, dst_dpid, capacity_mbps, throughput_mbps,
                                             utilization_pct, latency_ms, jitter_ms, loss_pct, scenario_id, label_now, label_pred)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (row['ts'], row['src_dpid'], row['dst_dpid'], row['capacity_mbps'], row['throughput_mbps'],
                      row['utilization_pct'], row['latency_ms'], row['jitter_ms'], row['loss_pct'], 
                      row['scenario_id'], int(row['label_now']), int(row['label_pred'])))
            conn.commit()
        print(">>> Đã đồng bộ thành công vào SQLite DB.")

    return full_df

if __name__ == '__main__':
    generate_full_dataset(samples_per_scenario=600, save_to_db=True)
