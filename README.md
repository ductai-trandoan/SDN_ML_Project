# ĐỒ ÁN TỐT NGHIỆP: GIÁM SÁT QoS VÀ ĐIỀU PHỐI LƯU LƯỢNG MẠNG SDN + HỌC MÁY

- **Đề tài:** Nghiên cứu, xây dựng hệ thống giám sát chất lượng dịch vụ và điều phối lưu lượng mạng thích ứng dựa trên SDN và học máy
- **GVHD:** ThS. Nguyễn Minh Tâm
- **Sinh viên:** Đặng Văn Chương (N22DCCN012), Trần Đoàn Đức Tài (N22DCCN072) - Lớp: D22CQCNMT01-N (PTIT)

---

## 1. TIẾN ĐỘ CÁC PHẦN ĐÃ LÀM

### 1. Mạng giả lập (Mininet)
- Đã dựng xong topology 6 switch Open vSwitch (`s1` đến `s6`) và 4 host trong file `topology.py`.
- Đã chia sẵn 3 đường truyền song song từ `s1` đến `s6`:
  - Đường 1 (P1): `s1 -> s2 -> s6` (10 Mbps, trễ 10ms, đường ngắn nhất mặc định).
  - Đường 2 (P2): `s1 -> s3 -> s4 -> s6` (10 Mbps, trễ 30ms, đường dự phòng băng thông cao).
  - Đường 3 (P3): `s1 -> s5 -> s6` (5 Mbps, trễ 20ms, đường dự phòng ít chặng).
- Đã cấu hình luồng tải nền chạy chéo từ `h3 -> h4` qua đoạn `s2-s6` để chủ động gây nghẽn đường P1 khi cần test.

### 2. Bộ điều khiển (Ryu Controller)
- Chạy trên OpenFlow 1.3 trong file `controller.py`.
- Tự động nhận diện switch khi kết nối và cài đặt luồng cơ bản.
- Đã có vòng lặp 1 giây gửi lệnh `OFPPortStatsRequest` để lấy dung lượng cổng và tính thông lượng (Throughput) theo thời gian thực.
- Đã viết thuật toán tính chi phí đường đi dựa trên 4 chỉ số: độ trễ, jitter, mất gói và mức sử dụng băng thông.
- Đã cài cơ chế chuyển luồng an toàn (Make-Before-Break): khi chuyển từ đường cũ sang đường mới thì cài luật ưu tiên cao cho đường mới chạy trước, 2 giây sau mới dỡ đường cũ để không rớt gói. Có thêm biến giữ 10 giây để tránh việc đường bị nhảy liên tục.

### 3. Phần Học máy (Machine Learning)
- Đã lập trình xong quy trình trích xuất 12 đặc trưng (vừa lấy tức thời, vừa lấy giá trị trượt trung bình, độ biến động và gia tốc tăng tải trong 5 giây gần nhất).
- Đã huấn luyện thử nghiệm mô hình Random Forest trong file `ml_engine/train_models.py`. Đánh giá cả 2 việc: phát hiện nghẽn tức thời và dự báo trước 5 giây xem có nghẽn không.
- Kết quả kiểm thử sơ bộ: điểm F1 đạt trên 99%, thời gian AI chạy dự đoán cực nhanh (mất khoảng 0.025 mili-giây mỗi lần gọi).
- Đã xuất sẵn 4 file biểu đồ chất lượng cao trong thư mục `ml_engine/plots/` (biểu đồ ROC, ma trận nhầm lẫn, so sánh F1 và mức độ quan trọng của các đặc trưng) để đưa vào báo cáo.
- Đã viết dịch vụ chạy nền `ml_service.py` mở cổng API 5001 để Controller gọi sang hỏi kết quả dự đoán.

### 4. Giao diện theo dõi (Dashboard)
- Đã viết xong giao diện web trong `dashboard/templates/index.html` bằng React và Tailwind CSS.
- Thiết kế theo phong cách bảng điều khiển kỹ thuật NOC viễn thông: nền tối, phẳng, hiển thị thẳng các thông số kỹ thuật (RTT, Jitter, Packet Loss, Throughput, Flow Table, sơ đồ trạng thái 3 đường mạng và nhật ký chuyển tuyến).
- Đã tích hợp sẵn 6 nút bấm chọn nhanh các kịch bản thử nghiệm ngay trên web để tiện demo.

### 5. Kịch bản thử nghiệm
- Đã viết xong file `experiments/traffic_generator.py` chứa 6 kịch bản tải thực tế:
  - K1: Tải nhẹ bình thường (2 Mbps).
  - K2: Tải tăng dần từng nấc từ 2 lên 12 Mbps.
  - K3: Tải đột biến tăng vọt trong 8 giây rồi hạ.
  - K4: Bơm tải nền 9.5 Mbps làm nghẽn chết đoạn `s2-s6`.
  - K5: Dùng lệnh `tc netem` làm tăng trễ 50ms và làm rớt gói 4% (suy giảm chất lượng không do tải).
  - K6: Đánh sập liên kết để kiểm tra khả năng phục hồi mạng.

---

## 2. NHỮNG VIỆC CÒN LẠI CẦN LÀM

Dưới đây là các đầu việc còn thiếu cần hoàn thiện để đồ án chuẩn chỉnh, đúng thực tế và không bị bắt bẻ khi bảo vệ:

- [ ] **Đổi cách đo Độ trễ và Mất gói trong Controller sang đo thật:**
  Hiện tại Throughput thì đọc đúng từ switch rồi, nhưng Trễ và Mất gói đang tính mẹo bằng công thức ước lượng từ mức tải. Cần sửa code `controller.py`:
  - Gửi gói tin probe (hoặc LLDP) có gắn mốc thời gian để tính Round-Trip Time (RTT) thực tế giữa các switch.
  - Dùng công thức đếm gói: lấy số gói gửi ra ở switch trước trừ đi số gói nhận vào ở switch sau để tính tỉ lệ mất gói thật.

- [ ] **Thu thập tập dữ liệu thực tế từ Mininet để train lại AI:**
  Dữ liệu hiện tại trong file `dataset_qos.csv` là do script toán học tự sinh ra để test code chạy trước. Cần làm theo đúng quy trình thực nghiệm:
  - Chạy Mininet thật, bật lần lượt các kịch bản K1 đến K6 từ 20 đến 30 phút.
  - Cho Controller ghi toàn bộ số liệu đo thật từng giây vào database SQLite.
  - Xuất dữ liệu đó ra file CSV thật rồi chạy lại `train_models.py` để lấy số liệu thực nghiệm chuẩn và cập nhật lại các ảnh biểu đồ.

- [ ] **Chạy thực nghiệm so sánh thuật toán bằng iperf3 thật:**
  File `evaluate_baselines.py` hiện đang dùng số liệu mô phỏng. Cần đổi sang chạy thực tế trên Mininet với 3 chế độ:
  1. Chế độ 1: Định tuyến đường ngắn nhất cố định (Shortest Path - luôn bám P1).
  2. Chế độ 2: Chia tải tĩnh / ECMP.
  3. Chế độ 3: Dùng giải pháp của đề tài (SDN + AI chuyển tuyến tự động).
  - Hứng kết quả iperf3 và lệnh ping thật xuất ra file log.
  - Vẽ biểu đồ so sánh: Throughput theo thời gian, biểu đồ biến thiên độ trễ, và đo thời gian mạng phục hồi sau khi bị nghẽn (Reroute latency).

- [ ] **Hoàn thiện Thuyết minh Luận văn tốt nghiệp:**
  - Viết Chương 1: Cơ sở lý thuyết về mạng SDN, OpenFlow 1.3 và các chỉ số đo lường QoS.
  - Viết Chương 2: Lý thuyết về học máy trong dự đoán nghẽn mạng và xử lý chuỗi thời gian.
  - Viết Chương 3: Thiết kế kiến trúc hệ thống, sơ đồ mạng, thuật toán chọn đường và Dashboard.
  - Viết Chương 4: Kết quả thực nghiệm đo đạc, phân tích độ chính xác của AI và biểu đồ so sánh với các thuật toán cơ sở.

- [ ] **Quay video demo dự phòng:**
  Quay lại màn hình một lượt chạy hoàn chỉnh: bật Mininet, bật Ryu Controller, bật Dashboard, bơm tải nghẽn vào thấy AI cảnh báo và luồng tự động nhảy mượt mà sang đường P2 không bị rớt gói (đề phòng hôm lên trường bảo vệ máy ảo hoặc mạng bị trục trặc).

---

## 3. Cách chạy nhanh hệ thống

1. **Xem Dashboard & Test AI trên Windows:**
   - Chạy lệnh: `python dashboard/app.py` rồi mở trình duyệt vào `http://127.0.0.1:5000` (hoặc nhấp đúp thẳng vào file `dashboard/templates/index.html`).
   - Chạy kiểm tra mô hình AI: `python ml_engine/train_models.py`.

2. **Chạy mạng Mininet trên WSL 2 (Ubuntu 22.04):**
   - Mở terminal WSL vào thư mục dự án: `cd /mnt/d/Project/SDN_ML_Project`.
   - Bật switch ảo: `sudo service openvswitch-switch start`.
   - Chạy Controller: `ryu-manager controller.py`.
   - Mở terminal khác bật mạng: `sudo python3 topology.py`.
   - Chi tiết thêm xem trong file [`HUONG_DAN_MININET.md`](./HUONG_DAN_MININET.md).

#Có nhu cầu nâng cấp thì từ từ tính. Hoàn thiện cơ bản đi đã.