"""
DỊCH VỤ HỌC MÁY ĐỘC LẬP QUA REST API (SDN ML SERVICE)
Thiết kế theo mục 2.2 của Báo cáo Đợt 1:
"Dịch vụ học máy được tách thành một tiến trình riêng, bộ điều khiển gọi qua giao diện REST hoặc đọc số liệu từ cơ sở dữ liệu.
Cách tách này giúp phát triển và thay thế mô hình độc lập với bộ điều khiển, đồng thời tránh làm chậm vòng xử lý sự kiện của Ryu."
"""

import os
import sys
import json
import joblib
import pandas as pd
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ML_SERVICE_HOST, ML_SERVICE_PORT, CONGESTION_UTIL_THRESHOLD, CONGESTION_LOSS_THRESHOLD

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_NOW_PATH = os.path.join(CUR_DIR, "qos_model_rf.pkl")
MODEL_PRED_PATH = os.path.join(CUR_DIR, "qos_model_pred_rf.pkl")

# Tải các mô hình học máy
MODEL_NOW = None
MODEL_PRED = None

if os.path.exists(MODEL_NOW_PATH):
    try:
        MODEL_NOW = joblib.load(MODEL_NOW_PATH)
        print(f">>> [ML SERVICE] Đã nạp thành công mô hình Phát hiện nghẽn: {MODEL_NOW_PATH}")
    except Exception as e:
        print(f"!!! [ML SERVICE] Lỗi load MODEL_NOW: {e}")

if os.path.exists(MODEL_PRED_PATH):
    try:
        MODEL_PRED = joblib.load(MODEL_PRED_PATH)
        print(f">>> [ML SERVICE] Đã nạp thành công mô hình Dự đoán nghẽn: {MODEL_PRED_PATH}")
    except Exception as e:
        print(f"!!! [ML SERVICE] Lỗi load MODEL_PRED: {e}")

class MLRequestHandler(BaseHTTPRequestHandler):
    def _send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self._send_json_response(200, {'status': 'ok'})

    def do_GET(self):
        if self.path == '/health':
            self._send_json_response(200, {
                'status': 'healthy',
                'service': 'SDN ML Inference Service',
                'model_now_loaded': MODEL_NOW is not None,
                'model_pred_loaded': MODEL_PRED is not None
            })
        elif self.path == '/model_info':
            report_path = os.path.join(CUR_DIR, "ml_evaluation_report.json")
            if os.path.exists(report_path):
                with open(report_path, 'r', encoding='utf-8') as f:
                    self._send_json_response(200, json.load(f))
            else:
                self._send_json_response(200, {'message': 'Chưa có báo cáo huấn luyện. Hãy chạy train_models.py'})
        else:
            self._send_json_response(404, {'error': 'Endpoint not found'})

    def do_POST(self):
        if self.path == '/predict':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                payload = json.loads(post_data.decode('utf-8'))
            except Exception as e:
                self._send_json_response(400, {'error': f'Invalid JSON: {str(e)}'})
                return

            # Trích xuất các tham số từ request
            tp = float(payload.get('throughput_mbps', 0.0))
            util = float(payload.get('utilization_pct', 0.0))
            lat = float(payload.get('latency_ms', 5.0))
            jit = float(payload.get('jitter_ms', 1.0))
            loss = float(payload.get('loss_pct', 0.0))

            # Các tham số trượt (nếu có, không có thì xấp xỉ bằng giá trị hiện thời)
            util_mean = float(payload.get('util_rolling_mean', util))
            util_std = float(payload.get('util_rolling_std', 0.0))
            util_max = float(payload.get('util_rolling_max', util))
            util_diff = float(payload.get('util_diff', 0.0))
            lat_mean = float(payload.get('latency_rolling_mean', lat))
            lat_max = float(payload.get('latency_rolling_max', lat))
            loss_mean = float(payload.get('loss_rolling_mean', loss))

            features = np.array([[
                tp, util, lat, jit, loss,
                util_mean, util_std, util_max, util_diff,
                lat_mean, lat_max, loss_mean
            ]])

            is_congested_now = 0
            prob_now = 0.0
            will_congest_soon = 0
            prob_pred = 0.0
            reasons = []

            # 1. Dự đoán phát hiện hiện tại
            if MODEL_NOW is not None:
                try:
                    pred_res = MODEL_NOW.predict(features)[0]
                    proba_res = MODEL_NOW.predict_proba(features)[0]
                    is_congested_now = int(pred_res)
                    prob_now = round(float(proba_res[1]), 4)
                except Exception as e:
                    # Fallback theo ngưỡng
                    is_congested_now = 1 if (util >= CONGESTION_UTIL_THRESHOLD or loss >= CONGESTION_LOSS_THRESHOLD) else 0
                    prob_now = 1.0 if is_congested_now else 0.0
            else:
                # Fallback theo ngưỡng
                is_congested_now = 1 if (util >= CONGESTION_UTIL_THRESHOLD or loss >= CONGESTION_LOSS_THRESHOLD) else 0
                prob_now = 1.0 if is_congested_now else 0.0

            # 2. Dự đoán nguy cơ trong H = 5s
            if MODEL_PRED is not None:
                try:
                    pred_fut = MODEL_PRED.predict(features)[0]
                    proba_fut = MODEL_PRED.predict_proba(features)[0]
                    will_congest_soon = int(pred_fut)
                    prob_pred = round(float(proba_fut[1]), 4)
                except Exception as e:
                    will_congest_soon = 1 if (util >= 70.0 and util_diff > 5.0) else is_congested_now
                    prob_pred = 0.8 if will_congest_soon else 0.1
            else:
                will_congest_soon = 1 if (util >= 70.0 and util_diff > 5.0) else is_congested_now
                prob_pred = 0.8 if will_congest_soon else 0.1

            if is_congested_now == 1:
                reasons.append(f"Mức sử dụng ({util:.1f}%) hoặc Mất gói ({loss:.1f}%) vượt ngưỡng báo động")
            if will_congest_soon == 1 and is_congested_now == 0:
                reasons.append(f"Xu hướng tăng tải ({util_diff:+.1f}%) cảnh báo nguy cơ nghẽn trong 5s tới")

            response_data = {
                'status': 'success',
                'is_congested_now': is_congested_now,
                'prob_now': prob_now,
                'will_congest_soon': will_congest_soon,
                'prob_pred': prob_pred,
                'requires_reroute': bool(is_congested_now or will_congest_soon),
                'reasons': reasons
            }

            self._send_json_response(200, response_data)
        else:
            self._send_json_response(404, {'error': 'Endpoint not found'})

def run_service(host=ML_SERVICE_HOST, port=ML_SERVICE_PORT):
    server = HTTPServer((host, port), MLRequestHandler)
    print(f">>> [ML SERVICE] Đang chạy tại http://{host}:{port}")
    print(f"    - Endpoint kiểm tra: http://{host}:{port}/health")
    print(f"    - Endpoint suy luận: POST http://{host}:{port}/predict")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n>>> [ML SERVICE] Đang tắt máy chủ...")
        server.server_close()

if __name__ == '__main__':
    run_service()
