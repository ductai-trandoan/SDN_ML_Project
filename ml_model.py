"""
MÃ NGUỒN HUẤN LUYỆN VÀ ĐÁNH GIÁ MÔ HÌNH HỌC MÁY (ML MODEL ENTRYPOINT)
Tự động kích hoạt toàn bộ pipeline huấn luyện từ ml_engine:
- Sinh dữ liệu 6 kịch bản thực nghiệm (K1 đến K6)
- Tính đặc trưng chuỗi thời gian (Rolling features)
- Huấn luyện và so sánh: Ngưỡng cố định (Baseline), Random Forest (Chính), Gradient Boosting / XGBoost (So sánh)
- Xuất báo cáo Precision, Recall, F1 và lưu mô hình vào qos_model.pkl
"""

import os
import sys

# Chuyển hướng sang ml_engine.train_models
from ml_engine.train_models import main

if __name__ == "__main__":
    main()
