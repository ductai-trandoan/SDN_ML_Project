"""
HUẤN LUYỆN, ĐÁNH GIÁ VÀ TRỰC QUAN HÓA CÁC MÔ HÌNH HỌC MÁY (SDN QoS)
Nâng cấp toàn diện cho ĐATN:
- Bổ sung Logistic Regression, Random Forest (Balanced), Gradient Boosting
- Tính toán đầy đủ: Accuracy, Precision, Recall, F1-Score, ROC-AUC, Inference Latency
- Trực quan hóa và tự động lưu 4 biểu đồ khoa học vào thư mục ml_engine/plots/
  1. feature_importance.png: Tầm quan trọng đặc trưng trong dự đoán sớm
  2. confusion_matrices.png: Ma trận nhầm lẫn chi tiết
  3. roc_curves.png: Đường cong ROC & chỉ số AUC
  4. model_comparison_metrics.png: Biểu đồ cột so sánh tổng thể
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use('Agg') # Không cần giao diện GUI, chỉ xuất file PNG
import matplotlib.pyplot as plt

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_auc_score, roc_curve
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONGESTION_UTIL_THRESHOLD, CONGESTION_LOSS_THRESHOLD
from ml_engine.dataset_generator import generate_full_dataset, add_time_series_features

# Danh sách 12 đặc trưng đầu vào (Instantaneous & Rolling Features)
FEATURE_COLS = [
    'throughput_mbps',
    'utilization_pct',
    'latency_ms',
    'jitter_ms',
    'loss_pct',
    'util_rolling_mean',
    'util_rolling_std',
    'util_rolling_max',
    'util_diff',
    'latency_rolling_mean',
    'latency_rolling_max',
    'loss_rolling_mean'
]

# Tên thân thiện cho biểu đồ
FEATURE_NAMES_VI = [
    'Thông lượng (Mbps)',
    'Mức sử dụng (%)',
    'Độ trễ (ms)',
    'Jitter (ms)',
    'Tỉ lệ mất gói (%)',
    'Tải TB trượt 5s (%)',
    'Độ lệch chuẩn tải 5s',
    'Tải cực đại 5s (%)',
    'Gia tốc tăng tải (Δu)',
    'Trễ TB trượt 5s (ms)',
    'Trễ cực đại 5s (ms)',
    'Mất gói TB trượt 5s (%)'
]

def load_or_create_data():
    """Tải dữ liệu từ CSV hoặc tự sinh nếu chưa tồn tại"""
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(cur_dir, "dataset_qos.csv")
    if os.path.exists(csv_path):
        print(f">>> Đọc dữ liệu từ: {csv_path}")
        df = pd.read_csv(csv_path)
    else:
        df = generate_full_dataset(samples_per_scenario=600, save_to_db=True)
    return df

def evaluate_threshold_baseline(df_test, target_col='label_now'):
    """Đánh giá phương pháp Ngưỡng cố định (Fixed Threshold Baseline)"""
    y_test = df_test[target_col].values
    start_time = time.time()
    
    # Luật: Tải >= 80% hoặc Loss >= 2%
    y_pred = ((df_test['utilization_pct'] >= CONGESTION_UTIL_THRESHOLD) | 
              (df_test['loss_pct'] >= CONGESTION_LOSS_THRESHOLD)).astype(int).values
    inf_time_ms = ((time.time() - start_time) / len(df_test)) * 1000.0

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred).tolist()
    
    # Tính ROC-AUC giả định từ nhãn nhị phân
    try:
        auc = roc_auc_score(y_test, y_pred)
    except Exception:
        auc = 0.5

    return {
        'model_name': 'Ngưỡng cố định (Threshold)',
        'target': target_col,
        'accuracy': round(float(acc), 4),
        'precision': round(float(prec), 4),
        'recall': round(float(rec), 4),
        'f1_score': round(float(f1), 4),
        'roc_auc': round(float(auc), 4),
        'confusion_matrix': cm,
        'inference_time_ms': round(float(inf_time_ms), 4),
        'train_time_sec': 0.0,
        'y_pred': y_pred,
        'y_prob': y_pred.astype(float)
    }

def train_and_eval_model(model, model_name, X_train, y_train, X_test, y_test, target_col):
    """Huấn luyện và đánh giá mô hình học máy"""
    print(f"  + Huấn luyện {model_name} [{target_col}]...")
    start_train = time.time()
    model.fit(X_train, y_train)
    train_duration = time.time() - start_train

    # Đo thời gian suy luận (Inference Latency)
    start_inf = time.time()
    y_pred = model.predict(X_test)
    inf_time_ms = ((time.time() - start_inf) / len(X_test)) * 1000.0

    y_prob = None
    auc = 0.5
    if hasattr(model, 'predict_proba'):
        y_prob = model.predict_proba(X_test)[:, 1]
        try:
            auc = roc_auc_score(y_test, y_prob)
        except Exception:
            auc = 0.5

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred).tolist()

    feature_importances = {}
    if hasattr(model, 'feature_importances_'):
        for name, imp in zip(FEATURE_COLS, model.feature_importances_):
            feature_importances[name] = round(float(imp), 4)

    return {
        'model_name': model_name,
        'target': target_col,
        'accuracy': round(float(acc), 4),
        'precision': round(float(prec), 4),
        'recall': round(float(rec), 4),
        'f1_score': round(float(f1), 4),
        'roc_auc': round(float(auc), 4),
        'confusion_matrix': cm,
        'inference_time_ms': round(float(inf_time_ms), 4),
        'train_time_sec': round(float(train_duration), 3),
        'feature_importances': feature_importances,
        'y_pred': y_pred,
        'y_prob': y_prob if y_prob is not None else y_pred.astype(float)
    }

def export_visualization_plots(plots_dir, results_dict, rf_now, rf_pred, X_test, y_test_now, y_test_pred):
    """Xuất các biểu đồ trực quan hóa phục vụ Luận văn và Slide báo cáo"""
    os.makedirs(plots_dir, exist_ok=True)
    plt.rcParams['font.sans-serif'] = 'Arial'
    plt.rcParams['axes.edgecolor'] = '#cbd5e1'
    plt.rcParams['axes.linewidth'] = 0.8

    # 1. BIỂU ĐỒ TẦM QUAN TRỌNG CỦA CÁC ĐẶC TRƯNG (FEATURE IMPORTANCE)
    print(">>> Đang xuất biểu đồ: Feature Importance...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Bài toán 1: label_now
    imp_now = rf_now.feature_importances_
    idx_now = np.argsort(imp_now)
    ax1.barh(np.array(FEATURE_NAMES_VI)[idx_now], imp_now[idx_now], color='#38bdf8')
    ax1.set_title('Phát hiện nghẽn tức thời (t)', fontsize=12, fontweight='bold', pad=10)
    ax1.set_xlabel('Mức độ quan trọng (Gini Importance)')
    ax1.grid(axis='x', linestyle='--', alpha=0.5)

    # Bài toán 2: label_pred (H = 5s)
    imp_pred = rf_pred.feature_importances_
    idx_pred = np.argsort(imp_pred)
    ax2.barh(np.array(FEATURE_NAMES_VI)[idx_pred], imp_pred[idx_pred], color='#10b981')
    ax2.set_title('Dự đoán sớm nguy cơ nghẽn (t + 5s)', fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel('Mức độ quan trọng (Gini Importance)')
    ax2.grid(axis='x', linestyle='--', alpha=0.5)

    plt.tight_layout()
    feat_path = os.path.join(plots_dir, 'feature_importance.png')
    plt.savefig(feat_path, dpi=300)
    plt.close()

    # 2. BIỂU ĐỒ MA TRẬN NHẦM LẪN (CONFUSION MATRICES)
    print(">>> Đang xuất biểu đồ: Confusion Matrices...")
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    models_to_plot = ['Ngưỡng cố định (Threshold)', 'Random Forest', 'Gradient Boosting']

    for row_idx, (target_name, y_true) in enumerate([('label_now', y_test_now), ('label_pred', y_test_pred)]):
        target_results = results_dict[target_name]
        for col_idx, m_name in enumerate(models_to_plot):
            res = next(r for r in target_results if m_name in r['model_name'])
            cm = np.array(res['confusion_matrix'])
            ax = axes[row_idx, col_idx]
            
            im = ax.imshow(cm, cmap='Blues', interpolation='nearest')
            title_prefix = "Phát hiện (t)" if target_name == 'label_now' else "Dự đoán (t+5s)"
            ax.set_title(f"{title_prefix}\n{m_name}", fontsize=11, fontweight='bold')
            ax.set_xticks([0, 1])
            ax.set_yticks([0, 1])
            ax.set_xticklabels(['Bình thường', 'Nghẽn'])
            ax.set_yticklabels(['Bình thường', 'Nghẽn'])
            ax.set_xlabel('Dự đoán (Predicted)')
            ax.set_ylabel('Thực tế (Actual)')

            for i in range(2):
                for j in range(2):
                    ax.text(j, i, format(cm[i, j], 'd'),
                            ha="center", va="center",
                            color="white" if cm[i, j] > cm.max() / 2.0 else "black",
                            fontweight='bold', fontsize=12)

    plt.tight_layout()
    cm_path = os.path.join(plots_dir, 'confusion_matrices.png')
    plt.savefig(cm_path, dpi=300)
    plt.close()

    # 3. BIỂU ĐỒ ĐƯỜNG CONG ROC & AUC
    print(">>> Đang xuất biểu đồ: ROC Curves...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    
    colors = {'Threshold': '#94a3b8', 'Logistic Regression': '#f59e0b', 'Random Forest': '#38bdf8', 'Gradient Boosting': '#10b981'}

    for ax, target_name, y_true, title in [
        (ax1, 'label_now', y_test_now, 'ROC Curve: Phát hiện nghẽn tức thời (t)'),
        (ax2, 'label_pred', y_test_pred, 'ROC Curve: Dự đoán sớm nghẽn (t + 5s)')
    ]:
        for res in results_dict[target_name]:
            fpr, tpr, _ = roc_curve(y_true, res['y_prob'])
            label_text = f"{res['model_name']} (AUC = {res['roc_auc']:.3f})"
            color = next((c for k, c in colors.items() if k in res['model_name']), '#64748b')
            ax.plot(fpr, tpr, label=label_text, color=color, linewidth=2)
            
        ax.plot([0, 1], [0, 1], 'k--', alpha=0.4, label='Ngẫu nhiên (AUC = 0.50)')
        ax.set_title(title, fontsize=12, fontweight='bold', pad=10)
        ax.set_xlabel('Tỉ lệ dương tính giả (False Positive Rate)')
        ax.set_ylabel('Tỉ lệ dương tính thật (True Positive Rate)')
        ax.legend(loc='lower right', fontsize=9)
        ax.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    roc_path = os.path.join(plots_dir, 'roc_curves.png')
    plt.savefig(roc_path, dpi=300)
    plt.close()

    # 4. BIỂU ĐỒ CỘT SO SÁNH HIỆU NĂNG TỔNG THỂ
    print(">>> Đang xuất biểu đồ: Performance Metrics Bar Chart...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # So sánh F1-Score cho cả 2 bài toán
    model_names_short = ['Ngưỡng (Threshold)', 'Logistic Reg.', 'Random Forest', 'Gradient Boosting']
    f1_now = [r['f1_score'] * 100 for r in results_dict['label_now']]
    f1_pred = [r['f1_score'] * 100 for r in results_dict['label_pred']]
    
    x = np.arange(len(model_names_short))
    width = 0.35
    ax1.bar(x - width/2, f1_now, width, label='Phát hiện (t)', color='#38bdf8')
    ax1.bar(x + width/2, f1_pred, width, label='Dự đoán sớm (t+5s)', color='#10b981')
    ax1.set_ylabel('F1-Score (%)', fontsize=11)
    ax1.set_title('So sánh F1-Score giữa các mô hình', fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(model_names_short, rotation=15, ha='right')
    ax1.set_ylim(0, 105)
    ax1.legend()
    ax1.grid(axis='y', linestyle='--', alpha=0.5)

    # Thời gian suy luận (Inference Latency - ms)
    inf_times = [r['inference_time_ms'] for r in results_dict['label_pred']]
    ax2.bar(model_names_short, inf_times, color='#f59e0b', width=0.5)
    ax2.set_ylabel('Thời gian suy luận / mẫu (ms)', fontsize=11)
    ax2.set_title('Thời gian suy luận (Inference Latency)', fontsize=12, fontweight='bold')
    ax2.set_xticklabels(model_names_short, rotation=15, ha='right')
    ax2.grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    bar_path = os.path.join(plots_dir, 'model_comparison_metrics.png')
    plt.savefig(bar_path, dpi=300)
    plt.close()

    print(f">>> Đã lưu toàn bộ 4 biểu đồ trực quan hóa vào: {plots_dir}")

def main():
    print("=" * 75)
    print("HUẤN LUYỆN VÀ ĐÁNH GIÁ CHUYÊN SÂU MÔ HÌNH HỌC MÁY (SDN QoS)")
    print("=" * 75)

    df = load_or_create_data()
    if 'util_rolling_mean' not in df.columns:
        df = add_time_series_features(df)

    # Phân chia 70% Train, 30% Test theo thời gian của từng kịch bản
    train_dfs, test_dfs = [], []
    for sc in df['scenario_id'].unique():
        sc_df = df[df['scenario_id'] == sc]
        split_idx = int(len(sc_df) * 0.7)
        train_dfs.append(sc_df.iloc[:split_idx])
        test_dfs.append(sc_df.iloc[split_idx:])

    df_train = pd.concat(train_dfs, ignore_index=True)
    df_test = pd.concat(test_dfs, ignore_index=True)

    print(f">>> Số lượng mẫu huấn luyện: {len(df_train)}")
    print(f">>> Số lượng mẫu kiểm thử:   {len(df_test)}")

    X_train = df_train[FEATURE_COLS]
    X_test = df_test[FEATURE_COLS]

    results_dict = {'label_now': [], 'label_pred': []}

    # =========================================================================
    # BÀI TOÁN 1: PHÁT HIỆN NGHẼN TỨC THỜI (label_now)
    # =========================================================================
    print("\n--- [BÀI TOÁN 1: PHÁT HIỆN NGHẼN TỨC THỜI (label_now)] ---")
    y_train_now = df_train['label_now']
    y_test_now = df_test['label_now']

    # 1. Baseline: Fixed Threshold
    results_dict['label_now'].append(evaluate_threshold_baseline(df_test, 'label_now'))

    # 2. Logistic Regression (Baseline tuyến tính)
    lr_now = LogisticRegression(max_iter=1000, random_state=42)
    results_dict['label_now'].append(train_and_eval_model(lr_now, 'Logistic Regression', X_train, y_train_now, X_test, y_test_now, 'label_now'))

    # 3. Random Forest (Mô hình chính, xử lý mất cân bằng lớp)
    rf_now = RandomForestClassifier(n_estimators=100, max_depth=6, class_weight='balanced', random_state=42)
    results_dict['label_now'].append(train_and_eval_model(rf_now, 'Random Forest', X_train, y_train_now, X_test, y_test_now, 'label_now'))

    # 4. Gradient Boosting (Mô hình Boosting)
    gb_now = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
    results_dict['label_now'].append(train_and_eval_model(gb_now, 'Gradient Boosting', X_train, y_train_now, X_test, y_test_now, 'label_now'))

    # =========================================================================
    # BÀI TOÁN 2: DỰ ĐOÁN SỚM NGUY CƠ NGHẼN TRƯỚC H=5s (label_pred)
    # =========================================================================
    print("\n--- [BÀI TOÁN 2: DỰ ĐOÁN SỚM NGUY CƠ NGHẼN TRƯỚC H=5s (label_pred)] ---")
    y_train_pred = df_train['label_pred']
    y_test_pred = df_test['label_pred']

    # 1. Baseline: Fixed Threshold
    results_dict['label_pred'].append(evaluate_threshold_baseline(df_test, 'label_pred'))

    # 2. Logistic Regression
    lr_pred = LogisticRegression(max_iter=1000, random_state=42)
    results_dict['label_pred'].append(train_and_eval_model(lr_pred, 'Logistic Regression', X_train, y_train_pred, X_test, y_test_pred, 'label_pred'))

    # 3. Random Forest
    rf_pred = RandomForestClassifier(n_estimators=100, max_depth=6, class_weight='balanced', random_state=42)
    results_dict['label_pred'].append(train_and_eval_model(rf_pred, 'Random Forest', X_train, y_train_pred, X_test, y_test_pred, 'label_pred'))

    # 4. Gradient Boosting
    gb_pred = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
    results_dict['label_pred'].append(train_and_eval_model(gb_pred, 'Gradient Boosting', X_train, y_train_pred, X_test, y_test_pred, 'label_pred'))

    # =========================================================================
    # LƯU MÔ HÌNH VÀ XUẤT CÁC BIỂU ĐỒ TRỰC QUAN HÓA
    # =========================================================================
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    plots_dir = os.path.join(cur_dir, "plots")
    export_visualization_plots(plots_dir, results_dict, rf_now, rf_pred, X_test, y_test_now, y_test_pred)

    # Lưu model cho Controller và REST API
    model_rf_path = os.path.join(cur_dir, "qos_model_rf.pkl")
    model_pred_path = os.path.join(cur_dir, "qos_model_pred_rf.pkl")
    joblib.dump(rf_now, model_rf_path)
    joblib.dump(rf_pred, model_pred_path)
    joblib.dump(rf_now, os.path.join(os.path.dirname(cur_dir), "qos_model.pkl"))

    # Lưu báo cáo JSON (bỏ các mảng numpy để serialize được)
    clean_results = []
    for target in ['label_now', 'label_pred']:
        for r in results_dict[target]:
            r_copy = {k: v for k, v in r.items() if k not in ['y_pred', 'y_prob']}
            clean_results.append(r_copy)

    report_path = os.path.join(cur_dir, "ml_evaluation_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)

    # IN BẢNG TỔNG HỢP HIỆU NĂNG
    print("\n" + "=" * 80)
    print("BẢNG TỔNG HỢP HIỆU NĂNG MÔ HÌNH HỌC MÁY (TẬP KIỂM THỬ ĐỘC LẬP)")
    print("=" * 80)
    print(f"{'Mô hình':<28} | {'Mục tiêu':<10} | {'Acc':<6} | {'Prec':<6} | {'Recall':<6} | {'F1':<6} | {'AUC':<6} | {'Trễ (ms)':<8}")
    print("-" * 88)
    for r in clean_results:
        print(f"{r['model_name']:<28} | {r['target']:<10} | {r['accuracy']*100:>5.1f}% | {r['precision']*100:>5.1f}% | {r['recall']*100:>5.1f}% | {r['f1_score']*100:>5.1f}% | {r['roc_auc']:>6.3f} | {r['inference_time_ms']:>6.3f}ms")
    print("=" * 80)
    print(f">>> Đã lưu mô hình tốt nhất vào: {model_rf_path}")
    print(f">>> Đã lưu báo cáo đánh giá vào: {report_path}")

if __name__ == '__main__':
    main()
