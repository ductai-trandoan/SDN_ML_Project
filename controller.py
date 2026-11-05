"""
RYU SDN CONTROLLER - GIÁM SÁT QoS VÀ ĐIỀU PHỐI LƯU LƯỢNG THÍCH ỨNG (SDN + ML)
Tuân thủ toàn diện thiết kế trong Báo cáo định kỳ Đợt 1 ĐATN:
- Khám phá topology (mục 1.3.1, FR1)
- Giám sát QoS định kỳ Δt = 1s: Throughput, Utilization, Latency, Jitter, Packet loss (mục 1.3.2, 1.3.3, FR2)
- Lưu trữ SQLite bảng link_metrics chuẩn Bảng 2.4 (mục 1.3.4, 2.5.1, FR3)
- Tích hợp mô hình học máy phát hiện/dự đoán nguy cơ nghẽn (mục 1.4, 2.2, FR6)
- Thuật toán chọn đường đa tiêu chí QoS w(e) theo Công thức 1.9 & 1.10 (mục 1.5.3, FR7)
- Cơ chế điều phối thích ứng và chống dao động tuyến theo Công thức 2.1 (mục 1.5.4, 2.4, FR8)
- Ghi nhật ký chuyển tuyến phục vụ đánh giá (mục 2.1.2, FR9)
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, arp
from ryu.topology import event
from ryu.topology.api import get_switch, get_link

import os
import sys
import time
import json
import urllib.request
import urllib.error
import joblib

# Import cấu hình và DB manager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    MONITOR_INTERVAL, PREDICTION_HORIZON, CONGESTION_UTIL_THRESHOLD, CONGESTION_LOSS_THRESHOLD,
    ANTI_FLAP_DELTA, ANTI_FLAP_T_HOLD, QOS_WEIGHTS, NORM_MAX, PATHS_CONFIG, HOSTS_CONFIG,
    ML_SERVICE_HOST, ML_SERVICE_PORT
)
from database.db_manager import DatabaseManager

class AdaptiveSDNQoSController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(AdaptiveSDNQoSController, self).__init__(*args, **kwargs)
        self.name = 'adaptive_sdn_qos_controller'
        
        # Quản lý cơ sở dữ liệu SQLite
        self.db = DatabaseManager()
        
        # Cấu trúc lưu trữ trạng thái mạng nội tại
        self.datapaths = {}          # dpid -> datapath
        self.port_stats = {}         # (dpid, port_no) -> {'rx_bytes', 'tx_bytes', 'rx_packets', 'tx_packets', 'tx_dropped', 'ts'}
        self.link_qos = {}           # (src_dpid, dst_dpid) -> {'tp': Mbps, 'util': %, 'latency': ms, 'jitter': ms, 'loss': %}
        self.link_history = {}       # (src_dpid, dst_dpid) -> list các mẫu gần đây để tính rolling features
        
        # Quản lý cổng kết nối giữa các switch theo Topology
        # (src_dpid, dst_dpid) -> (src_port, dst_port)
        self.link_ports = {
            (1, 2): (2, 1), (2, 1): (1, 2),
            (2, 6): (2, 2), (6, 2): (2, 2),
            (1, 3): (3, 1), (3, 1): (1, 3),
            (3, 4): (2, 1), (4, 3): (1, 2),
            (4, 6): (2, 3), (6, 4): (3, 2),
            (1, 5): (4, 1), (5, 1): (1, 4),
            (5, 6): (2, 4), (6, 5): (4, 2)
        }
        
        # Cổng nối switch với host
        self.host_ports = {
            1: {1: ('10.0.0.1', '00:00:00:00:00:01')}, # s1 port 1 -> h1
            2: {3: ('10.0.0.3', '00:00:00:00:00:03')}, # s2 port 3 -> h3
            6: {1: ('10.0.0.2', '00:00:00:00:00:02'),  # s6 port 1 -> h2
                4: ('10.0.0.4', '00:00:00:00:00:04')}  # s6 port 4 -> h4
        }

        # Trạng thái điều phối thích ứng (mục 2.4)
        self.active_path_name = 'P1' # Khởi tạo mặc định đường ngắn nhất P1
        self.active_path = PATHS_CONFIG['P1']['path']
        self.last_reroute_time = 0.0 # Thời điểm chuyển tuyến gần nhất
        self.current_scenario = self.db.get_system_status('current_scenario', 'K1')
        
        # Tải mô hình ML cục bộ dự phòng nếu REST API không mở
        self.local_model = None
        local_model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ml_engine', 'qos_model_rf.pkl')
        if not os.path.exists(local_model_path):
            local_model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qos_model.pkl')
        if os.path.exists(local_model_path):
            try:
                self.local_model = joblib.load(local_model_path)
                self.logger.info(">>> [CONTROLLER] Đã nạp mô hình ML cục bộ dự phòng: %s", local_model_path)
            except Exception as e:
                self.logger.warning(">>> Không thể nạp mô hình cục bộ: %s", e)

        # Khởi động tiểu trình (Hub Thread) thu thập QoS định kỳ Δt = 1s (mục 2.5.2)
        self.monitor_thread = hub.spawn(self._periodic_monitor_loop)
        self.logger.info(">>> [CONTROLLER] Hệ thống giám sát QoS và Điều phối thích ứng đã sẵn sàng.")

    # =========================================================================
    # 1. QUẢN LÝ KẾT NỐI VÀ SWITCH FEATURES (OpenFlow 1.3)
    # =========================================================================
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.info(">>> [SWITCH JOIN] Switch s%s (DPID=%s) đã kết nối.", datapath.id, datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.info("<<< [SWITCH LEAVE] Switch s%s đã ngắt kết nối.", datapath.id)
                del self.datapaths[datapath.id]

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        self.datapaths[datapath.id] = datapath

        # Cài đặt Rule mặc định (Table-miss): Gửi gói tin chưa khớp lên Controller (Packet-In)
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, priority=0, match=match, actions=actions)

        # Cài đặt quy tắc định tuyến khởi tạo cho luồng chính h1 <-> h2 theo P1
        self._install_initial_flows(datapath)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath, buffer_id=buffer_id, priority=priority,
                match=match, instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath, priority=priority, match=match,
                instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout
            )
        datapath.send_msg(mod)

    def delete_flow(self, datapath, match, priority=10):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            priority=priority,
            match=match
        )
        datapath.send_msg(mod)

    # =========================================================================
    # 2. KHỞI TẠO VÀ CÀI ĐẶT CÁC QUY TẮC CHUYỂN TIẾP (FLOWS)
    # =========================================================================
    def _install_initial_flows(self, datapath):
        """Cài đặt luật ban đầu cho tải nền h3-h4 (qua s2-s6) và luồng chính h1-h2 (P1)"""
        dpid = datapath.id
        parser = datapath.ofproto_parser

        # 1. Luồng tải nền h3 (10.0.0.3) -> h4 (10.0.0.4) đi qua s2 - s6
        if dpid == 2:
            # Nhận từ h3 (port 3) -> đẩy ra s6 qua port 2
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src='10.0.0.3', ipv4_dst='10.0.0.4')
            self.add_flow(datapath, priority=20, match=match, actions=[parser.OFPActionOutput(2)])
            # Chiều ngược lại: nhận từ s6 (port 2) -> trả về h3 qua port 3
            match_rev = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src='10.0.0.4', ipv4_dst='10.0.0.3')
            self.add_flow(datapath, priority=20, match=match_rev, actions=[parser.OFPActionOutput(3)])
        elif dpid == 6:
            # Nhận từ s2 (port 2) -> trả cho h4 (port 4)
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src='10.0.0.3', ipv4_dst='10.0.0.4')
            self.add_flow(datapath, priority=20, match=match, actions=[parser.OFPActionOutput(4)])
            # Chiều ngược lại: h4 (port 4) -> s2 qua port 2
            match_rev = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src='10.0.0.4', ipv4_dst='10.0.0.3')
            self.add_flow(datapath, priority=20, match=match_rev, actions=[parser.OFPActionOutput(2)])

        # 2. Cài đặt đường ban đầu cho luồng h1 -> h2 theo P1 [s1, s2, s6]
        self._apply_path_for_flow(path_nodes=[1, 2, 6], priority=10)

    def _apply_path_for_flow(self, path_nodes, priority=10):
        """
        Cài đặt luật chuyển tiếp OpenFlow dọc theo danh sách switch của một đường dẫn.
        Cơ chế Make-Before-Break: Cài đặt đường mới với độ ưu tiên cao trước khi dỡ đường cũ.
        """
        self.logger.info(">>> [FLOW MOD] Đang cài đặt tuyến chuyển tiếp: %s (Priority=%d)", path_nodes, priority)
        
        # Cài đặt cho chiều h1 -> h2 (10.0.0.1 -> 10.0.0.2)
        for i in range(len(path_nodes)):
            curr_dpid = path_nodes[i]
            if curr_dpid not in self.datapaths:
                continue
            dp = self.datapaths[curr_dpid]
            parser = dp.ofproto_parser
            
            # Cổng ra
            if i == len(path_nodes) - 1:
                # Switch cuối cùng (s6) -> Đẩy ra host h2 (port 1)
                out_port = 1
            else:
                next_dpid = path_nodes[i+1]
                out_port = self.link_ports.get((curr_dpid, next_dpid), (None, None))[0]

            if out_port:
                # Match IP và ARP
                match_ip = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src='10.0.0.1', ipv4_dst='10.0.0.2')
                self.add_flow(dp, priority=priority, match=match_ip, actions=[parser.OFPActionOutput(out_port)])
                
                match_arp = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_ARP, arp_spa='10.0.0.1', arp_tpa='10.0.0.2')
                self.add_flow(dp, priority=priority, match=match_arp, actions=[parser.OFPActionOutput(out_port)])

        # Cài đặt cho chiều h2 -> h1 (10.0.0.2 -> 10.0.0.1)
        rev_nodes = list(reversed(path_nodes))
        for i in range(len(rev_nodes)):
            curr_dpid = rev_nodes[i]
            if curr_dpid not in self.datapaths:
                continue
            dp = self.datapaths[curr_dpid]
            parser = dp.ofproto_parser
            
            if i == len(rev_nodes) - 1:
                # Switch đầu tiên (s1) -> Đẩy ra host h1 (port 1)
                out_port = 1
            else:
                next_dpid = rev_nodes[i+1]
                out_port = self.link_ports.get((curr_dpid, next_dpid), (None, None))[0]

            if out_port:
                match_ip = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src='10.0.0.2', ipv4_dst='10.0.0.1')
                self.add_flow(dp, priority=priority, match=match_ip, actions=[parser.OFPActionOutput(out_port)])
                
                match_arp = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_ARP, arp_spa='10.0.0.2', arp_tpa='10.0.0.1')
                self.add_flow(dp, priority=priority, match=match_arp, actions=[parser.OFPActionOutput(out_port)])

    # =========================================================================
    # 3. GIÁM SÁT QoS ĐỊNH KỲ (Δt = 1s) THEO MỤC 1.3 & 2.5.2
    # =========================================================================
    def _periodic_monitor_loop(self):
        """Vòng lặp gửi OFPPortStatsRequest định kỳ mỗi Δt giây"""
        while True:
            for dp in list(self.datapaths.values()):
                self._request_port_stats(dp)
            hub.sleep(MONITOR_INTERVAL)

    def _request_port_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """Xử lý thống kê cổng gửi về để tính Throughput, Loss và Mức sử dụng (Mục 1.3.2)"""
        msg = ev.msg
        dpid = msg.datapath.id
        current_time = time.time()
        
        for stat in msg.body:
            port_no = stat.port_no
            if port_no > ofproto_v1_3.OFPP_MAX:
                continue

            key = (dpid, port_no)
            rx_bytes = stat.rx_bytes
            tx_bytes = stat.tx_bytes
            rx_pkts = stat.rx_packets
            tx_pkts = stat.tx_packets
            tx_dropped = stat.tx_dropped

            if key in self.port_stats:
                prev = self.port_stats[key]
                time_delta = current_time - prev['ts']
                if time_delta > 0:
                    # Tính Throughput (Mbps) = (ΔBytes * 8) / (Δt * 10^6)
                    delta_bytes = (tx_bytes - prev['tx_bytes']) + (rx_bytes - prev['rx_bytes'])
                    tp_mbps = (delta_bytes * 8.0) / (time_delta * 1_000_000.0)
                    
                    # Tính Packet Loss (%)
                    delta_tx_pkts = tx_pkts - prev['tx_packets']
                    delta_dropped = tx_dropped - prev['tx_dropped']
                    loss_pct = 0.0
                    if (delta_tx_pkts + delta_dropped) > 0:
                        loss_pct = (delta_dropped / float(delta_tx_pkts + delta_dropped)) * 100.0

                    self._update_link_qos(dpid, port_no, tp_mbps, loss_pct)

            # Cập nhật số liệu mới nhất
            self.port_stats[key] = {
                'rx_bytes': rx_bytes,
                'tx_bytes': tx_bytes,
                'rx_packets': rx_pkts,
                'tx_packets': tx_pkts,
                'tx_dropped': tx_dropped,
                'ts': current_time
            }

    def _update_link_qos(self, dpid, port_no, tp_mbps, loss_pct):
        """Xác định liên kết và tính toán các chỉ số QoS đầy đủ"""
        # Tìm xem cổng port_no của switch dpid nối tới switch nào
        dst_dpid = None
        for (u, v), (p_u, _) in self.link_ports.items():
            if u == dpid and p_u == port_no:
                dst_dpid = v
                break
                
        if not dst_dpid:
            return

        link_key = (dpid, dst_dpid)
        # Dung lượng cấu hình (10 Mbps cho P1, P2; 5 Mbps cho P3 s1-s5, s5-s6)
        capacity = 5.0 if (dpid in [1, 5] and dst_dpid in [5, 6]) else 10.0
        util_pct = min(100.0, (tp_mbps / capacity) * 100.0)

        # Độ trễ cơ sở cấu hình (5ms cho P1, 10ms cho P2, P3)
        base_delay = 5.0 if link_key in [(1, 2), (2, 1), (2, 6), (6, 2)] else 10.0
        # Nếu nghẽn (util >= 80%), độ trễ và jitter tăng mô phỏng theo hàng đợi OVS (Mục 1.3.3)
        delay_ms = base_delay
        jitter_ms = 1.0
        if util_pct >= CONGESTION_UTIL_THRESHOLD:
            delay_ms += (util_pct - CONGESTION_UTIL_THRESHOLD) * 1.5
            jitter_ms += (util_pct - CONGESTION_UTIL_THRESHOLD) * 0.3

        self.link_qos[link_key] = {
            'tp': round(tp_mbps, 3),
            'util': round(util_pct, 2),
            'latency': round(delay_ms, 2),
            'jitter': round(jitter_ms, 2),
            'loss': round(loss_pct, 2),
            'capacity': capacity
        }

        # Lưu vào danh sách trượt
        if link_key not in self.link_history:
            self.link_history[link_key] = []
        self.link_history[link_key].append(self.link_qos[link_key])
        if len(self.link_history[link_key]) > 10:
            self.link_history[link_key].pop(0)

        # Lưu bản ghi số liệu vào SQLite theo Bảng 2.4
        self.current_scenario = self.db.get_system_status('current_scenario', 'K1')
        self.db.insert_link_metric(
            src_dpid=dpid, dst_dpid=dst_dpid,
            capacity_mbps=capacity, throughput_mbps=tp_mbps,
            latency_ms=delay_ms, jitter_ms=jitter_ms, loss_pct=loss_pct,
            scenario_id=self.current_scenario
        )

        # Nếu liên kết này thuộc đường đang dùng (active_path), kiểm tra nguy cơ nghẽn
        if self._is_link_in_active_path(dpid, dst_dpid):
            self._evaluate_congestion_and_steer(dpid, dst_dpid)

    def _is_link_in_active_path(self, src_dpid, dst_dpid):
        for i in range(len(self.active_path) - 1):
            if (self.active_path[i] == src_dpid and self.active_path[i+1] == dst_dpid) or \
               (self.active_path[i] == dst_dpid and self.active_path[i+1] == src_dpid):
                return True
        return False

    # =========================================================================
    # 4. HỌC MÁY & ĐIỀU PHỐI THÍCH ỨNG (Mục 1.4, 1.5, 2.4)
    # =========================================================================
    def _evaluate_congestion_and_steer(self, src_dpid, dst_dpid):
        """Đánh giá nguy cơ nghẽn bằng AI / Ngưỡng và điều phối luồng nếu thỏa điều kiện"""
        qos = self.link_qos.get((src_dpid, dst_dpid), {})
        if not qos:
            return

        # Tính toán rolling features từ history
        history = self.link_history.get((src_dpid, dst_dpid), [qos])
        utils = [h['util'] for h in history]
        util_mean = sum(utils) / len(utils)
        util_std = (sum((u - util_mean)**2 for u in utils) / len(utils))**0.5
        util_max = max(utils)
        util_diff = (utils[-1] - utils[-2]) if len(utils) >= 2 else 0.0

        # Gọi dịch vụ học máy qua REST API (Mục 2.2)
        is_congested = False
        will_congest = False
        reasons = []

        try:
            url = f"http://{ML_SERVICE_HOST}:{ML_SERVICE_PORT}/predict"
            req_data = json.dumps({
                'throughput_mbps': qos['tp'],
                'utilization_pct': qos['util'],
                'latency_ms': qos['latency'],
                'jitter_ms': qos['jitter'],
                'loss_pct': qos['loss'],
                'util_rolling_mean': util_mean,
                'util_rolling_std': util_std,
                'util_rolling_max': util_max,
                'util_diff': util_diff
            }).encode('utf-8')
            
            req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=0.5) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                is_congested = bool(res_body.get('is_congested_now', 0))
                will_congest = bool(res_body.get('will_congest_soon', 0))
                reasons = res_body.get('reasons', [])
        except Exception:
            # Fallback nếu REST service chưa mở: Sử dụng ngưỡng cố định (Baseline)
            if qos['util'] >= CONGESTION_UTIL_THRESHOLD or qos['loss'] >= CONGESTION_LOSS_THRESHOLD:
                is_congested = True
                reasons.append(f"Mức sử dụng ({qos['util']}%) hoặc mất gói ({qos['loss']}%) vượt ngưỡng")

        if is_congested or will_congest:
            self.logger.warning("!!! [CẢNH BÁO NGHẼN] Liên kết (s%d -> s%d): %s", src_dpid, dst_dpid, "; ".join(reasons))
            self._execute_adaptive_reroute(trigger_reason="; ".join(reasons) or "Phát hiện nguy cơ nghẽn")

    def _calculate_path_cost(self, path_config):
        """
        Tính chi phí đường dẫn theo trọng số đa tiêu chí QoS (Công thức 1.9 & 1.10):
        w(e) = w1 * (d/d_max) + w2 * (j/j_max) + w3 * (l/l_max) + w4 * u
        Cost(P) = Sum(w(e))
        """
        links = path_config['links']
        total_cost = 0.0
        
        w_d = QOS_WEIGHTS['w_delay']
        w_j = QOS_WEIGHTS['w_jitter']
        w_l = QOS_WEIGHTS['w_loss']
        w_u = QOS_WEIGHTS['w_util']

        for (u, v) in links:
            # Lấy thông số QoS hiện tại của liên kết
            qos = self.link_qos.get((u, v), {
                'latency': path_config['nominal_delay_ms'] / len(links),
                'jitter': 1.0,
                'loss': 0.0,
                'util': 10.0
            })

            d_norm = min(1.0, qos['latency'] / NORM_MAX['latency_ms'])
            j_norm = min(1.0, qos['jitter'] / NORM_MAX['jitter_ms'])
            l_norm = min(1.0, qos['loss'] / NORM_MAX['loss_pct'])
            u_norm = min(1.0, qos['util'] / NORM_MAX['utilization_pct'])

            w_e = (w_d * d_norm) + (w_j * j_norm) + (w_l * l_norm) + (w_u * u_norm)
            total_cost += w_e

        return total_cost

    def _execute_adaptive_reroute(self, trigger_reason=""):
        """
        Thực hiện điều phối lưu lượng thích ứng với cơ chế chống dao động tuyến (Mục 2.4, Công thức 2.1):
        Cost(P_mới) < (1 - δ) * Cost(P_hiện_tại)  và  t - t_chuyển >= T_giữ
        """
        now = time.time()
        
        # 1. Kiểm tra điều kiện thời gian giữ tối thiểu T_giữ
        if (now - self.last_reroute_time) < ANTI_FLAP_T_HOLD:
            remaining = ANTI_FLAP_T_HOLD - (now - self.last_reroute_time)
            self.logger.info("--- [ANTI-FLAPPING] Chưa đủ thời gian giữ T_giữ (còn %.1fs). Bỏ qua chuyển tuyến.", remaining)
            return

        current_path_name = self.active_path_name
        current_cost = self._calculate_path_cost(PATHS_CONFIG[current_path_name])
        
        # 2. Đánh giá chi phí của tất cả các đường ứng viên
        best_path_name = current_path_name
        min_cost = current_cost

        for p_name, p_cfg in PATHS_CONFIG.items():
            if p_name == current_path_name:
                continue
            cost = self._calculate_path_cost(p_cfg)
            self.logger.info("    -> Chi phí đường %s: %.4f (Đường hiện tại %s: %.4f)", p_name, cost, current_path_name, current_cost)
            if cost < min_cost:
                min_cost = cost
                best_path_name = p_name

        # 3. Kiểm tra điều kiện biên độ cải thiện δ: Cost(P_mới) < (1 - δ) * Cost(P_hiện_tại)
        threshold_cost = (1.0 - ANTI_FLAP_DELTA) * current_cost
        if min_cost < threshold_cost and best_path_name != current_path_name:
            self.logger.info(">>> [REROUTING THỰC HIỆN] Chuyển luồng từ %s sang %s (Chi phí: %.4f -> %.4f, Giảm: %.1f%%)",
                             current_path_name, best_path_name, current_cost, min_cost,
                             ((current_cost - min_cost) / current_cost) * 100.0)

            # Thực hiện Make-Before-Break: Cài đường mới trước
            new_path_nodes = PATHS_CONFIG[best_path_name]['path']
            old_path_nodes = PATHS_CONFIG[current_path_name]['path']
            
            # Cài đường mới với độ ưu tiên cao hơn (Priority 15)
            self._apply_path_for_flow(new_path_nodes, priority=15)
            
            # Ghi log chuyển tuyến vào SQLite
            self.db.log_reroute_event(
                flow_id="h1_to_h2",
                old_path=old_path_nodes,
                new_path=new_path_nodes,
                trigger_reason=trigger_reason,
                cost_old=current_cost,
                cost_new=min_cost
            )

            # Cập nhật trạng thái
            self.active_path_name = best_path_name
            self.active_path = new_path_nodes
            self.last_reroute_time = now

            # Dỡ bỏ đường cũ sau 2 giây để tránh mất gói (Make-before-break)
            hub.spawn_after(2, self._cleanup_old_path_flows, old_path_nodes, 10)
        else:
            self.logger.info("--- [ANTI-FLAPPING] Đường mới không vượt qua ngưỡng cải thiện δ=%.0f%%. Giữ nguyên %s.",
                             ANTI_FLAP_DELTA * 100.0, current_path_name)

    def _cleanup_old_path_flows(self, old_nodes, priority=10):
        """Dỡ bỏ luật cũ sau khi luật mới đã ổn định"""
        for dpid in old_nodes:
            if dpid in self.datapaths:
                dp = self.datapaths[dpid]
                parser = dp.ofproto_parser
                # Xóa match IP
                match_ip = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src='10.0.0.1', ipv4_dst='10.0.0.2')
                self.delete_flow(dp, match=match_ip, priority=priority)
                match_rev = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src='10.0.0.2', ipv4_dst='10.0.0.1')
                self.delete_flow(dp, match=match_rev, priority=priority)

    # =========================================================================
    # 5. XỬ LÝ GÓI TIN CHƯA BIẾT (PACKET-IN) VÀ ARP
    # =========================================================================
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Bỏ qua gói LLDP của Ryu
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # Xử lý phản hồi ARP
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            # Flood ARP nếu là broadcast
            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=msg.data)
            datapath.send_msg(out)
            return
