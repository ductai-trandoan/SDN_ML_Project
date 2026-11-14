"""
WEB DASHBOARD BACKEND (FLASK REST API & UI)
Đã sửa lỗi chồng chéo tiến trình khi chuyển kịch bản trên Web
"""

import os
import sys
import json
import time
import signal
import threading
import subprocess
from flask import Flask, render_template, jsonify, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
from config import DASHBOARD_HOST, DASHBOARD_PORT, PATHS_CONFIG, HOSTS_CONFIG, SCENARIOS
from database.db_manager import DatabaseManager

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['TEMPLATES_AUTO_RELOAD'] = True
db = DatabaseManager()

# Quản lý tiến trình kịch bản đang chạy để tránh chạy chồng chéo
_scenario_lock = threading.Lock()
_current_proc = None

def _stop_running_scenario():
    """Dừng triệt để mọi kịch bản cũ, pipeline thu thập cũ và các luồng iperf đang chạy"""
    global _current_proc
    with _scenario_lock:
        if _current_proc and _current_proc.poll() is None:
            try:
                _current_proc.kill()
                _current_proc.wait(timeout=1)
            except Exception:
                pass
        _current_proc = None

        kill_cmd = (
            "pkill -9 -f 'traffic_generator.py' 2>/dev/null; "
            "pkill -9 -f 'run_full_pipeline.py' 2>/dev/null; "
            "pkill -9 -f 'test_mock_system.py' 2>/dev/null; "
            "killall -9 iperf iperf3 2>/dev/null; true"
        )
        if os.name == 'nt':
            subprocess.run(
                ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "bash", "-c", kill_cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            subprocess.run(kill_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _trigger_traffic_scenario(sc_id):
    """Kích hoạt kịch bản tạo tải trong Mininet thật chạy ngầm (đơn luồng sạch sẽ)"""
    global _current_proc
    try:
        _stop_running_scenario()
        with _scenario_lock:
            if os.name == 'nt':
                wsl_script = "/mnt/d/Project/SDN_ML_Project/experiments/traffic_generator.py"
                cmd = ["wsl", "-d", "Ubuntu-22.04", "--", "python3", wsl_script, "--scenario", sc_id]
            else:
                script_path = os.path.join(BASE_DIR, 'experiments', 'traffic_generator.py')
                cmd = [sys.executable, script_path, "--scenario", sc_id]

            _current_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f">>> [DASHBOARD] Đã kích hoạt kịch bản {sc_id} trên Mininet.")
    except Exception as e:
        print(f"!!! [DASHBOARD] Lỗi khi kích hoạt kịch bản {sc_id}: {e}")

@app.route('/')
def index():
    return render_template('index.html')

# Bộ đệm 30 điểm thời gian thực cho CẢ 3 TUYẾN (P1, P2, P3) và tuyến ACTIVE
_live_chart_history = []
_paths_chart_history = {
    'P1': [],
    'P2': [],
    'P3': []
}

@app.route('/api/live_data')
def get_live_data():
    """Endpoint trả về dữ liệu thời gian thực của cả 3 tuyến P1, P2, P3 để người dùng click xem từng tuyến"""
    global _live_chart_history, _paths_chart_history
    status_map, latest_links, _, reroute_logs = db.get_dashboard_live_bundle()
    active_path = status_map.get('active_path', 'P1')
    current_scenario = status_map.get('current_scenario', 'K1')
    
    ml_risk = float(status_map.get('ml_risk', '8.4'))
    ml_pred = int(status_map.get('ml_pred', '0'))
    
    # Ánh xạ thông số liên kết theo cặp switch (Giữ chiều có lưu lượng lớn hơn)
    link_map = {}
    for l in latest_links:
        k = (l['src_dpid'], l['dst_dpid'])
        if k not in link_map or l.get('throughput_mbps', 0) >= link_map[k].get('throughput_mbps', 0):
            link_map[k] = l
        
    # Tính toán thông số cho từng tuyến P1, P2, P3
    paths_status = {}
    for pid, pcfg in PATHS_CONFIG.items():
        links = pcfg.get('links', [])
        p_utils, p_tps, p_lats, p_jits, p_losses = [], [], [], [], []
        for (u, v) in links:
            lm = link_map.get((u, v)) or link_map.get((v, u))
            if lm:
                p_utils.append(lm.get('utilization_pct', 0.0))
                p_tps.append(lm.get('throughput_mbps', 0.0))
                p_lats.append(lm.get('latency_ms', pcfg.get('nominal_delay_ms', 10.0) / len(links)))
                p_jits.append(lm.get('jitter_ms', 0.8))
                p_losses.append(lm.get('loss_pct', 0.0))
            else:
                p_utils.append(0.0)
                p_tps.append(0.0)
                p_lats.append(pcfg.get('nominal_delay_ms', 10.0) / len(links))
                p_jits.append(0.8)
                p_losses.append(0.0)
                
        max_u = max(p_utils) if p_utils else 0.0
        avg_tp = max(p_tps) if p_tps else 0.0
        total_lat = sum(p_lats) if p_lats else pcfg.get('nominal_delay_ms', 10.0)
        avg_jit = max(p_jits) if p_jits else 0.8
        max_loss = max(p_losses) if p_losses else 0.0

        # Lọc nhiễu nền nhỏ cho các đường dự phòng đang nghỉ
        if pid != active_path and pid in ['P2', 'P3'] and avg_tp < 0.3:
            avg_tp = 0.0
            max_u = 0.0

        paths_status[pid] = {
            'is_active': (pid == active_path),
            'name': pcfg.get('name', pid),
            'capacity_mbps': pcfg.get('capacity_mbps', 10.0),
            'nominal_delay_ms': pcfg.get('nominal_delay_ms', 10.0),
            'hops': pcfg.get('hops', 2),
            'max_util': round(max_u, 1),
            'throughput_mbps': round(avg_tp, 2),
            'latency_ms': round(total_lat, 1),
            'jitter_ms': round(avg_jit, 2),
            'loss_pct': round(max_loss, 2)
        }
        
    active_summary = paths_status.get(active_path, {
        'throughput_mbps': 3.0,
        'latency_ms': 10.0,
        'jitter_ms': 0.8,
        'loss_pct': 0.0,
        'max_util': 30.0
    })

    # Kiểm tra trạng thái nghẽn toàn cục hoặc trên tuyến đang chọn
    p1_congested = (paths_status.get('P1', {}).get('max_util', 0) >= 80.0) or (paths_status.get('P1', {}).get('loss_pct', 0) >= 2.0)
    is_congested = (active_summary['max_util'] >= 80.0) or (active_summary['loss_pct'] >= 2.0) or (ml_risk >= 65.0) or p1_congested
    system_status = 'CONGESTED_ALERT' if is_congested else 'NORMAL'

    # Cập nhật lịch sử 30 giây cho TỪNG TUYẾN P1, P2, P3 và cho tuyến ACTIVE
    now_str = time.strftime("%H:%M:%S")
    if not _live_chart_history or _live_chart_history[-1]['ts'] != now_str:
        _live_chart_history.append({
            'ts': now_str,
            'active_path': active_path,
            'throughput_mbps': active_summary['throughput_mbps'],
            'latency_ms': active_summary['latency_ms'],
            'loss_pct': active_summary['loss_pct'],
            'utilization_pct': active_summary['max_util']
        })
        if len(_live_chart_history) > 30:
            _live_chart_history.pop(0)

        for pid in ['P1', 'P2', 'P3']:
            p_stat = paths_status.get(pid, {})
            _paths_chart_history[pid].append({
                'ts': now_str,
                'path_id': pid,
                'throughput_mbps': p_stat.get('throughput_mbps', 0.0),
                'latency_ms': p_stat.get('latency_ms', 10.0),
                'loss_pct': p_stat.get('loss_pct', 0.0),
                'utilization_pct': p_stat.get('max_util', 0.0)
            })
            if len(_paths_chart_history[pid]) > 30:
                _paths_chart_history[pid].pop(0)
    
    return jsonify({
        'active_path': active_path,
        'active_path_info': PATHS_CONFIG.get(active_path, {}),
        'active_summary': active_summary,
        'current_scenario': current_scenario,
        'scenario_desc': SCENARIOS.get(current_scenario, ''),
        'system_status': system_status,
        'ml_risk': ml_risk,
        'ml_pred': ml_pred,
        'paths_status': paths_status,
        'paths_history': _paths_chart_history,
        'links': latest_links,
        'recent_metrics': _live_chart_history,
        'reroute_logs': reroute_logs
    })

@app.route('/api/scenario/set', methods=['POST'])
def set_scenario():
    """Kích hoạt kịch bản thử nghiệm từ giao diện Dashboard và bơm tải Mininet thật"""
    data = request.get_json() or {}
    sc_id = data.get('scenario_id', 'K1')
    if sc_id in SCENARIOS:
        db.set_system_status('current_scenario', sc_id)
        if sc_id == 'K1':
            db.set_system_status('force_reset_path', 'P1')
        threading.Thread(target=_trigger_traffic_scenario, args=(sc_id,), daemon=True).start()
        return jsonify({
            'status': 'success',
            'scenario_id': sc_id,
            'description': SCENARIOS[sc_id],
            'message': f'Đã kích hoạt {sc_id} trên Mininet'
        })
    return jsonify({'status': 'error', 'message': 'Mã kịch bản không hợp lệ'}), 400

@app.route('/api/reset', methods=['POST'])
def reset_database():
    """Xóa dữ liệu cũ, dừng kịch bản đang chạy và đưa tuyến về P1"""
    global _live_chart_history, _paths_chart_history
    _stop_running_scenario()
    _live_chart_history.clear()
    for pid in ['P1', 'P2', 'P3']:
        _paths_chart_history[pid].clear()
    db.clear_metrics()
    db.set_system_status('active_path', 'P1')
    db.set_system_status('force_reset_path', 'P1')
    db.set_system_status('current_scenario', 'K1')
    db.set_system_status('ml_risk', '5.0')
    db.set_system_status('ml_pred', '0')
    db.set_system_status('system_status', 'NORMAL')
    return jsonify({'status': 'success', 'message': 'Đã đặt lại dữ liệu và khôi phục tuyến P1.'})

def run_dashboard():
    print(f">>> [DASHBOARD] Khởi động Web Dashboard tại: http://127.0.0.1:{DASHBOARD_PORT}")
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False, threaded=True)

if __name__ == '__main__':
    run_dashboard()
