"""
QUẢN LÝ CƠ SỞ DỮ LIỆU SQLITE (SDN QoS & REROUTING LOGS)
Tuân thủ đúng Bảng 2.4: Cấu trúc bảng link_metrics trong Báo cáo Đợt 1
"""
import sqlite3
import os
from datetime import datetime
import json

try:
    from config import DB_PATH, CONGESTION_UTIL_THRESHOLD, CONGESTION_LOSS_THRESHOLD
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import DB_PATH, CONGESTION_UTIL_THRESHOLD, CONGESTION_LOSS_THRESHOLD

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Kích hoạt WAL mode để cho phép đọc ghi đồng thời không bị khóa file
        conn.execute('PRAGMA journal_mode = WAL;')
        conn.execute('PRAGMA synchronous = NORMAL;')
        conn.execute('PRAGMA busy_timeout = 3000;')
        return conn

    def init_db(self):
        """Khởi tạo các bảng theo Báo cáo Đợt 1"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Bảng link_metrics (Bảng 2.4 trong Báo cáo ĐATN)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS link_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    src_dpid INTEGER NOT NULL,
                    dst_dpid INTEGER NOT NULL,
                    capacity_mbps REAL NOT NULL,
                    throughput_mbps REAL NOT NULL,
                    utilization_pct REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    jitter_ms REAL NOT NULL,
                    loss_pct REAL NOT NULL,
                    scenario_id TEXT NOT NULL,
                    label_now INTEGER NOT NULL,
                    label_pred INTEGER DEFAULT 0
                )
            ''')
            
            # Tạo index tối ưu truy vấn cực nhanh
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_link_ts ON link_metrics(src_dpid, dst_dpid, ts)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_link_id_desc ON link_metrics(id DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_link_pair_id ON link_metrics(src_dpid, dst_dpid, id DESC)')

            # 2. Bảng reroute_logs (Lịch sử các sự kiện điều phối luồng)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reroute_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    flow_id TEXT NOT NULL,
                    old_path TEXT NOT NULL,
                    new_path TEXT NOT NULL,
                    trigger_reason TEXT NOT NULL,
                    cost_old REAL,
                    cost_new REAL,
                    improvement_pct REAL,
                    status TEXT DEFAULT 'SUCCESS'
                )
            ''')

            # 3. Bảng current_status (Lưu trạng thái hiện thời của hệ thống cho Dashboard)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS current_status (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Khởi tạo trạng thái mặc định
            cursor.execute('''
                INSERT OR IGNORE INTO current_status (key, value) 
                VALUES ('active_path', 'P1'), ('current_scenario', 'K1'), ('system_status', 'NORMAL')
            ''')
            conn.commit()

    def insert_link_metric(self, src_dpid, dst_dpid, capacity_mbps, throughput_mbps, 
                           latency_ms, jitter_ms, loss_pct, scenario_id="K1", label_now=None, label_pred=0, ts=None):
        """Chèn 1 bản ghi số liệu liên kết vào bảng link_metrics"""
        utilization_pct = min(100.0, (throughput_mbps / capacity_mbps) * 100.0) if capacity_mbps > 0 else 0.0
        
        # Tự động gán nhãn label_now theo quy ước mục 2.5.2 nếu chưa truyền vào
        if label_now is None:
            if utilization_pct >= CONGESTION_UTIL_THRESHOLD or loss_pct >= CONGESTION_LOSS_THRESHOLD:
                label_now = 1
            else:
                label_now = 0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if ts:
                cursor.execute('''
                    INSERT INTO link_metrics (ts, src_dpid, dst_dpid, capacity_mbps, throughput_mbps,
                                             utilization_pct, latency_ms, jitter_ms, loss_pct, scenario_id, label_now, label_pred)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (ts, src_dpid, dst_dpid, capacity_mbps, throughput_mbps, utilization_pct, 
                      latency_ms, jitter_ms, loss_pct, scenario_id, label_now, label_pred))
            else:
                cursor.execute('''
                    INSERT INTO link_metrics (src_dpid, dst_dpid, capacity_mbps, throughput_mbps,
                                             utilization_pct, latency_ms, jitter_ms, loss_pct, scenario_id, label_now, label_pred)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (src_dpid, dst_dpid, capacity_mbps, throughput_mbps, utilization_pct, 
                      latency_ms, jitter_ms, loss_pct, scenario_id, label_now, label_pred))
            conn.commit()

    def log_reroute_event(self, flow_id, old_path, new_path, trigger_reason, cost_old=0.0, cost_new=0.0):
        """Ghi nhận sự kiện chuyển tuyến phục vụ đánh giá FR8 & FR9"""
        improvement_pct = 0.0
        if cost_old > 0:
            improvement_pct = ((cost_old - cost_new) / cost_old) * 100.0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reroute_logs (flow_id, old_path, new_path, trigger_reason, cost_old, cost_new, improvement_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (flow_id, json.dumps(old_path), json.dumps(new_path), trigger_reason, cost_old, cost_new, improvement_pct))
            
            # Cập nhật active_path
            path_name = "P1"
            if new_path == [1, 3, 4, 6]:
                path_name = "P2"
            elif new_path == [1, 5, 6]:
                path_name = "P3"
            elif new_path == [1, 2, 6]:
                path_name = "P1"
            else:
                path_name = str(new_path)
                
            cursor.execute('''
                INSERT OR REPLACE INTO current_status (key, value, updated_at)
                VALUES ('active_path', ?, CURRENT_TIMESTAMP)
            ''', (path_name,))
            conn.commit()

    def get_latest_metrics(self, limit=30, src_dpid=2, dst_dpid=6):
        """Lấy danh sách các bản ghi số liệu của liên kết trọng yếu s2-s6"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM link_metrics 
                WHERE src_dpid = ? AND dst_dpid = ?
                ORDER BY id DESC LIMIT ?
            ''', (src_dpid, dst_dpid, limit))
            return [dict(row) for row in cursor.fetchall()]

    def insert_link_metrics_batch(self, metrics_list):
        """Chèn hàng loạt bản ghi trong 1 transaction duy nhất để tránh khóa database"""
        if not metrics_list:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO link_metrics (ts, src_dpid, dst_dpid, capacity_mbps, throughput_mbps,
                                         utilization_pct, latency_ms, jitter_ms, loss_pct, scenario_id, label_now, label_pred)
                VALUES (:ts, :src_dpid, :dst_dpid, :capacity_mbps, :throughput_mbps,
                        :utilization_pct, :latency_ms, :jitter_ms, :loss_pct, :scenario_id, :label_now, :label_pred)
            ''', metrics_list)
            conn.commit()

    def get_latest_metrics_by_link(self):
        """Lấy bản ghi mới nhất của từng liên kết siêu tốc từ 50 mẫu gần nhất"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM (
                    SELECT * FROM link_metrics ORDER BY id DESC LIMIT 50
                )
                GROUP BY src_dpid, dst_dpid
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def get_dashboard_live_bundle(self):
        """Lấy trọn vẹn status, link metrics, biểu đồ và reroute logs chỉ trong 1 lần mở kết nối duy nhất (< 2ms)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM current_status')
            status_map = {row['key']: row['value'] for row in cursor.fetchall()}
            
            cursor.execute('''
                SELECT * FROM (
                    SELECT * FROM link_metrics ORDER BY id DESC LIMIT 50
                )
                GROUP BY src_dpid, dst_dpid
            ''')
            latest_links = [dict(row) for row in cursor.fetchall()]
            
            # 3. Lấy chuỗi 30 mẫu thời gian liên tục của liên kết trọng yếu s2-s6
            cursor.execute('''
                SELECT * FROM link_metrics 
                WHERE src_dpid = 2 AND dst_dpid = 6 
                ORDER BY id DESC LIMIT 30
            ''')
            recent_metrics = [dict(row) for row in cursor.fetchall()]
            recent_metrics.reverse()
            
            cursor.execute('SELECT * FROM reroute_logs ORDER BY id DESC LIMIT 15')
            reroute_logs = [dict(row) for row in cursor.fetchall()]
            
            return status_map, latest_links, recent_metrics, reroute_logs

    def get_reroute_logs(self, limit=50):
        """Lấy danh sách các lần chuyển tuyến gần nhất"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM reroute_logs ORDER BY id DESC LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def set_system_status(self, key, value):
        """Cập nhật giá trị trạng thái hệ thống"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO current_status (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, str(value)))
            conn.commit()

    def get_system_status(self, key, default=None):
        """Lấy giá trị trạng thái hệ thống"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM current_status WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row['value'] if row else default

    def clear_metrics(self):
        """Xóa trắng dữ liệu thử nghiệm"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM link_metrics')
            cursor.execute('DELETE FROM reroute_logs')
            conn.commit()
