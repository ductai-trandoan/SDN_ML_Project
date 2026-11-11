"""
MODULE TRÍCH XUẤT DỮ LIỆU TELEMETRY THỰC TẾ TỪ SQLITE RA TẬP DATASET HUẤN LUYỆN
Thuộc phân hệ: Xử lý dữ liệu & Machine Learning Pipeline (Phần của bạn Tài)
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, CONGESTION_UTIL_THRESHOLD, CONGESTION_LOSS_THRESHOLD, PREDICTION_HORIZON

def export_telemetry_to_dataset(db_path=DB_PATH, output_csv="dataset_real_qos.csv"):
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(cur_dir, output_csv)

    print("=" * 75)
    print("PIPELINE TRÍCH XUẤT VÀ XỬ LÝ DỮ LIỆU THỰC NGHIỆM TỪ SQLITE (SDN QoS)")
    print("=" * 75)
    print(f">>> Đang kết nối tới cơ sở dữ liệu: {db_path}")

    if not os.path.exists(db_path):
        print(f"!!! CẢNH BÁO: Không tìm thấy file {db_path}.")
        return None

    conn = sqlite3.connect(db_path)
    query = """
    SELECT 
        id, ts, src_dpid, dst_dpid, capacity_mbps, 
        throughput_mbps, latency_ms, jitter_ms, loss_pct, scenario_id
    FROM link_metrics
    ORDER BY src_dpid, dst_dpid, id ASC
    """
    
    try:
        df_raw = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"!!! Lỗi khi đọc dữ liệu từ database: {e}")
        conn.close()
        return None
    finally:
        conn.close()

    total_records = len(df_raw)
    print(f">>> Đã đọc thành công {total_records} bản ghi telemetry từ bảng link_metrics.")

    if total_records == 0:
        print("!!! Database hiện chưa có bản ghi nào.")
        return None

    # 1. Tính toán mức sử dụng băng thông (utilization_pct)
    df_raw['utilization_pct'] = (df_raw['throughput_mbps'] / df_raw['capacity_mbps'].replace(0, 10.0)) * 100.0
    df_raw['utilization_pct'] = df_raw['utilization_pct'].clip(0.0, 100.0)

    # 2. Xử lý đặc trưng trượt theo từng liên kết (src_dpid, dst_dpid) độc lập
    processed_dfs = []
    window = 5 # Cửa sổ trượt W = 5 giây
    h_steps = int(PREDICTION_HORIZON)

    for (src, dst), group in df_raw.groupby(['src_dpid', 'dst_dpid']):
        g = group.sort_values(by='id').copy()
        
        # Đặc trưng chuỗi thời gian
        g['util_rolling_mean'] = g['utilization_pct'].rolling(window, min_periods=1).mean()
        g['util_rolling_std'] = g['utilization_pct'].rolling(window, min_periods=1).std().fillna(0.0)
        g['util_rolling_max'] = g['utilization_pct'].rolling(window, min_periods=1).max()
        g['util_diff'] = g['utilization_pct'].diff().fillna(0.0)
        
        g['latency_rolling_mean'] = g['latency_ms'].rolling(window, min_periods=1).mean()
        g['latency_rolling_max'] = g['latency_ms'].rolling(window, min_periods=1).max()
        g['loss_rolling_mean'] = g['loss_pct'].rolling(window, min_periods=1).mean()

        # 3. Gán nhãn bài toán 1: Nghẽn tức thời tại t (label_now)
        g['label_now'] = ((g['utilization_pct'] >= CONGESTION_UTIL_THRESHOLD) | 
                          (g['loss_pct'] >= CONGESTION_LOSS_THRESHOLD)).astype(int)

        # 4. Gán nhãn bài toán 2: Dự đoán nguy cơ trong H = 5s kế tiếp (label_pred)
        # Đảo ngược chuỗi -> tính rolling max h_steps mẫu -> đảo ngược lại
        g['label_pred'] = g['label_now'].iloc[::-1].rolling(window=h_steps, min_periods=1).max().iloc[::-1].astype(int)

        processed_dfs.append(g)

    df_final = pd.concat(processed_dfs, ignore_index=True)
    
    # Làm tròn số liệu
    df_final['throughput_mbps'] = df_final['throughput_mbps'].round(3)
    df_final['utilization_pct'] = df_final['utilization_pct'].round(2)
    df_final['latency_ms'] = df_final['latency_ms'].round(2)
    df_final['jitter_ms'] = df_final['jitter_ms'].round(2)
    df_final['loss_pct'] = df_final['loss_pct'].round(2)
    df_final['util_rolling_mean'] = df_final['util_rolling_mean'].round(2)
    df_final['util_rolling_std'] = df_final['util_rolling_std'].round(2)
    df_final['util_rolling_max'] = df_final['util_rolling_max'].round(2)
    df_final['util_diff'] = df_final['util_diff'].round(2)
    df_final['latency_rolling_mean'] = df_final['latency_rolling_mean'].round(2)
    df_final['latency_rolling_max'] = df_final['latency_rolling_max'].round(2)
    df_final['loss_rolling_mean'] = df_final['loss_rolling_mean'].round(2)

    df_final.to_csv(out_path, index=False, encoding='utf-8')

    congested_now_count = int(df_final['label_now'].sum())
    congested_pred_count = int(df_final['label_pred'].sum())

    print(f"\n>>> XỬ LÝ HOÀN TẤT VÀ ĐÃ XUẤT RA: {out_path}")
    print(f"  + Tổng số mẫu: {len(df_final)}")
    print(f"  + Số mẫu nghẽn tức thời (label_now=1): {congested_now_count} ({congested_now_count/len(df_final)*100:.1f}%)")
    print(f"  + Số mẫu cảnh báo sớm H=5s (label_pred=1): {congested_pred_count} ({congested_pred_count/len(df_final)*100:.1f}%)")
    print("=" * 75)
    return out_path

if __name__ == '__main__':
    export_telemetry_to_dataset()
