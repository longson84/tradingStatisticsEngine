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
    value="BTC-USD",
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

# 3. Save Options (Removed as per request)
# save_to_disk = st.sidebar.checkbox("Lưu báo cáo ra file (re/report)", value=True)

# --- Main Action ---
# Hàm wrapper để sử dụng st.cache_data
@st.cache_data(ttl=3600) # Cache trong RAM 1 giờ để thao tác nhanh trên Cloud
def load_data(ticker):
    ingestor = YFinanceIngestor(ticker)
    return ingestor.get_data()

if st.sidebar.button("🚀 Chạy Phân Tích", type="primary") or st.session_state.get('submitted'):
    st.session_state['submitted'] = True
    
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
        
        for i, ticker in enumerate(tickers):
            status_text.text(f"Đang xử lý {ticker} ({i+1}/{len(tickers)})...")
            
            try:
                # 1. Ingest Data (Đã có cache RAM)
                with st.spinner(f"[{ticker}] Đang tải dữ liệu..."):
                    df = load_data(ticker)
                
                # 2. Calculate Signal
                with st.spinner(f"[{ticker}] Đang tính toán tín hiệu..."):
                    signal_series = final_strategy.calculate(df)
                
                # 3. Generate Report
                report_gen = ReportGenerator(ticker, final_strategy, df, signal_series)
                report_gen.calculate()
                report_text = report_gen.generate_text_report()
                
                # 4. Visualization
                fig = ChartVisualizer.create_chart(ticker, df, signal_series, final_strategy)
                
                # 4.1 Distribution Chart
                current_signal_value = signal_series.iloc[-1]
                fig_dist = ChartVisualizer.create_distribution_chart(signal_series, current_signal_value, final_strategy.name)
                
                # --- Display Results (Vertical Layout) ---
                with results_container:
                    # Gói toàn bộ Ticker vào 1 Expander lớn
                    with st.expander(f"📊 Kết quả phân tích: {ticker}", expanded=True):
                        # Section 1: Báo cáo chi tiết (Render Markdown)
                        st.subheader("📝 Báo cáo phân tích")
                        st.markdown(report_text)
                        
                        st.divider()

                        # Section 2: Biểu đồ Phân phối (Mới)
                        with st.expander("📊 Xem Phân phối tín hiệu (Distribution)", expanded=True):
                            st.plotly_chart(fig_dist, use_container_width=True)

                        st.divider()
 
                        # Section 3: Biểu đồ Tín hiệu
                        with st.expander("📈 Xem Biểu đồ tín hiệu lịch sử", expanded=True):
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # st.divider()

                        # Section 3: Download Buttons
                        st.subheader("Tải về kết quả")
                        col1, col2 = st.columns(2)
                        
                        # Button 1: Download Report (.md)
                        timestamp = datetime.now().strftime("%y%m%d")
                        md_filename = f"{timestamp}_{ticker}_Report.md"
                        with col1:
                            st.download_button(
                                label="📥 Tải Báo Cáo (.md)",
                                data=report_text,
                                file_name=md_filename,
                                mime="text/markdown",
                                key=f"dl_md_{ticker}_{i}"
                            )
                        
                        # Button 2: Download Chart (.png or .html)
                        # Cố gắng convert sang PNG, nếu lỗi (do thiếu kaleido) thì fallback sang HTML
                        with col2:
                            try:
                                # Tăng scale để ảnh nét hơn
                                img_bytes = fig.to_image(format="png", width=1200, height=800, scale=2)
                                st.download_button(
                                    label="📥 Tải Biểu Đồ (.png)",
                                    data=img_bytes,
                                    file_name=f"{timestamp}_{ticker}_Chart.png",
                                    mime="image/png",
                                    key=f"dl_png_{ticker}_{i}"
                                )
                            except Exception as e:
                                # Fallback sang HTML nếu không tạo được PNG
                                html_bytes = fig.to_html()
                                st.download_button(
                                    label="📥 Tải Biểu Đồ (.html)",
                                    data=html_bytes,
                                    file_name=f"{timestamp}_{ticker}_Chart.html",
                                    mime="text/html",
                                    key=f"dl_html_{ticker}_{i}"
                                )
                                st.caption("⚠️ Không thể tạo ảnh PNG (có thể thiếu thư viện hỗ trợ), đã chuyển sang tải HTML.")
                    
            except Exception as e:
                st.error(f"❌ Lỗi khi xử lý {ticker}: {str(e)}")
            
            # Update progress
            progress_bar.progress((i + 1) / len(tickers))
            
        status_text.text("Hoàn tất!")
        ## st.balloons()
