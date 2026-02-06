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

                print(f"[{ticker}] Đang tính toán tín hiệu: {strategy.name}...")
                signal_series = strategy.calculate(df)
                
                print(f"[{ticker}] Đang chạy backtest và tổng hợp báo cáo...")
                report_gen = ReportGenerator(ticker, strategy, df, signal_series)
                report_gen.calculate()
                report_text = report_gen.generate_text_report()
                
                # Visualization
                print(f"[{ticker}] Đang tạo và hiển thị biểu đồ...")
                fig = ChartVisualizer.create_chart(ticker, df, signal_series, strategy)
                fig.show()
                
                # Save Chart (HTML + PNG)
                timestamp = datetime.now().strftime("%y%m%d%H%M%S")
                
                # Folder charts
                charts_dir = os.path.join(os.getcwd(), "re", "charts")
                os.makedirs(charts_dir, exist_ok=True)
                
                # 1. HTML
                chart_filename_html = f"{timestamp}_{ticker}_{strategy.report_name}_chart.html"
                chart_path_html = os.path.join(charts_dir, chart_filename_html)
                fig.write_html(chart_path_html)
                
                # 2. Static Image (PNG)
                chart_filename_png = f"{timestamp}_{ticker}_{strategy.report_name}_chart.png"
                chart_path_png = os.path.join(charts_dir, chart_filename_png)
                try:
                    # Yêu cầu cài đặt kaleido: pip install kaleido
                    # Không cần chỉ định engine="kaleido" nữa vì Plotly sẽ tự động nhận diện
                    fig.write_image(chart_path_png)
                    print(f"-> Đã lưu biểu đồ: {chart_filename_png} (PNG)")
                except Exception as e:
                    print(f"-> Không thể lưu ảnh tĩnh (cần cài kaleido): {e}")
                    chart_filename_png = None

                print(f"-> Đã lưu biểu đồ tương tác: {chart_filename_html}")
                
                # Store filenames in report object for linking
                report_gen.chart_filename = chart_filename_html
                report_gen.image_filename = chart_filename_png
                
                # Print report
                print("\n" + "=" * 65)
                print(f"KẾT QUẢ CHO: {ticker}")
                print("=" * 65)
                print(report_text)
                
                generated_reports.append(report_gen)

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
                    filename = report.save_to_file(chart_filename=c_name, image_filename=img_name)
                    print(f"-> Đã lưu: {filename}")
            
            input("\n[Enter] để quay lại menu...")

if __name__ == "__main__":
    main()
