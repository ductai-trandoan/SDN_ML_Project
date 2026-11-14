"""
BỘ TẠO TẢI VÀ THỰC THI CÁC KỊCH BẢN THỰC NGHIỆM MININET (K1 - K6)
Đã sửa lỗi mất cấu hình băng thông TCLink (HTB) và xung đột luồng iperf
"""

import time
import os
import sys
import subprocess
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SCENARIOS
from database.db_manager import DatabaseManager

class TrafficScenarioRunner:
    def __init__(self, net=None):
        self.net = net
        self.db = DatabaseManager()

    def _cmd(self, host, command):
        """Thực thi câu lệnh trong network namespace của host một cách phi đồng bộ (Non-blocking)"""
        if self.net:
            try:
                node = self.net.get(host)
                return node.cmd(f"{command} &")
            except Exception as e:
                print(f"[!] Lỗi khi thực thi lệnh trên {host}: {e}")
                return None
        else:
            try:
                pid_out = subprocess.check_output(f"pgrep -f 'mininet:{host}'", shell=True).decode().strip()
                if pid_out:
                    pid = pid_out.split()[0]
                    full_cmd = f"mnexec -a {pid} bash -c '{command}'"
                    subprocess.Popen(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            return None

    def _restore_s2_eth3_tc(self, delay='5ms', loss=0):
        """
        Khôi phục hoặc chỉnh sửa thông số netem trên cổng s2-eth3 MÀ KHÔNG XÓA HTB (10 Mbps) của Mininet.
        Mininet TCLink tạo root handle 5:0 htb (class 5:1 rate 10Mbit) và child netem handle 10: parent 5:1.
        """
        loss_str = f"loss {loss}%" if loss > 0 else ""
        # Thử thay đổi qdisc netem con của Mininet trước; nếu chưa có thì gắn lại đúng cấu trúc HTB 10Mbit + netem
        cmd = (
            f"tc qdisc change dev s2-eth3 parent 5:1 handle 10: netem delay {delay} {loss_str} 2>/dev/null || "
            f"(tc qdisc del dev s2-eth3 root 2>/dev/null; "
            f"tc qdisc add dev s2-eth3 root handle 5:0 htb default 1 && "
            f"tc class add dev s2-eth3 parent 5:0 classid 5:1 htb rate 10Mbit burst 15k && "
            f"tc qdisc add dev s2-eth3 parent 5:1 handle 10: netem delay {delay} {loss_str}) 2>/dev/null || true"
        )
        subprocess.run(cmd, shell=True)

    def _ensure_servers(self):
        """Khởi động lại iperf sạch sẽ và khôi phục trạng thái vật lý chuẩn của liên kết"""
        try:
            subprocess.run("killall -9 iperf iperf3 2>/dev/null || true", shell=True)
            subprocess.run("ip link set s2-eth3 up 2>/dev/null || true", shell=True)
            subprocess.run("ip link set s6-eth3 up 2>/dev/null || true", shell=True)
            subprocess.run("ip link set s2-eth2 up 2>/dev/null || true", shell=True)
            
            # Khôi phục đúng chuẩn 10Mbps, 5ms, 0% loss cho s2-eth3
            self._restore_s2_eth3_tc(delay='5ms', loss=0)
            self.db.set_system_status('netem_degraded', '0')
            self.db.set_system_status('link_s2_s6_down', '0')
            time.sleep(0.5)

            if self.net:
                self.net.get('h2').cmd('iperf -s -u -p 5001 -D')
                self.net.get('h4').cmd('iperf -s -u -p 5002 -D')
            else:
                pid_h2 = subprocess.check_output("pgrep -f 'mininet:h2'", shell=True).decode().strip().split()[0]
                subprocess.run(f"mnexec -a {pid_h2} iperf -s -u -p 5001 -D >/dev/null 2>&1", shell=True)

                pid_h4 = subprocess.check_output("pgrep -f 'mininet:h4'", shell=True).decode().strip().split()[0]
                subprocess.run(f"mnexec -a {pid_h4} iperf -s -u -p 5002 -D >/dev/null 2>&1", shell=True)
            time.sleep(0.5)
        except Exception as e:
            print(f"[!] Cảnh báo khởi động iperf server: {e}")

    def _start_main_flow(self, duration=25, bw_mbps=3.5):
        """
        Luồng dịch vụ chính cần bảo vệ QoS: h1 -> h2 (3.5 Mbps = 35% Load trên P1/P2).
        Giúp quan sát cực rõ % Load khi chuyển sang P2!
        """
        # Dừng iperf client cũ trên h1 (nếu có) trước khi phát luồng mới
        self._cmd('h1', 'killall -9 iperf 2>/dev/null; true')
        time.sleep(0.2)
        self._cmd('h1', f'iperf -c 10.0.0.2 -u -b {bw_mbps}M -t {duration} -p 5001')

    def _auto_revert_to_k1(self):
        """
        Sau khi kịch bản gây nghẽn (K2-K6) kết thúc và mạng ổn định,
        tự động đưa hệ thống về lại kịch bản K1 và tuyến chính P1.
        """
        if self.db.get_system_status('collect_mode', '0') == '1':
            return
        print("\n>>> [AUTO-REVERT] Kịch bản thử nghiệm đã xong. Đang hoàn nguyên về K1 (Tuyến P1)...")
        self.run_k1_normal(duration=60)

    def set_current_scenario(self, scenario_id):
        desc = SCENARIOS.get(scenario_id, "Kịch bản không xác định")
        print(f"\n{'='*75}\n>>> [SCENARIO] KÍCH HOẠT [{scenario_id}]: {desc}\n{'='*75}")
        self.db.set_system_status('current_scenario', scenario_id)

    def run_k1_normal(self, duration=60):
        """K1: Dừng sạch tải nghẽn cũ -> Đợi xả hàng đợi 1.2s -> Đặt lại về P1 và phát tải nhẹ"""
        # 1. Dọn sạch tiến trình iperf gây nghẽn cũ và khôi phục cổng trước tiên
        self._ensure_servers()
        time.sleep(1.0) # Chờ hàng đợi OVS xả sạch 100% gói tin cũ

        # 2. Bây giờ mới đổi trạng thái về K1 và yêu cầu Controller về P1
        self.set_current_scenario('K1')
        self.db.set_system_status('force_reset_path', 'P1')
        self.db.set_system_status('active_path', 'P1')
        self.db.set_system_status('ml_risk', '8.4')
        self.db.set_system_status('ml_pred', '0')
        self.db.set_system_status('system_status', 'NORMAL')

        print(f">>> [K1] Phát luồng chính h1->h2 (3.0M) trên P1 và tải nền nhẹ h3->h4 (0.5M)...")
        self._start_main_flow(duration, bw_mbps=3.0)
        self._cmd('h3', f'iperf -c 10.0.0.4 -u -b 0.5M -t {duration} -p 5002')
        time.sleep(duration)
        print(">>> [K1] Hoàn thành.")

    def run_k2_gradual_load(self, duration=24):
        """K2: Tải nền tăng dần trên link s2-s6, sau đó tự động trả về K1/P1"""
        self.set_current_scenario('K2')
        self._ensure_servers()
        self.db.set_system_status('force_reset_path', 'P1')
        time.sleep(1.0)
        self._start_main_flow(duration + 5, bw_mbps=3.5)
        steps = [2, 4, 6.5, 8.5, 9.5, 9.5]
        step_dur = max(3, int(duration / len(steps)))
        for bw in steps:
            print(f"  + [K2] Bước tải nền h3->h4: {bw} Mbps ({step_dur}s)...")
            self._cmd('h3', f'iperf -c 10.0.0.4 -u -b {bw}M -t {step_dur} -p 5002')
            time.sleep(step_dur)
        print(">>> [K2] Hoàn thành. Chuẩn bị trả về K1 (P1)...")
        self._auto_revert_to_k1()

    def run_k3_sudden_spike(self, duration=20):
        """K3: Tải đột biến (burst spike), sau đó hạ nhiệt và tự động trả về K1/P1"""
        self.set_current_scenario('K3')
        self._ensure_servers()
        self.db.set_system_status('force_reset_path', 'P1')
        time.sleep(1.0)
        self._start_main_flow(duration + 5, bw_mbps=3.5)
        print(">>> [K3] Giai đoạn 1: Tải bình thường 4s...")
        self._cmd('h3', 'iperf -c 10.0.0.4 -u -b 1M -t 4 -p 5002')
        time.sleep(4)
        print(">>> [K3] Giai đoạn 2: BÙNG NỔ TẢI ĐỘT BIẾN (Burst spike 10M) trong 10s...")
        self._cmd('h3', 'iperf -c 10.0.0.4 -u -b 10M -t 10 -p 5002')
        time.sleep(10)
        print(">>> [K3] Giai đoạn 3: Tải hạ nhiệt, ổn định trên P2 thêm 6s trước khi về K1...")
        self._cmd('h3', 'iperf -c 10.0.0.4 -u -b 0.5M -t 6 -p 5002')
        time.sleep(6)
        self._auto_revert_to_k1()

    def run_k4_congestion(self, duration=20):
        """K4: Nghẽn liên tục s2-s6, chuyển sang P2 chạy ổn định rồi tự trả về K1/P1"""
        self.set_current_scenario('K4')
        self._ensure_servers()
        self.db.set_system_status('force_reset_path', 'P1')
        time.sleep(1.0)
        print(f">>> [K4] Gây nghẽn s2-s6 bằng tải nền 9.0M + luồng chính 3.5M trong {duration}s...")
        self._start_main_flow(duration + 2, bw_mbps=3.5)
        self._cmd('h3', f'iperf -c 10.0.0.4 -u -b 9.0M -t {duration} -p 5002')
        time.sleep(duration)
        print(">>> [K4] Hoàn thành. Đang trả về K1 (P1)...")
        self._auto_revert_to_k1()

    def run_k5_degradation(self, duration=20):
        """K5: Suy giảm chất lượng phi tải (netem), chuyển sang P2 rồi tự trả về K1/P1"""
        self.set_current_scenario('K5')
        self._ensure_servers()
        self.db.set_system_status('force_reset_path', 'P1')
        time.sleep(1.0)
        self._start_main_flow(duration + 2, bw_mbps=3.5)
        self._cmd('h3', f'iperf -c 10.0.0.4 -u -b 1.0M -t {duration} -p 5002')
        time.sleep(3)
        print(">>> [K5] Kích hoạt netem trên cổng s2-eth3 (delay 55ms, loss 4.5%)...")
        self._restore_s2_eth3_tc(delay='55ms', loss=4.5)
        self.db.set_system_status('netem_degraded', '1')
        time.sleep(max(5, duration - 3))
        self._restore_s2_eth3_tc(delay='5ms', loss=0)
        self.db.set_system_status('netem_degraded', '0')
        print(">>> [K5] Đã khôi phục s2-eth3. Đang trả về K1 (P1)...")
        self._auto_revert_to_k1()

    def run_k6_link_down(self, duration=18):
        """K6: Đứt liên kết s2-s6, failover sang P2 rồi tự khôi phục về K1/P1"""
        self.set_current_scenario('K6')
        self._ensure_servers()
        self.db.set_system_status('force_reset_path', 'P1')
        time.sleep(1.0)
        self._start_main_flow(duration + 2, bw_mbps=3.5)
        time.sleep(3)
        print(">>> [K6] Ngắt liên kết s2-s6 (cổng s2-eth3)...")
        self.db.set_system_status('link_s2_s6_down', '1')
        subprocess.run("ip link set s2-eth3 down 2>/dev/null || true", shell=True)
        time.sleep(max(8, duration - 3))
        print(">>> [K6] Khôi phục liên kết s2-s6 và trả về K1 (P1)...")
        subprocess.run("ip link set s2-eth3 up 2>/dev/null || true", shell=True)
        self._restore_s2_eth3_tc(delay='5ms', loss=0)
        self.db.set_system_status('link_s2_s6_down', '0')
        self._auto_revert_to_k1()

    def run_dataset_collection(self, cycles=2):
        self.db.set_system_status('collect_mode', '1')
        start_time = time.time()
        try:
            for c in range(1, cycles + 1):
                self.run_k1_normal(duration=20)
                self.run_k2_gradual_load(duration=30)
                self.run_k3_sudden_spike(duration=25)
                self.run_k4_congestion(duration=30)
                self.run_k5_degradation(duration=20)
        finally:
            self.db.set_system_status('collect_mode', '0')
            self.run_k1_normal(duration=10)
            print(f"[HOÀN THÀNH THU THẬP] Tổng thời gian: {round(time.time() - start_time, 1)} giây.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SDN Traffic Scenario Runner')
    parser.add_argument('--scenario', choices=['K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'ALL', 'COLLECT'], default='K1')
    parser.add_argument('--cycles', type=int, default=2)
    args = parser.parse_args()

    runner = TrafficScenarioRunner()
    if args.scenario == 'COLLECT':
        runner.run_dataset_collection(cycles=args.cycles)
    elif args.scenario == 'ALL':
        for sc in ['K1', 'K2', 'K3', 'K4', 'K5', 'K6']:
            getattr(runner, f"run_{sc.lower()}_" + (
                "normal" if sc=='K1' else "gradual_load" if sc=='K2' else "sudden_spike" if sc=='K3' 
                else "congestion" if sc=='K4' else "degradation" if sc=='K5' else "link_down"
            ))(duration=15)
    else:
        func_name = f"run_{args.scenario.lower()}_" + (
            "normal" if args.scenario=='K1' else "gradual_load" if args.scenario=='K2' else "sudden_spike" if args.scenario=='K3' 
            else "congestion" if args.scenario=='K4' else "degradation" if args.scenario=='K5' else "link_down"
        )
        getattr(runner, func_name)()
