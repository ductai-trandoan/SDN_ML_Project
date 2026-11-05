# HƯỚNG DẪN TRIỂN KHAI VÀ VẬN HÀNH TOPOLOGY MININET 
---

## 1. THÔNG SỐ TOPOLOGY MẠNG (FILE `topology.py`)

Hệ thống mô phỏng gồm **6 Open vSwitch (s1 - s6)** và **4 Host (h1 - h4)**, được kết nối theo mô hình **3 đường truyền song song** kết nối từ s1 đến s6:

```text
       [h1]
         | (100M, 1ms)
       [s1] ─── (P1: 10M, 5ms) ───► [s2] ─── (P1: 10M, 5ms) ───► [s6] ─── [h2]
        │                             │                             ▲   (100M, 1ms)
        │                             └─── [h3] (Tải nền)           │
        │                                                           ├─── [h4]
        ├─── (P2: 10M, 10ms) ──► [s3] ──► [s4] ── (10M, 10ms) ──────┤
        │
        └─── (P3: 5M, 10ms)  ──► [s5] ───────── (5M, 10ms) ─────────┘
```

### Chi tiết 3 tuyến truyền dẫn:
1. **Đường 1 (P1 - Tuyến ngắn nhất):** `s1 -> s2 -> s6`  
   - Băng thông: **10 Mbps**, Trễ: **10ms** (5ms mỗi chặng), 2 hop.
   - Đây là tuyến mặc định khi mạng bình thường. Tuyến này có tải nền từ **h3 -> h4** chạy qua liên kết `s2-s6` để gây nghẽn.
2. **Đường 2 (P2 - Tuyến trễ cao, băng thông rộng):** `s1 -> s3 -> s4 -> s6`  
   - Băng thông: **10 Mbps**, Trễ: **30ms** (10ms mỗi chặng), 3 hop.  
   - Dùng để chuyển tuyến khi P1 bị nghẽn tải.
3. **Đường 3 (P3 - Tuyến ít chặng, băng thông thấp):** `s1 -> s5 -> s6`  
   - Băng thông: **5 Mbps**, Trễ: **20ms** (10ms mỗi chặng), 2 hop.  
   - Dự phòng cho các dịch vụ đòi hỏi trễ trung bình nhưng lưu lượng nhỏ.

---

## 2. CÁCH KHỞI CHẠY MININET TRÊN WSL / UBUNTU

### Bước 1: Mở Terminal WSL Ubuntu và di chuyển vào thư mục dự án
```bash
wsl -d Ubuntu-22.04
cd /mnt/d/Project/SDN_ML_Project
```

### Bước 2: Cài đặt môi trường Mininet & Open vSwitch (chỉ cần chạy lần đầu)
```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch openvswitch-testcontroller iperf iproute2 net-tools
sudo service openvswitch-switch start
```

### Bước 3: Khởi động mạng Mininet kết nối Ryu Controller
```bash
sudo python3 topology.py
```
*(Nếu Ryu Controller đang chạy ở một máy khác hoặc IP khác, truyền thêm: `--controller-ip <IP_CỦA_CONTROLLER>`)*

---

## 3. CÁC LỆNH KIỂM THỬ NHANH TRÊN GIAO DIỆN MININET CLI

Sau khi lệnh trên khởi động thành công, màn hình sẽ vào dấu nhắc lệnh `mininet>`. Bạn có thể thử các lệnh sau:

### 1. Kiểm tra kết nối giữa tất cả các node:
```bash
mininet> pingall
```

### 2. Kiểm tra ping đơn giữa h1 và h2:
```bash
mininet> h1 ping -c 4 h2
```

### 3. Kiểm tra thông lượng tối đa giữa h1 và h2 bằng iperf:
```bash
mininet> iperf h1 h2
```

### 4. Mở cửa sổ xterm riêng cho từng host (nếu cần theo dõi trực quan):
```bash
mininet> xterm h1 h2
```

### 5. Thoát Mininet và dọn dẹp sạch sẽ tài nguyên mạng ảo:
```bash
mininet> exit
sudo mn -c
```
*(Lưu ý: Lệnh `sudo mn -c` dùng để xóa sạch các switch ảo bị treo trước khi chạy lại).*

---

## 4. TẠO TẢI GÂY NGHẼN THỰC NGHIỆM (KỊCH BẢN K1 - K6)

Khi Ryu Controller và AI Service đang chạy, bạn chỉ cần mở một terminal khác và gõ:
```bash
sudo python3 experiments/traffic_generator.py
```
Script này sẽ tự động:
- **K1:** Phát luồng nhẹ 2 Mbps h1 -> h2 (mạng bình thường).
- **K2:** Tăng tải nền h3 -> h4 từ 2M đến 12M để kiểm tra khả năng phát hiện tải tăng.
- **K3:** Tạo xung tải đột biến (Burst spike 14M trong 8s).
- **K4:** Gây nghẽn liên tục link `s2-s6` (tải nền 9.5M trên link 10M) -> quan sát Controller tự động chuyển luồng h1-h2 sang P2 (`s1-s3-s4-s6`).
- **K5:** Dùng `tc netem` làm tăng trễ thêm 50ms và rớt gói 4% trên cổng `s2-eth2` -> quan sát Controller chuyển tuyến do suy giảm chất lượng phi tải.
- **K6:** Đánh sập liên kết `s2-s6` để kiểm tra khả năng chuyển mạch khẩn cấp (Failover).

