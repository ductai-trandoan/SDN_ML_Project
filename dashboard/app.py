"""
WEB DASHBOARD BACKEND (FLASK REST API & UI)
Tuân thủ FR4 trong Báo cáo Đợt 1:
"Hiển thị topology, màu liên kết theo tải, biểu đồ chỉ số, cảnh báo, đường đang dùng"
Giao tiếp với cơ sở dữ liệu SQLite link_metrics và reroute_logs
"""

import os
import sys
import json
from flask import Flask, render_template, jsonify, request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DASHBOARD_HOST, DASHBOARD_PORT, PATHS_CONFIG, HOSTS_CONFIG, SCENARIOS
from database.db_manager import DatabaseManager

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['TEMPLATES_AUTO_RELOAD'] = True
db = DatabaseManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/live_data')
def get_live_data():
    """Endpoint siêu tốc kết hợp tất cả dữ liệu chỉ trong 1 request duy nhất"""
    status_map, latest_links, recent_metrics, reroute_logs = db.get_dashboard_live_bundle()
    active_path = status_map.get('active_path', 'P1')
    current_scenario = status_map.get('current_scenario', 'K1')
    is_congested = any(l.get('label_now', 0) == 1 for l in latest_links)
    system_status = 'CONGESTED_ALERT' if is_congested else 'NORMAL'
    
    return jsonify({
        'active_path': active_path,
        'active_path_info': PATHS_CONFIG.get(active_path, {}),
        'current_scenario': current_scenario,
        'scenario_desc': SCENARIOS.get(current_scenario, ''),
        'system_status': system_status,
        'links': latest_links,
        'recent_metrics': recent_metrics,
        'reroute_logs': reroute_logs
    })

@app.route('/api/status')
def get_status():
    """Lấy thông tin trạng thái tổng quan thời gian thực"""
    active_path = db.get_system_status('active_path', 'P1')
    current_scenario = db.get_system_status('current_scenario', 'K1')
    system_status = db.get_system_status('system_status', 'NORMAL')
    
    # Lấy thông số liên kết mới nhất
    latest_links = db.get_latest_metrics_by_link()
    
    # Kiểm tra xem có liên kết nào đang nghẽn không
    is_congested = any(l.get('label_now', 0) == 1 for l in latest_links)
    if is_congested:
        system_status = 'CONGESTED_ALERT'

    return jsonify({
        'active_path': active_path,
        'active_path_info': PATHS_CONFIG.get(active_path, {}),
        'current_scenario': current_scenario,
        'scenario_desc': SCENARIOS.get(current_scenario, ''),
        'system_status': system_status,
        'links': latest_links
    })

@app.route('/api/metrics/recent')
def get_recent_metrics():
    """Lấy 30 bản ghi số liệu gần nhất để vẽ đồ thị"""
    limit = request.args.get('limit', 30, type=int)
    metrics = db.get_latest_metrics(limit=limit)
    # Đảo ngược lại theo thứ tự thời gian tăng dần
    metrics.reverse()
    return jsonify(metrics)

@app.route('/api/reroute_logs')
def get_reroute_logs():
    """Lấy danh sách các sự kiện chuyển tuyến gần nhất"""
    logs = db.get_reroute_logs(limit=20)
    return jsonify(logs)

@app.route('/api/scenario/set', methods=['POST'])
def set_scenario():
    """Kích hoạt kịch bản thử nghiệm từ giao diện Dashboard"""
    data = request.get_json() or {}
    sc_id = data.get('scenario_id', 'K1')
    if sc_id in SCENARIOS:
        db.set_system_status('current_scenario', sc_id)
        return jsonify({'status': 'success', 'scenario_id': sc_id, 'description': SCENARIOS[sc_id]})
    return jsonify({'status': 'error', 'message': 'Mã kịch bản không hợp lệ'}), 400

@app.route('/api/reset', methods=['POST'])
def reset_database():
    """Xóa dữ liệu cũ và thiết lập lại ban đầu"""
    db.clear_metrics()
    db.set_system_status('active_path', 'P1')
    db.set_system_status('current_scenario', 'K1')
    return jsonify({'status': 'success', 'message': 'Đã đặt lại dữ liệu.'})

def run_dashboard():
    print(f">>> [DASHBOARD] Khởi động Web Dashboard tại: http://127.0.0.1:{DASHBOARD_PORT}")
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False, threaded=True)

if __name__ == '__main__':
    run_dashboard()
