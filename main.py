import sys
import os
from datetime import datetime
from src.ingestor import YFinanceIngestor
from src.signals import AHR999Signal, DistanceFromPeakSignal
from src.report import ReportGenerator
from src.visualizer import ChartVisualizer

def get_ticker_input():
    print("\n" + "="*40)
    print("   NHẬP TICKER (Phân cách bằng dấu cách)")
    print("   Ví dụ: MSFT GOOGL AAPL")
    print("="*40)
    ticker_input = input("\nNhập mã Ticker (0 để thoát): ").strip().upper()
    if ticker_input == '0':
        return None
    if not ticker_input:
        return ["BTC-USD"]
    # Tách chuỗi thành list các ticker
    return [t for t in ticker_input.split() if t]

def get_strategy_input(tickers):
    # Danh sách tất cả các strategy có thể có
    all_strategies = [
        AHR999Signal(),
        DistanceFromPeakSignal(window_days=200),
        DistanceFromPeakSignal(window_days=150),
        DistanceFromPeakSignal(window_days=100),
        DistanceFromPeakSignal(window_days=50),
        DistanceFromPeakSignal(window_days=None) # Custom option
    ]
    
    # Lọc ra các strategy phù hợp với TẤT CẢ ticker hiện tại
    available_strategies = []
    for s in all_strategies:
        if all(s.is_applicable(t) for t in tickers):
            available_strategies.append(s)
    
    tickers_str = ", ".join(tickers)
    print("\n" + "="*40)
    print(f"   MENU TÍN HIỆU ({tickers_str})")
    print("="*40)
    
    for i, strategy in enumerate(available_strategies, 1):
        print(f"{i}. {strategy.name}")
        
    print("8. Chọn lại Ticker")
    print("0. Thoát chương trình")
    
    choice = input("\nChọn chức năng: ")
    
    if choice == '0': return 'exit'
    if choice == '8': return 'back'
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(available_strategies):
            selected_strategy = available_strategies[idx]
            
            # Nếu là DistanceFromPeakSignal và chưa có window_days (Custom option)
            if isinstance(selected_strategy, DistanceFromPeakSignal) and selected_strategy.window is None:
                while True:
                    try:
                        days = int(input("Nhập số ngày N (ví dụ: 200): "))
                        if days > 0:
                            # Tạo instance mới với số ngày đã nhập
                            return DistanceFromPeakSignal(window_days=days)
                        print("Số ngày phải > 0.")
                    except ValueError:
                        print("Vui lòng nhập số nguyên.")
            
            return selected_strategy
        else:
            print("Lựa chọn không hợp lệ.")
            return None
    except ValueError:
        print("Vui lòng nhập số.")
        return None

def main():
    print("=== TRADING STATISTICS ENGINE ===")
    
    while True:
        tickers = get_ticker_input()
        if not tickers:
            print("Tạm biệt!")
            break
            
        while True:
            strategy = get_strategy_input(tickers)
            if strategy == 'exit':
                print("Tạm biệt!")
                return
            if strategy == 'back':
                break
            if strategy is None:
                continue

            generated_reports = []
            
            # Xử lý từng ticker
            for ticker in tickers:
                print(f"\n[{ticker}] Đang tải dữ liệu...")
                try:
                    ingestor = YFinanceIngestor(ticker)
                    df = ingestor.get_data()
                except Exception as e:
                    print(f"[{ticker}] Lỗi tải dữ liệu: {e}")
                    continue

                try:
                    print(f"[{ticker}] Đang tính toán tín hiệu: {strategy.name}...")
                    signal_series = strategy.calculate(df)
                    
                    print(f"[{ticker}] Đang chạy backtest và tổng hợp báo cáo...")
                    report_gen = ReportGenerator(ticker, strategy, df, signal_series)
                    report_gen.calculate()
                    report_text = report_gen.generate_text_report()
                    
                    # Visualization
                    print(f"[{ticker}] Đang tạo và hiển thị biểu đồ...")
                    
                    # 1. Main Chart
                    fig = ChartVisualizer.create_chart(ticker, df, signal_series, strategy)
                    
                    # 2. Distribution Chart
                    current_signal_value = signal_series.iloc[-1]
                    fig_dist = ChartVisualizer.create_distribution_chart(signal_series, current_signal_value, strategy.name)
                    
                    # Show charts (optional in script mode, maybe too much popups)
                    # fig.show() 
                    
                    # Save Charts (HTML + PNG)
                    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
                    
                    # Folder charts
                    charts_dir = os.path.join(os.getcwd(), "re", "charts")
                    os.makedirs(charts_dir, exist_ok=True)
                    
                    # --- Save Main Chart ---
                    # HTML
                    chart_filename_html = f"{timestamp}_{ticker}_{strategy.report_name}_chart.html"
                    chart_path_html = os.path.join(charts_dir, chart_filename_html)
                    fig.write_html(chart_path_html)
                    
                    # PNG
                    chart_filename_png = f"{timestamp}_{ticker}_{strategy.report_name}_chart.png"
                    chart_path_png = os.path.join(charts_dir, chart_filename_png)
                    try:
                        fig.write_image(chart_path_png)
                        print(f"-> Đã lưu biểu đồ tín hiệu: {chart_filename_png} (PNG)")
                    except Exception as e:
                        print(f"-> Không thể lưu ảnh tĩnh (cần cài kaleido): {e}")
                        chart_filename_png = None

                    # --- Save Distribution Chart ---
                    # HTML
                    dist_chart_filename_html = f"{timestamp}_{ticker}_{strategy.report_name}_dist.html"
                    dist_path_html = os.path.join(charts_dir, dist_chart_filename_html)
                    fig_dist.write_html(dist_path_html)
                    
                    # PNG
                    dist_chart_filename_png = f"{timestamp}_{ticker}_{strategy.report_name}_dist.png"
                    dist_path_png = os.path.join(charts_dir, dist_chart_filename_png)
                    try:
                        fig_dist.write_image(dist_path_png)
                        print(f"-> Đã lưu biểu đồ phân phối: {dist_chart_filename_png} (PNG)")
                    except Exception as e:
                        print(f"-> Không thể lưu ảnh tĩnh phân phối: {e}")
                        dist_chart_filename_png = None

                    print(f"-> Đã lưu các biểu đồ tương tác HTML.")
                    
                    # Store filenames in report object for linking
                    report_gen.chart_filename = chart_filename_html
                    report_gen.image_filename = chart_filename_png
                    report_gen.dist_chart_filename = dist_chart_filename_html
                    report_gen.dist_image_filename = dist_chart_filename_png
                    
                    # Print report
                    print("\n" + "=" * 65)
                    print(f"KẾT QUẢ CHO: {ticker}")
                    print("=" * 65)
                    print(report_text)
                    
                    generated_reports.append(report_gen)
                
                except Exception as e:
                    print(f"\n[LỖI] Xảy ra lỗi khi xử lý ticker {ticker}: {e}")
                    print("-> Đang bỏ qua và chuyển sang ticker tiếp theo...")
                    continue

            if not generated_reports:
                input("\nKhông có báo cáo nào được tạo. [Enter] để quay lại...")
                continue

            # Post-analysis options (Bulk action)
            print("\n" + "=" * 65)
            print("TÙY CHỌN CHUNG:")
            print("1. Lưu TẤT CẢ kết quả ra file")
            print("2. Quay lại menu")
            
            post_choice = input("Chọn (Mặc định quay lại): ")
            if post_choice == '1':
                for report in generated_reports:
                    c_name = getattr(report, 'chart_filename', None)
                    img_name = getattr(report, 'image_filename', None)
                    dist_c_name = getattr(report, 'dist_chart_filename', None)
                    dist_img_name = getattr(report, 'dist_image_filename', None)
                    
                    filename = report.save_to_file(
                        chart_filename=c_name, 
                        image_filename=img_name,
                        dist_chart_filename=dist_c_name,
                        dist_image_filename=dist_img_name
                    )
                    print(f"-> Đã lưu: {filename}")
            
            input("\n[Enter] để quay lại menu...")

if __name__ == "__main__":
    main()
