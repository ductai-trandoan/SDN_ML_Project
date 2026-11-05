"""
BỘ TẠO TẢI VÀ THỰC THI 6 KỊCH BẢN THỰC NGHIỆM (K1 - K6)
Tuân thủ Bảng 1.5 trong Báo cáo định kỳ Đợt 1:
- K1: Mạng bình thường, tải nhẹ (iperf 2 Mbps)
- K2: Tải tăng dần (từ 2 Mbps lên 12 Mbps qua s2-s6)
- K3: Tải đột biến (burst spike lên 14 Mbps)
- K4: Nghẽn một liên kết s2-s6 (tải nền h3->h4 đẩy 9.5 Mbps)
- K5: Suy giảm chất lượng không do tải (tc netem tăng trễ 50ms, mất gói 4%)
- K6: Đứt liên kết s2-s6 (kiểm tra khả năng phát hiện đứt và failover)
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
        self.net = net # Đối tượng Mininet nếu chạy bên trong script Mininet
        self.db = DatabaseManager()

    def set_current_scenario(self, scenario_id):
        desc = SCENARIOS.get(scenario_id, "Kịch bản không xác định")
        print(f"\n{'='*70}\n>>> BẮT ĐẦU KỊCH BẢN [{scenario_id}]: {desc}\n{'='*70}")
        self.db.set_system_status('current_scenario', scenario_id)

    def run_k1_normal(self, duration=20):
        """K1: Mạng bình thường, tải nhẹ h1->h2: 2 Mbps"""
        self.set_current_scenario('K1')
        print(f">>> Phát luồng chính h1 -> h2 tốc độ nhẹ 2 Mbps trong {duration}s...")
        if self.net:
            h1 = self.net.get('h1')
            h2 = self.net.get('h2')
            h2.cmd('iperf -s -u -p 5001 &')
            h1.cmd(f'iperf -c 10.0.0.2 -u -b 2M -t {duration} -p 5001 &')
        time.sleep(duration)
        print(">>> Kịch bản K1 hoàn thành.")

    def run_k2_gradual_load(self, duration=35):
        """K2: Tải tăng dần từ 2M lên 12M qua s2-s6"""
        self.set_current_scenario('K2')
        print(">>> Tải nền h3 -> h4 tăng dần từng bước (2M -> 4M -> 6M -> 8M -> 10M -> 12M)...")
        steps = [2, 4, 6, 8, 10, 12]
        step_duration = duration / len(steps)
        
        for bw in steps:
            print(f"  + Bước tải nền: {bw} Mbps (thời gian {step_duration:.1f}s)...")
            if self.net:
                h3 = self.net.get('h3')
                h4 = self.net.get('h4')
                h4.cmd('iperf -s -u -p 5002 &')
                h3.cmd(f'iperf -c 10.0.0.4 -u -b {bw}M -t {int(step_duration)} -p 5002 &')
            time.sleep(step_duration)
        print(">>> Kịch bản K2 hoàn thành.")

    def run_k3_sudden_spike(self, duration=25):
        """K3: Tải đột biến (burst spike lên 14 Mbps trong 8s)"""
        self.set_current_scenario('K3')
        print(">>> Giai đoạn 1: Chạy tải nhẹ 5s...")
        time.sleep(5)
        print(">>> Giai đoạn 2: BÙNG NỔ TẢI ĐỘT BIẾN (Burst spike 14 Mbps) trong 8s...")
        if self.net:
            h3 = self.net.get('h3')
            h4 = self.net.get('h4')
            h4.cmd('iperf -s -u -p 5002 &')
            h3.cmd('iperf -c 10.0.0.4 -u -b 14M -t 8 -p 5002 &')
        time.sleep(8)
        print(">>> Giai đoạn 3: Tải hạ nhiệt trở lại bình thường...")
        time.sleep(duration - 13)
        print(">>> Kịch bản K3 hoàn thành.")

    def run_k4_congestion(self, duration=30):
        """K4: Nghẽn liên tục một liên kết s2-s6 (tải nền h3->h4 đẩy 9.5 Mbps trên link 10 Mbps)"""
        self.set_current_scenario('K4')
        print(f">>> Phát tải nền h3 -> h4 liên tục 9.5 Mbps gây nghẽn liên kết s2-s6 trong {duration}s...")
        if self.net:
            h3 = self.net.get('h3')
            h4 = self.net.get('h4')
            h4.cmd('iperf -s -u -p 5002 &')
            h3.cmd(f'iperf -c 10.0.0.4 -u -b 9.5M -t {duration} -p 5002 &')
        time.sleep(duration)
        print(">>> Kịch bản K4 hoàn thành.")

    def run_k5_degradation(self, duration=30):
        """K5: Suy giảm chất lượng phi tải (tc netem tăng trễ 50ms, mất gói 4% trên s2-eth2)"""
        self.set_current_scenario('K5')
        print(">>> Kích hoạt suy giảm bằng lệnh tc netem trên cổng nối s2 -> s6 (trễ +50ms, loss 4%)...")
        if self.net:
            s2 = self.net.get('s2')
            # Cổng 2 của s2 kết nối với s6
            s2.cmd('tc qdisc add dev s2-eth2 root netem delay 50ms loss 4%')
        time.sleep(duration)
        if self.net:
            s2 = self.net.get('s2')
            s2.cmd('tc qdisc del dev s2-eth2 root')
        print(">>> Đã khôi phục trạng thái ban đầu của s2. Kịch bản K5 hoàn thành.")

    def run_k6_link_down(self, duration=25):
        """K6: Đứt liên kết s2-s6 (kiểm tra khôi phục và chuyển hướng)"""
        self.set_current_scenario('K6')
        print(">>> Ngắt liên kết s2 - s6...")
        if self.net:
            self.net.configLinkStatus('s2', 's6', 'down')
        time.sleep(duration - 5)
        print(">>> Khôi phục lại liên kết s2 - s6...")
        if self.net:
            self.net.configLinkStatus('s2', 's6', 'up')
        time.sleep(5)
        print(">>> Kịch bản K6 hoàn thành.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SDN Traffic Scenario Runner')
    parser.add_argument('--scenario', choices=['K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'ALL'], default='K4',
                        help='Mã kịch bản cần thực thi')
    args = parser.parse_args()

    runner = TrafficScenarioRunner()
    if args.scenario == 'K1':
        runner.run_k1_normal()
    elif args.scenario == 'K2':
        runner.run_k2_gradual_load()
    elif args.scenario == 'K3':
        runner.run_k3_sudden_spike()
    elif args.scenario == 'K4':
        runner.run_k4_congestion()
    elif args.scenario == 'K5':
        runner.run_k5_degradation()
    elif args.scenario == 'K6':
        runner.run_k6_link_down()
    elif args.scenario == 'ALL':
        for sc in ['K1', 'K2', 'K3', 'K4', 'K5', 'K6']:
            getattr(runner, f"run_{sc.lower()}_" + (
                "normal" if sc=='K1' else "gradual_load" if sc=='K2' else "sudden_spike" if sc=='K3' 
                else "congestion" if sc=='K4' else "degradation" if sc=='K5' else "link_down"
            ))(duration=15)
