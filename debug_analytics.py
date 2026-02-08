import sys
import pandas as pd
from src.ingestor import YFinanceIngestor
from src.signals import AHR999Signal, DistanceFromPeakSignal
from src.analytics import AnalyticsEngine
from src.constants import DATE_FORMAT_DISPLAY

def main():
    print("=== DEBUG ANALYTICS ENGINE ===")
    
    # 1. Nhập Ticker
    ticker = input("Nhập Ticker (VD: BTC-USD, MSFT): ").strip().upper()
    if not ticker:
        ticker = "MSFT"
        print(f"Sử dụng mặc định: {ticker}")
        
    # 2. Chọn Strategy
    print("\nChọn Strategy:")
    print("1. DistanceFromPeakSignal (200 days)")
    print("2. DistanceFromPeakSignal (Custom)")
    print("3. AHR999Signal")
    
    choice = input("Nhập lựa chọn (1-3) [Mặc định 1]: ").strip()
    
    strategy = None
    if choice == "2":
        days = input("Nhập số ngày (window): ").strip()
        days = int(days) if days.isdigit() else 200
        strategy = DistanceFromPeakSignal(days)
    elif choice == "3":
        strategy = AHR999Signal()
    else:
        strategy = DistanceFromPeakSignal(200)
        
    print(f"\nĐang tải dữ liệu cho {ticker}...")
    ingestor = YFinanceIngestor(ticker)
    df = ingestor.get_data()
    
    if df.empty:
        print("Không tải được dữ liệu!")
        return
        
    print(f"Dữ liệu tải thành công: {len(df)} dòng. Từ {df.index.min().date()} đến {df.index.max().date()}")
    
    print(f"\nĐang tính toán tín hiệu {strategy.name}...")
    signal_series = strategy.calculate(df)
    
    # 3. Nhập Percentile để debug
    print("\nNhập Percentile để phân tích Drawdown (VD: 5, 10, 20)")
    p_input = input("Percentile [Mặc định 10]: ").strip()
    percentile = float(p_input) if p_input else 10.0
    
    print(f"\n=== KẾT QUẢ DEBUG: analyze_entry_points_drawdown (Percentile: {percentile}%) ===")
    
    events = AnalyticsEngine.analyze_entry_points_drawdown(df['Close'], signal_series, percentile)
    
    if not events:
        print("Không tìm thấy sự kiện nào!")
    else:
        # Chuyển thành DataFrame để in đẹp
        debug_df = pd.DataFrame(events)
        
        # Chọn các cột quan trọng để hiển thị
        cols_to_show = [
            'start_date_str', 
            'entry_price', 
            'min_price', 
            'min_date_str', 
            'max_dd_pct', 
            'days_to_bottom', 
            'recovery_date_str', 
            'days_to_recover', 
            'status'
        ]
        
        # Format lại số liệu cho dễ nhìn
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        
        # Làm đẹp output
        display_df = debug_df[cols_to_show].copy()
        display_df['max_dd_pct'] = display_df['max_dd_pct'].map(lambda x: f"{x:.2f}%")
        display_df['entry_price'] = display_df['entry_price'].map(lambda x: f"{x:,.2f}")
        display_df['min_price'] = display_df['min_price'].map(lambda x: f"{x:,.2f}")
        
        print(display_df.to_string(index=False))
        
        print(f"\nTổng số sự kiện tìm thấy: {len(events)}")

if __name__ == "__main__":
    main()
