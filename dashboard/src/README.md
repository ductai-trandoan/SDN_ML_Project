# SDN-ML NOC TELEMETRY CONSOLE (REACT & TAILWIND CSS)

Bảng điều khiển giám sát QoS và điều phối lưu lượng mạng thích ứng theo chuẩn **NOC Industrial Console (Anti-AI Slop)**.

---

## 1. CÁCH XEM TRỰC TIẾP NGAY LẬP TỨC (KHÔNG CẦN CÀI ĐẶT NODE.JS/NPM)

Giao diện đã được tích hợp sẵn dưới dạng **Single Page Application (React 18 + Tailwind CSS)** ngay bên trong file:
`dashboard/templates/index.html`

Bạn có 2 cách xem:
- **Cách 1 (Mở bằng Flask Backend):**
  ```bash
  python dashboard/app.py
  ```
  Sau đó mở trình duyệt tại: `http://127.0.0.1:5000`
- **Cách 2 (Mở trực tiếp file HTML):**
  Nhấp đúp chuột trực tiếp vào file `dashboard/templates/index.html` để mở trong Chrome / Edge / Firefox. Giao diện sẽ tự động chạy chế độ giả lập thời gian thực với đầy đủ các tương tác chuyển kịch bản K1-K6, lọc OpenFlow table và biểu đồ trễ/băng thông.

---

## 2. CẤU TRÚC MÃ NGUỒN REACT MODULAR (TYPESCRIPT)

Nếu bạn muốn copy mã nguồn React vào một dự án Vite hoặc Next.js:
- `Dashboard.tsx`: Component giao diện chính hoàn chỉnh.
- `mockData.ts`: Các kiểu dữ liệu (`SystemMetrics`, `LinkTelemetry`, `FlowEntry`, `DecisionLog`) và tập dữ liệu mô phỏng chuẩn xác 6 Switch Open vSwitch và 3 đường P1, P2, P3.

---

## 3. CÁC QUY CHUẨN THIẾT KẾ ĐÃ ÁP DỤNG (ANTI-AI SLOP)

1. **Hình học phẳng tuyệt đối:** `rounded-none`, không bo tròn, không shadow nhòe, không hiệu ứng kính mờ (glassmorphism), không dải màu gradient tím/xanh.
2. **Bố cục lưới công nghiệp (NOC Telemetry Grid):** Các khối được phân tách bằng đường viền mỏng sắc nét `1px` (`border-zinc-800`), chia theo tỷ lệ 7:3 chuẩn bảng điều khiển mạng viễn thông.
3. **Typography kỹ thuật:** 
   - Số liệu, IP, Flow rules, metrics, timestamps hiển thị bằng font **Monospace** (`JetBrains Mono`).
   - Tiêu đề, nhãn thẻ viết hoa có chủ đích, tracking rộng, kích thước nhỏ `text-[10px]` - `text-[11px]`.
4. **Màu sắc trạng thái viễn thông:**
   - Normal / Active Route: `#10b981` (Emerald)
   - Congestion Warning / Reroute Hold: `#f59e0b` (Amber)
   - Drop / Loss Alert: `#ef4444` (Crimson)
   - Nền tối than kỹ thuật: `#090a0f` (Zinc-950)

