import pandas as pd
from src.ingestor import YFinanceIngestor
from src.signals import DistanceFromPeakSignal
from src.analytics import AnalyticsEngine
from src.constants import DRAWDOWN_PERCENTILES, TOP_N_DRAWDOWN

def main():
    print("=== CONSOLIDATED DRAWDOWN TABLE VIEWER ===")
    
    ticker = "MSFT" 
    print(f"Ticker: {ticker}")
        
    strategy = DistanceFromPeakSignal(200)
    print(f"Strategy: {strategy.name}")
        
    print(f"Loading data...")
    ingestor = YFinanceIngestor(ticker)
    df = ingestor.get_data()
    
    if df.empty:
        print("No data found!")
        return
        
    print(f"Calculating signals...")
    signal_series = strategy.calculate(df)
    
    print(f"\nGenerating Consolidated Drawdown Analysis...")
    print(f"Percentiles: {DRAWDOWN_PERCENTILES}")
    print(f"Top N: {TOP_N_DRAWDOWN}")
    
    events = AnalyticsEngine.get_consolidated_drawdown_analysis(
        df['Close'], 
        signal_series, 
        percentiles=DRAWDOWN_PERCENTILES,
        top_n=TOP_N_DRAWDOWN
    )
    
    if not events:
        print("No events found.")
        return

    # Create DataFrame for display
    display_df = pd.DataFrame(events)
    
    # Select and rename columns for better readability
    columns_map = {
        'start_date_str': 'Start Date',
        'entry_price': 'Entry Price',
        'percentile': 'Percentile',
        'min_price': 'Bottom Price',
        'min_date_str': 'Bottom Date',
        'max_dd_pct': 'Max DD (%)',
        'days_to_bottom': 'Days to Bot',
        'recovery_date_str': 'Recovery Date',
        'days_to_recover': 'Days to Rec',
        'status': 'Status'
    }
    
    # Ensure all columns exist
    cols_to_use = [c for c in columns_map.keys() if c in display_df.columns]
    display_df = display_df[cols_to_use].rename(columns=columns_map)
    
    # Format numeric columns
    if 'Entry Price' in display_df.columns:
        display_df['Entry Price'] = display_df['Entry Price'].apply(lambda x: f"{x:,.2f}")
    if 'Bottom Price' in display_df.columns:
        display_df['Bottom Price'] = display_df['Bottom Price'].apply(lambda x: f"{x:,.2f}")
    if 'Max DD (%)' in display_df.columns:
        display_df['Max DD (%)'] = display_df['Max DD (%)'].apply(lambda x: f"{x:.2f}%")
        
    print("\n=== CONSOLIDATED DRAWDOWN EVENTS ===")
    # Adjust display options to ensure all columns are shown
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(display_df.to_string(index=False))

if __name__ == "__main__":
    main()
