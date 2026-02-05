import sys
from src.ingestor import YFinanceIngestor, CSVIngestor
from src.signals import AHR999Signal, DistanceFromPeakSignal
from src.analytics import AnalyticsEngine
from src.visualizer import UniversalVisualizer

def main():
    print("=== TRADING STATISTICS ENGINE ===")
    
    while True:
        # BƯỚC 1: NHẬP TICKER
        ticker_input = input("\nNhập mã Ticker (mặc định BTC-USD, 0 để thoát): ").strip().upper()
        if ticker_input == '0':
            print("Tạm biệt!")
            break
            
        ticker = ticker_input if ticker_input else "BTC-USD"
        
        try:
            ingestor = YFinanceIngestor(ticker)
            df = ingestor.get_data()
        except Exception as e:
            print(f"Lỗi tải dữ liệu: {e}")
            continue

        while True:
            print("\n" + "="*40)
            print(f"   MENU TÍN HIỆU ({ticker})")
            print("="*40)
            print("1. AHR999 (Chỉ số đáy)")
            print("2. Khoảng cách từ đỉnh (200 ngày)")
            print("3. Khoảng cách từ đỉnh (Tùy chỉnh)")
            print("8. Chọn lại Ticker")
            print("0. Thoát chương trình")
            
            choice = input("\nChọn chức năng: ")
            
            strategy = None
            if choice == '0': 
                print("Tạm biệt!")
                return
            elif choice == '8':
                break # Break inner loop to go back to ticker selection
            elif choice == '1':
                strategy = AHR999Signal()
            elif choice == '2':
                strategy = DistanceFromPeakSignal(window_days=200)
            elif choice == '3':
                try:
                    days = int(input("Nhập số ngày N: "))
                    strategy = DistanceFromPeakSignal(window_days=days)
                except ValueError:
                    print("Vui lòng nhập số hợp lệ.")
                    continue
            else:
                print("Lựa chọn không hợp lệ.")
                continue

            # BƯỚC 2: TÍNH TOÁN
            print(f"-> Đang tính toán tín hiệu: {strategy.name}...")
            signal_series = strategy.calculate(df)
            
            # Lấy thông tin bổ sung
            add_info = strategy.get_additional_info(df)
            
            # BƯỚC 3: THỐNG KÊ (Backtest Drawdown)
            print(f"-> Đang chạy backtest dữ liệu quá khứ...")
            stats_df = AnalyticsEngine.calculate_percentiles(signal_series, percentiles=[1, 5, 10, 20, 50])
            
            print(f"\nBẢNG THỐNG KÊ RỦI RO LỊCH SỬ ({strategy.name})")
            print("-" * 95)
            print(f"{'TOP TỆ NHẤT':<12} | {'NGƯỠNG':<15} | {'SỐ NGÀY':<15} | {'MAX DD LỊCH SỬ':<15} | {'GHI CHÚ'}")
            print("-" * 95)
            
            thresholds_to_plot = []
            stats_history = [] 
            
            for index, row in stats_df.iterrows():
                thresh = row['Threshold']
                thresholds_to_plot.append(thresh)
                
                dd_result = AnalyticsEngine.analyze_drawdown_after_threshold(
                    df['Close'], signal_series, thresh
                )
                
                stats_history.append({
                    'percentile': row['Percentile'],
                    'threshold': thresh,
                    'max_dd': dd_result['historical_max_drawdown']
                })
                
                # Format hiển thị
                if "Dist" in strategy.name:
                    # Với Distance strategy (số âm), hiển thị dạng % dương
                    display_thresh = f"{-thresh * 100:.2f}%"
                else:
                    display_thresh = f"{thresh:.4f}"
                
                days_info = f"{dd_result['days_in_zone']}/{dd_result['total_days']}"
                note = "Vùng đáy thế hệ" if row['Percentile'] <= 5 else "Vùng mua tốt"
                
                print(f"{row['Percentile']:>2}% {'(Hiếm)':<8} | {display_thresh:<15} | {days_info:<15} | {dd_result['formatted_drawdown']:<15} | {note}")

            # BƯỚC 4: HIỆN TRẠNG THỰC TẾ (FORMAT MỚI)
            print("-" * 95)
            current_status = AnalyticsEngine.get_detailed_current_status(
                df['Close'], signal_series, stats_history
            )
            
            print("\n--- HIỆN TRẠNG THỰC TẾ ---")
            print(f"1. Giá hiện tại: {current_status['current_price']:,.2f} USD")
            
            # Hiển thị giá trị Signal
            if "Dist" in strategy.name:
                 print(f"2. Giá trị {strategy.name} hiện tại: {-current_status['current_signal']*100:.2f}%")
            else:
                 print(f"2. Giá trị {strategy.name} hiện tại: {current_status['current_signal']:.4f}")
            
            rarity_note = f"(Nhóm {current_status['ref_percentile']}% tệ nhất)" if current_status['ref_percentile'] else "(An toàn)"
            print(f"3. Độ hiếm hiện tại: {current_status['rarity']:.2f}% {rarity_note}")
            
            next_idx = 4
            
            # THÔNG TIN BỔ SUNG (Tham chiếu)
            if add_info:
                print(f"{next_idx}. Ngày tham chiếu: {add_info['ref_date']}")
                next_idx += 1
                print(f"{next_idx}. Giá trị tham chiếu: {add_info['ref_value']}")
                next_idx += 1
                print(f"{next_idx}. Số phiên tính từ ngày tham chiếu: {add_info['days_since_ref']}")
                next_idx += 1
                print(f"{next_idx}. Số ngày hiệu lực còn lại: {add_info['days_remaining']}")
                next_idx += 1

            if current_status['entry_date']:
                date_str = current_status['entry_date'].strftime('%Y-%m-%d')
                print(f"{next_idx}. Giá bắt đầu lọt vùng {current_status['ref_percentile']}%: {current_status['entry_price']:,.2f} USD (Ngày: {date_str})")
                next_idx += 1
                
                # Max DD Lịch sử cũng cần format dương
                max_dd_display = -current_status['historical_max_dd_of_zone'] 
                
                dd_from_curr_display = ""
                if current_status.get('drawdown_from_current') is not None:
                    # Chuyển sang số dương để hiển thị % giảm
                    dd_pct = -current_status['drawdown_from_current'] * 100
                    dd_from_curr_display = f" | Cần giảm thêm {dd_pct:.2f}% từ giá hiện tại"

                print(f"{next_idx}. Target Drawdown tiềm năng: {current_status['target_price']:,.2f} USD (Mức giảm tệ nhất lịch sử {max_dd_display:.2f}%{dd_from_curr_display})")
            else:
                print(f"{next_idx}. Trạng thái: An toàn (Chưa lọt vùng rủi ro cao)")
                
            print("=" * 65)
            
            # BƯỚC 5: BIỂU ĐỒ (Đã bỏ qua theo yêu cầu)
            # Quay lại menu chọn signal
            input("\n[Enter] để quay lại menu...")

if __name__ == "__main__":
    main()