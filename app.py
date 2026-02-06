import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from src.ingestor import YFinanceIngestor
from src.signals import AHR999Signal, DistanceFromPeakSignal
from src.report import ReportGenerator
from src.visualizer import ChartVisualizer

# Page configuration
st.set_page_config(
    page_title="Trading Statistics Engine",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and Description
st.title("📈 Trading Statistics Engine")
st.markdown("Công cụ phân tích thống kê và tín hiệu giao dịch.")

# --- Sidebar: Configuration ---
st.sidebar.header("Cấu hình")

# 1. Ticker Input
ticker_input_str = st.sidebar.text_input(
    "Nhập danh sách Ticker (cách nhau bởi dấu cách):",
    value="BTC-USD ETH-USD",
    help="Ví dụ: BTC-USD ETH-USD MSFT AAPL"
)

tickers = [t.strip().upper() for t in ticker_input_str.split() if t.strip()]

# 2. Strategy Selection Logic
# Define base strategies
all_strategies_objs = [
    DistanceFromPeakSignal(200),
    DistanceFromPeakSignal(150),
    DistanceFromPeakSignal(100),
    DistanceFromPeakSignal(50),
    # DistanceFromPeakSignal(None) will be handled via Custom option
    AHR999Signal()
]

# Create a mapping for display
strategy_map = {s.name: s for s in all_strategies_objs}
strategy_map["Khoảng cách từ đỉnh (Tùy chỉnh)"] = "CUSTOM_DIST"

# Filter applicable strategies based on ALL input tickers
available_strategy_names = []
if tickers:
    for name, s_obj in strategy_map.items():
        if s_obj == "CUSTOM_DIST":
            # Always available as a generic strategy (applicability checked later or assumed universal for price data)
            available_strategy_names.append(name)
            continue
            
        # Check applicability for all tickers
        is_ok = True
        for t in tickers:
            if not s_obj.is_applicable(t):
                is_ok = False
                break
        if is_ok:
            available_strategy_names.append(name)
else:
    st.sidebar.warning("Vui lòng nhập ít nhất một Ticker.")

# Strategy Dropdown
selected_strategy_name = st.sidebar.selectbox(
    "Chọn chiến lược:",
    options=available_strategy_names,
    index=0 if available_strategy_names else None
)

# Handle Custom Strategy Input
final_strategy = None
if selected_strategy_name and strategy_map[selected_strategy_name] == "CUSTOM_DIST":
    custom_days = st.sidebar.number_input("Nhập số ngày (Window):", min_value=10, value=200, step=10)
    final_strategy = DistanceFromPeakSignal(custom_days)
elif selected_strategy_name:
    final_strategy = strategy_map[selected_strategy_name]

# 3. Save Options
save_to_disk = st.sidebar.checkbox("Lưu báo cáo ra file (re/report)", value=True, help="Nếu chọn, báo cáo và biểu đồ sẽ được lưu vào thư mục 're' của dự án.")

# --- Main Action ---
if st.sidebar.button("🚀 Chạy Phân Tích", type="primary"):
    if not tickers:
        st.error("Vui lòng nhập Ticker để bắt đầu.")
    elif not final_strategy:
        st.error("Vui lòng chọn một chiến lược hợp lệ.")
    else:
        # Progress container
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Container for results
        results_container = st.container()
        
        generated_reports = []
        
        for i, ticker in enumerate(tickers):
            status_text.text(f"Đang xử lý {ticker} ({i+1}/{len(tickers)})...")
            
            try:
                # 1. Ingest Data
                with st.spinner(f"[{ticker}] Đang tải dữ liệu..."):
                    ingestor = YFinanceIngestor(ticker)
                    df = ingestor.get_data()
                
                # 2. Calculate Signal
                with st.spinner(f"[{ticker}] Đang tính toán tín hiệu..."):
                    signal_series = final_strategy.calculate(df)
                
                # 3. Generate Report
                report_gen = ReportGenerator(ticker, final_strategy, df, signal_series)
                report_gen.calculate()
                report_text = report_gen.generate_text_report()
                
                # 4. Visualization
                fig = ChartVisualizer.create_chart(ticker, df, signal_series, final_strategy)
                
                # 5. Save to Disk (Optional)
                saved_files_info = []
                if save_to_disk:
                    with st.spinner(f"[{ticker}] Đang lưu file..."):
                        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
                        
                        # Folders
                        charts_dir = os.path.join(os.getcwd(), "re", "charts")
                        os.makedirs(charts_dir, exist_ok=True)
                        
                        # Save HTML Chart
                        chart_filename_html = f"{timestamp}_{ticker}_{final_strategy.report_name}_chart.html"
                        chart_path_html = os.path.join(charts_dir, chart_filename_html)
                        fig.write_html(chart_path_html)
                        
                        # Save PNG Chart
                        chart_filename_png = f"{timestamp}_{ticker}_{final_strategy.report_name}_chart.png"
                        chart_path_png = os.path.join(charts_dir, chart_filename_png)
                        try:
                            fig.write_image(chart_path_png)
                        except Exception as e:
                            st.warning(f"Không thể lưu ảnh PNG cho {ticker}: {e}")
                            chart_filename_png = None
                            
                        # Store filenames in report object
                        report_gen.chart_filename = chart_filename_html
                        report_gen.image_filename = chart_filename_png
                        
                        # Save Markdown Report
                        md_path = report_gen.save_to_file(chart_filename=chart_filename_html, image_filename=chart_filename_png)
                        
                        if md_path:
                            saved_files_info.append(f"Report: `{os.path.basename(md_path)}`")
                        saved_files_info.append(f"Chart: `{chart_filename_html}`")

                # --- Display Results ---
                with results_container:
                    st.divider()
                    st.subheader(f"📊 Kết quả cho: {ticker}")
                    
                    # Tabs for View
                    tab1, tab2 = st.tabs(["Biểu đồ", "Báo cáo chi tiết"])
                    
                    with tab1:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with tab2:
                        st.text_area(f"Báo cáo text - {ticker}", value=report_text, height=400)
                        # Render markdown preview (optional, but text area keeps formatting better for copy-paste)
                        # st.markdown(report_text)
                    
                    if saved_files_info:
                        st.success(f"✅ Đã lưu file: {', '.join(saved_files_info)}")
                    
            except Exception as e:
                st.error(f"❌ Lỗi khi xử lý {ticker}: {str(e)}")
            
            # Update progress
            progress_bar.progress((i + 1) / len(tickers))
            
        status_text.text("Hoàn tất!")
        ## st.balloons()
