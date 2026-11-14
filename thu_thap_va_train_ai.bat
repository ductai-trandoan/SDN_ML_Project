@echo off
title SDN AI - Thu thap so lieu tu Mininet va Train Model
color 0B

echo =======================================================================
echo     QUY TRINH TU DONG: THU THAP DATA MININET THAT - TRAIN AI - XUAT BIEU DO
echo =======================================================================
echo.
echo LUU Y: Ban can chac chan file 'start.bat' dang chay o mot cua so khac!
echo.
echo Quy trinh se tu dong thuc hien cac buoc:
echo   1. Kiem tra ket noi voi cac switch va host trong Mininet
echo   2. Bom luong luu luong thuc te (K1 - K5) qua 2 chu ky (khoang 4-5 phut)
echo   3. Controller ghi so lieu OpenFlow vao SQLite
echo   4. Trich xuat dac trung chuoi thoi gian (Rolling Window W=5s, H=5s)
echo   5. Train 4 mo hinh: Random Forest, Logistic Reg, Decision Tree, Gradient Boosting
echo   6. Xuat 4 bieu do khoa hoc vao thu muc 'ml_engine/plots/'
echo   7. Cap nhat model moi nhat cho Controller
echo.
echo Bam phim bat ky de bat dau qua trinh thu thap va huan luyen...
pause > nul

wsl -d Ubuntu-22.04 -u root bash -c "cd /mnt/d/Project/SDN_ML_Project && python3 ml_engine/run_full_pipeline.py --cycles 2"

echo.
echo =======================================================================
echo [OK] HOAN TAT! Ban co the xem cac bieu do moi trong thu muc: ml_engine/plots/
echo =======================================================================
echo.
pause

