"""
KỊCH BẢN CHẠY MÔ PHỎNG VÀ KIỂM THỬ TOÀN DIỆN HỆ THỐNG (MOCK SIMULATION TEST)
Chạy nền liên tục và phản hồi ĐỘNG theo kịch bản được chọn trên Web Dashboard:
- K1: Mạng bình thường, tải nhẹ
- K2: Tải tăng dần (kiểm tra tính năng dự đoán sớm H=5s của AI)
- K3: Tải đột biến (burst spike)
- K4: Nghẽn nặng liên kết s2-s6 do tải nền h3->h4
- K5: Suy giảm chất lượng phi tải (tc netem trễ +50ms, loss 4.5%)
- K6: Đứt liên kết s2-s6 (kiểm tra fast failover)
"""

import time
import os
import sys
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    PATHS_CONFIG, QOS_WEIGHTS, NORM_MAX, ANTI_FLAP_DELTA, ANTI_FLAP_T_HOLD,
    CONGESTION_UTIL_THRESHOLD, CONGESTION_LOSS_THRESHOLD
)
from database.db_manager import DatabaseManager

def calculate_mock_path_cost(path_name, current_qos_dict, active_path_name='P1'):
    """
    Tính chi phí đường dẫn chuẩn hóa theo số chặng và dung lượng băng thông khả dụng:
    Đảm bảo khi P1 nghẽn (K2, K3, K4, K5), P2 (10 Mbps) có chi phí tốt hơn P3 (5 Mbps).
    """
    path_cfg = PATHS_CONFIG[path_name]
    links = path_cfg['links']
    total_cost = 0.0
    w_d = QOS_WEIGHTS['w_delay']
    w_j = QOS_WEIGHTS['w_jitter']
    w_l = QOS_WEIGHTS['w_loss']
    w_u = QOS_WEIGHTS['w_util']

    # Dự phóng tải nếu luồng chính (2.5 Mbps) đi qua tuyến này
    is_current = (path_name == active_path_name)
    cap = path_cfg.get('capacity_mbps', 10.0)
    projected_add_util = 0.0 if is_current else (2.5 / cap) * 100.0

    for (u, v) in links:
        qos = current_qos_dict.get((u, v), {
            'latency': path_cfg['nominal_delay_ms'] / len(links),
            'jitter': 1.0,
            'loss': 0.0,
            'util': 5.0
        })
        eff_util = min(100.0, qos['util'] + projected_add_util)
        d_norm = min(1.0, qos['latency'] / NORM_MAX['latency_ms'])
        j_norm = min(1.0, qos['jitter'] / NORM_MAX['jitter_ms'])
        l_norm = min(1.0, qos['loss'] / NORM_MAX['loss_pct'])
        u_norm = min(1.0, eff_util / NORM_MAX['utilization_pct'])

        w_e = (w_d * d_norm) + (w_j * j_norm) + (w_l * l_norm) + (w_u * u_norm)
        total_cost += w_e

    avg_link_cost = total_cost / max(1, len(links))
    capacity_penalty = 0.08 if cap < 10.0 else 0.0
    return round(avg_link_cost + capacity_penalty, 4)

def run_simulation(duration_seconds=3600):
    print("=" * 75)
    print("KHỞI ĐỘNG BỘ ĐIỀU PHỐI MÔ PHỎNG THỜI GIAN THỰC (ĐỒNG BỘ DASHBOARD)")
    print("=" * 75)

    db = DatabaseManager()
    active_path_name = 'P1'
    last_reroute_time = 0.0
    k2_step = 0
    k3_step = 0

    db.set_system_status('active_path', active_path_name)

    step = 0
    while step < duration_seconds:
        step += 1
        current_time = time.time()
        
        # Đọc kịch bản HIỆN TẠI trực tiếp từ Database (khi người dùng ấn nút trên Dashboard)
        sc_id = db.get_system_status('current_scenario', 'K1')

        # Mô phỏng trạng thái các liên kết
        qos_state = {}

        # -------------------------------------------------------------
        # 1. Liên kết then chốt s2 - s6 (nơi diễn ra các kịch bản thực nghiệm)
        # -------------------------------------------------------------
        if sc_id == 'K1':
            # K1: Mạng bình thường, tải nhẹ
            s2_s6_util = np.clip(np.random.normal(25.0, 2.5), 15.0, 35.0)
            s2_s6_tp = (s2_s6_util / 100.0) * 10.0
            s2_s6_lat = np.clip(np.random.normal(5.2, 0.3), 4.8, 6.5)
            s2_s6_jit = np.clip(np.random.normal(0.8, 0.2), 0.3, 1.5)
            s2_s6_loss = 0.0
            label_now = 0
            k2_step = 0

        elif sc_id == 'K2':
            # K2: Tải tăng dần từng giây (kiểm tra khả năng phát hiện sớm của AI)
            k2_step = (k2_step + 1) % 40
            trend = 25.0 + (k2_step / 40.0) * 70.0 # Tăng dần từ 25% lên 95%
            s2_s6_util = np.clip(np.random.normal(trend, 2.0), 10.0, 98.0)
            s2_s6_tp = (s2_s6_util / 100.0) * 10.0
            if s2_s6_util >= 80.0:
                s2_s6_lat = 5.0 + (s2_s6_util - 80.0) * 3.0
                s2_s6_jit = 1.0 + (s2_s6_util - 80.0) * 0.5
                s2_s6_loss = (s2_s6_util - 80.0) * 0.4
                label_now = 1
            else:
                s2_s6_lat = 5.2
                s2_s6_jit = 0.9
                s2_s6_loss = 0.0
                label_now = 0

        elif sc_id == 'K3':
            # K3: Tải đột biến (Spike ngẫu nhiên trong vài giây)
            k3_step = (k3_step + 1) % 15
            in_burst = (5 <= k3_step <= 10)
            if in_burst:
                s2_s6_util = np.clip(np.random.normal(96.0, 2.0), 90.0, 99.0)
                s2_s6_tp = 9.6
                s2_s6_lat = 72.0
                s2_s6_jit = 9.5
                s2_s6_loss = 4.8
                label_now = 1
            else:
                s2_s6_util = np.clip(np.random.normal(25.0, 2.0), 15.0, 35.0)
                s2_s6_tp = 2.5
                s2_s6_lat = 5.2
                s2_s6_jit = 0.8
                s2_s6_loss = 0.0
                label_now = 0

        elif sc_id == 'K4':
            # K4: Nghẽn nặng liên tục do tải nền h3 -> h4
            s2_s6_util = np.clip(np.random.normal(93.0, 2.5), 87.0, 98.5)
            s2_s6_tp = (s2_s6_util / 100.0) * 10.0
            s2_s6_lat = np.clip(np.random.normal(68.0, 6.0), 50.0, 88.0)
            s2_s6_jit = np.clip(np.random.normal(8.5, 1.2), 5.5, 14.0)
            s2_s6_loss = np.clip(np.random.normal(4.6, 0.8), 2.8, 7.5)
            label_now = 1

        elif sc_id == 'K5':
            # K5: Suy giảm chất lượng phi tải (tc netem trễ +50ms, loss 4.5%)
            s2_s6_util = np.clip(np.random.normal(42.0, 3.0), 30.0, 55.0) # Băng thông bình thường
            s2_s6_tp = (s2_s6_util / 100.0) * 10.0
            s2_s6_lat = np.clip(np.random.normal(62.0, 4.0), 52.0, 75.0) # Trễ cao
            s2_s6_jit = np.clip(np.random.normal(7.8, 1.0), 4.5, 12.0)
            s2_s6_loss = np.clip(np.random.normal(4.5, 0.6), 3.0, 6.5) # Mất gói cao
            label_now = 1 # Coi là nghẽn vì loss >= 2%

        elif sc_id == 'K6':
            # K6: Đứt liên kết s2-s6
            s2_s6_util = 0.0
            s2_s6_tp = 0.0
            s2_s6_lat = 999.0
            s2_s6_jit = 0.0
            s2_s6_loss = 100.0
            label_now = 1

        qos_state[(2, 6)] = {
            'tp': s2_s6_tp, 'util': s2_s6_util, 'latency': s2_s6_lat,
            'jitter': s2_s6_jit, 'loss': s2_s6_loss
        }

        batch_metrics = []
        batch_metrics.append({
            'ts': time.strftime("%Y-%m-%d %H:%M:%S"),
            'src_dpid': 2, 'dst_dpid': 6, 'capacity_mbps': 10.0,
            'throughput_mbps': s2_s6_tp, 'utilization_pct': s2_s6_util,
            'latency_ms': s2_s6_lat, 'jitter_ms': s2_s6_jit, 'loss_pct': s2_s6_loss,
            'scenario_id': sc_id, 'label_now': label_now, 'label_pred': 0
        })

        # -------------------------------------------------------------
        # 2. Các liên kết còn lại (P2: s1-s3, s3-s4, s4-s6; P3: s1-s5, s5-s6)
        # -------------------------------------------------------------
        other_links = [
            ((1, 2), 10.0, 5.0),
            ((1, 3), 10.0, 10.0), ((3, 4), 10.0, 10.0), ((4, 6), 10.0, 10.0),
            ((1, 5), 5.0, 10.0), ((5, 6), 5.0, 10.0)
        ]
        for (u, v), cap, nominal_d in other_links:
            u_pct = np.clip(np.random.normal(18.0, 2.0), 8.0, 28.0)
            tp = (u_pct / 100.0) * cap
            lat = nominal_d + np.random.uniform(-0.3, 0.4)
            jit = np.random.uniform(0.5, 1.2)
            qos_state[(u, v)] = {'tp': tp, 'util': u_pct, 'latency': lat, 'jitter': jit, 'loss': 0.0}
            batch_metrics.append({
                'ts': time.strftime("%Y-%m-%d %H:%M:%S"),
                'src_dpid': u, 'dst_dpid': v, 'capacity_mbps': cap,
                'throughput_mbps': tp, 'utilization_pct': u_pct,
                'latency_ms': lat, 'jitter_ms': jit, 'loss_pct': 0.0,
                'scenario_id': sc_id, 'label_now': 0, 'label_pred': 0
            })

        # Chèn hàng loạt 1 lần duy nhất cực nhanh
        db.insert_link_metrics_batch(batch_metrics)

        # -------------------------------------------------------------
        # 3. Thuật toán Đa tiêu chí QoS & Chống dao động tuyến (Mục 1.5.3 & 2.4)
        # -------------------------------------------------------------
        current_cost = calculate_mock_path_cost(active_path_name, qos_state, active_path_name)
        
        # Đánh giá 3 đường ứng viên P1, P2, P3
        candidate_costs = {}
        for p_name in ['P1', 'P2', 'P3']:
            candidate_costs[p_name] = calculate_mock_path_cost(p_name, qos_state, active_path_name)

        best_path = min(candidate_costs, key=candidate_costs.get)
        min_cost = candidate_costs[best_path]

        # Thời gian giữ tối thiểu trong chế độ demo (3.5s để quan sát nhanh nhạy)
        DEMO_T_HOLD = 3.5
        threshold_cost = (1.0 - ANTI_FLAP_DELTA) * current_cost
        can_switch_time = (current_time - last_reroute_time) >= DEMO_T_HOLD

        reroute_action = ""
        if best_path != active_path_name and min_cost < threshold_cost:
            if can_switch_time:
                old_p = active_path_name
                active_path_name = best_path
                last_reroute_time = current_time
                db.set_system_status('active_path', active_path_name)
                
                reason = f"[{sc_id}] Kích hoạt điều phối. Tải s2-s6={s2_s6_util:.1f}%, Loss={s2_s6_loss:.1f}%. Chi phí {old_p} ({current_cost:.3f}) > {best_path} ({min_cost:.3f})"
                db.log_reroute_event(
                    flow_id="h1_to_h2",
                    old_path=PATHS_CONFIG[old_p]['path'],
                    new_path=PATHS_CONFIG[best_path]['path'],
                    trigger_reason=reason,
                    cost_old=current_cost,
                    cost_new=min_cost
                )
                reroute_action = f"===> [CHUYỂN TUYẾN: {old_p} ➔ {best_path} (Chi phí giảm {((current_cost-min_cost)/current_cost)*100:.1f}%)]"
            else:
                remaining = ANTI_FLAP_T_HOLD - (current_time - last_reroute_time)
                reroute_action = f"[CHỐNG DAO ĐỘNG] Chặn chuyển tuyến do chưa qua T_giữ (còn {remaining:.1f}s)"

        print(f"[{step:03d}s] Kịch bản: {sc_id:<2} | s2-s6 Util: {s2_s6_util:>5.1f}% | Loss: {s2_s6_loss:>4.1f}% | Đường: {active_path_name} (Cost: {current_cost:.3f}) {reroute_action}")
        time.sleep(1)

if __name__ == '__main__':
    run_simulation(duration_seconds=3600)
