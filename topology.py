"""
TOPOLOGY MẠNG SDN VỚI BA ĐƯỜNG TRUYỀN SONG SONG
Tuân thủ thiết kế mục 2.3 (Bảng 2.3 & Hình 2.2) trong Báo cáo Đợt 1 ĐATN:
- 6 Switch Open vSwitch: s1 đến s6
- 4 Host:
    + h1 (10.0.0.1): Nguồn luồng dịch vụ chính cần bảo vệ QoS
    + h2 (10.0.0.2): Đích luồng dịch vụ chính
    + h3 (10.0.0.3): Host phát tải nền gây nghẽn (kết nối s2)
    + h4 (10.0.0.4): Host nhận tải nền gây nghẽn (kết nối s6)
- 3 Đường song song giữa s1 và s6:
    + Đường 1 (P1): s1 - s2 - s6 (10 Mbps, 5ms/link -> tổng 10ms). Chặng ngắn nhất, trễ thấp nhất.
    + Đường 2 (P2): s1 - s3 - s4 - s6 (10 Mbps, 10ms/link -> tổng 30ms). Băng thông cao, trễ lớn.
    + Đường 3 (P3): s1 - s5 - s6 (5 Mbps, 10ms/link -> tổng 20ms). Ít chặng, băng thông trung bình.
- Liên kết Host - Switch: 100 Mbps, 1ms.
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink, TCIntf
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import sys
import argparse

# Khử cảnh báo sch_htb của Linux kernel để giao diện dòng lệnh sạch sẽ, dễ nhìn
_orig_tc = TCIntf.tc
def _quiet_tc(self, cmd, *args, **kwargs):
    res = _orig_tc(self, cmd, *args, **kwargs)
    if res and 'Warning: sch_htb' in res:
        res = '\n'.join([line for line in res.splitlines() if 'Warning: sch_htb' not in line])
    return res
TCIntf.tc = _quiet_tc

class SDNMultipathTopo(Topo):
    """Lớp xây dựng topology mạng 6 switch theo đúng Báo cáo Đợt 1"""
    
    def build(self):
        info("*** 1. Đang tạo các Switch Open vSwitch (s1 - s6)... \n")
        # Khởi tạo 6 Switch với DPID tương ứng (dpid dạng hex string 16 ký tự)
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13', dpid='0000000000000001')
        s2 = self.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13', dpid='0000000000000002')
        s3 = self.addSwitch('s3', cls=OVSKernelSwitch, protocols='OpenFlow13', dpid='0000000000000003')
        s4 = self.addSwitch('s4', cls=OVSKernelSwitch, protocols='OpenFlow13', dpid='0000000000000004')
        s5 = self.addSwitch('s5', cls=OVSKernelSwitch, protocols='OpenFlow13', dpid='0000000000000005')
        s6 = self.addSwitch('s6', cls=OVSKernelSwitch, protocols='OpenFlow13', dpid='0000000000000006')

        info("*** 2. Đang tạo các End-Hosts (h1 - h4)... \n")
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

        info("*** 3. Đang cấu hình liên kết Host - Switch (100 Mbps, 1ms)... \n")
        self.addLink(h1, s1, bw=100, delay='1ms', loss=0, use_htb=True)
        self.addLink(h2, s6, bw=100, delay='1ms', loss=0, use_htb=True)
        self.addLink(h3, s2, bw=100, delay='1ms', loss=0, use_htb=True)
        self.addLink(h4, s6, bw=100, delay='1ms', loss=0, use_htb=True)

        info("*** 4. Đang cấu hình Đường 1 (P1): s1 - s2 - s6 (10 Mbps, 5ms)... \n")
        self.addLink(s1, s2, bw=10, delay='5ms', loss=0, use_htb=True)
        self.addLink(s2, s6, bw=10, delay='5ms', loss=0, use_htb=True)

        info("*** 5. Đang cấu hình Đường 2 (P2): s1 - s3 - s4 - s6 (10 Mbps, 10ms)... \n")
        self.addLink(s1, s3, bw=10, delay='10ms', loss=0, use_htb=True)
        self.addLink(s3, s4, bw=10, delay='10ms', loss=0, use_htb=True)
        self.addLink(s4, s6, bw=10, delay='10ms', loss=0, use_htb=True)

        info("*** 6. Đang cấu hình Đường 3 (P3): s1 - s5 - s6 (5 Mbps, 10ms)... \n")
        self.addLink(s1, s5, bw=5, delay='10ms', loss=0, use_htb=True)
        self.addLink(s5, s6, bw=5, delay='10ms', loss=0, use_htb=True)

def run(controller_ip='127.0.0.1', controller_port=6653):
    """Khởi động hệ thống mạng Mininet kết nối tới Ryu Controller"""
    setLogLevel('info')
    topo = SDNMultipathTopo()
    
    info(f"*** Khởi tạo mạng Mininet với Controller tại {controller_ip}:{controller_port}... \n")
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip=controller_ip, port=controller_port),
        switch=OVSKernelSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True
    )
    
    net.start()
    info("\n=======================================================\n")
    info("*** HE THONG MANG 6 SWITCH DA KHOI TAO THANH CONG!\n")
    info("*** GO 'pingall' DE KIEM TRA KET NOI GIUA CAC MAY\n")
    info("*** GO 'exit' DE THOAT VA DON DEP MANG\n")
    info("=======================================================\n\n")
    CLI(net)
    
    info("*** Đang dừng Mininet và dọn dẹp các switch ảo...\n")
    net.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mininet 6-Switch Multipath SDN Topology')
    parser.add_argument('--controller-ip', default='127.0.0.1', help='IP của Ryu Controller')
    parser.add_argument('--controller-port', type=int, default=6653, help='Port OpenFlow của Ryu Controller')
    args = parser.parse_args()
    
    run(controller_ip=args.controller_ip, controller_port=args.controller_port)
