import os
from datetime import datetime
import pandas as pd
import numpy as np
from src.analytics import (
    calculate_signal_percentiles,
    calculate_drawdown_statistics,
    get_detailed_current_status,
    get_consolidated_drawdown_analysis,
    calculate_drawdown_events
)
from src.constants import (
    CALCULATE_PERCENTILES,
    DRAWDOWN_PERCENTILES,
    TOP_N_DRAWDOWN,
    DATE_FORMAT_DISPLAY,
    MIN_RECOVERY_DAYS_THRESHOLD,
    DRAWDOWN_PERCENTILES_FOR_THRESHOLD
)

class ReportGenerator:
    def __init__(self, ticker, strategy, df, signal_series):
        self.ticker = ticker
        self.strategy = strategy
        self.df = df
        self.signal_series = signal_series
        self.stats_df = None
        self.stats_history = []
        self.current_status = None
        self.add_info = None

    def calculate(self):
        """Thực hiện toàn bộ các tính toán thống kê."""
        # 1. Calculate Percentiles
        self.stats_df = calculate_signal_percentiles(self.signal_series, percentiles=CALCULATE_PERCENTILES)
        
        # 2. Calculate History
        self.stats_history = []
        for _ , row in self.stats_df.iterrows():
            thresh = row['Threshold']
            dd_result = calculate_drawdown_statistics(
                self.df['Close'], self.signal_series, thresh
            )
            self.stats_history.append({
                'percentile': row['Percentile'],
                'threshold': thresh,
                'dd_result': dd_result  # Store full result for display
            })

        # 3. Calculate Current Status
        self.current_status = get_detailed_current_status(
            self.df['Close'], self.signal_series
        )
        
        # 3.1 Calculate Detailed Drawdown History
        # Sử dụng tất cả các mốc percentile quan trọng (CALCULATE_PERCENTILES) để đảm bảo không bỏ sót các sự kiện lớn
        # thay vì chỉ dùng DRAWDOWN_PERCENTILES (chỉ có 20, 15, 10...)
        self.detailed_drawdown_history = get_consolidated_drawdown_analysis(
            self.df['Close'],
            self.signal_series,
            percentiles=CALCULATE_PERCENTILES, 
            top_n=TOP_N_DRAWDOWN
        )

        # 4. Additional Info
        self.add_info = self.strategy.get_additional_info(self.df)

    def generate_text_report(self):
        """Tạo nội dung báo cáo dạng text (dùng cho print và save file)."""
        if self.current_status is None:
            self.calculate()
            
        lines = []
        # Header
        lines.append(f"## {self.ticker} — {self.strategy.name}")
        lines.append(f"Ngày thống kê: {datetime.now().strftime(DATE_FORMAT_DISPLAY)}  ")

        # Lấy ngày bắt đầu dữ liệu
        start_date_str = self.df.index.min().strftime(DATE_FORMAT_DISPLAY)
        lines.append(f"Ngày dữ liệu đầu tiên: {start_date_str}  ")
        lines.append(f"Ngày dữ liệu cuối cùng: {self.df.index[-1].strftime(DATE_FORMAT_DISPLAY)}  ")
        lines.append(f"Tổng số phiên: {len(self.df):,}  ")
        
        lines.append("")

        # Risk History Table
        lines.append(f"## Thống kê lịch sử")
        # Markdown Table Header
        header_cols = ["PCT", "TÍN HIỆU", "LẦN", "QR", "QR (%)", "5 NĂM", "10 NĂM", "SỐ NGÀY"] + ["MDD"] +  [f"MDD {p}%" for p in DRAWDOWN_PERCENTILES_FOR_THRESHOLD] 
        lines.append("| " + " | ".join(header_cols) + " |")
        lines.append("| " + " | ".join([":---"] * len(header_cols)) + " |")


        for item in self.stats_history:
            row = item
            dd_result = item['dd_result']
            thresh = row['threshold']
            
            # Use strategy's format_value method
            display_thresh = self.strategy.format_value(thresh)
            
            days_info = f"{dd_result['days_in_zone']}"
            
            total_events = dd_result.get('total_events', 0)
            quick_events = dd_result.get('quick_recoveries', 0)
            events_5y = dd_result.get('events_5y', "NA")
            events_10y = dd_result.get('events_10y', "NA")
            quick_rate = f"{(quick_events/total_events*100):.0f}%" if total_events > 0 else "0%"
            
            # Format top drawdowns
            top_cols = []
            top_dd_map = dd_result.get('top_drawdown_percentiles', {})
            for p in DRAWDOWN_PERCENTILES_FOR_THRESHOLD:
                val = top_dd_map.get(p)
                if val is not None:
                     # val is float (e.g., -0.25), convert to %
                     top_cols.append(f"{abs(val)*100:.2f}%")
                else:
                     top_cols.append("NA")

            # Format max drawdown
            formatted_max_dd = f"{-dd_result['historical_max_drawdown']*100:.2f}%"

            row_vals = [f"{row['percentile']:.0f}%", display_thresh, str(total_events), str(quick_events), quick_rate, str(events_5y), str(events_10y), days_info] + [formatted_max_dd] + top_cols 
            lines.append("| " + " | ".join(row_vals) + " |")
        
        lines.append("")

        # Current Status
        lines.append("## Trạng thái hiện tại")
        lines.append(f"1. Giá hiện tại: {self.current_status['current_price']:,.2f} USD")
        
        display_current_signal = self.strategy.format_value(self.current_status['current_signal'])
        lines.append(f"2. {self.strategy.name} hiện tại: {display_current_signal}")
        
        lines.append(f"3. Độ hiếm hiện tại: {self.current_status['rarity']:.0f}%")
        
        next_idx = 4
        if self.add_info:
            lines.append(f"{next_idx}. Ngày tham chiếu: {self.add_info['ref_date']}")
            next_idx += 1
            lines.append(f"{next_idx}. Giá trị tham chiếu: {self.add_info['ref_value']}")
            next_idx += 1
            lines.append(f"{next_idx}. Số phiên tính từ ngày tham chiếu: {self.add_info['days_since_ref']}")
            # Kiểm tra nếu có key 'days_remaining' (cho strategy 2)
            if 'days_remaining' in self.add_info:
                next_idx += 1
                lines.append(f"{next_idx}. Số ngày hiệu lực còn lại: {self.add_info['days_remaining']}")

        if self.current_status.get('entry_date'):
            date_str = self.current_status['entry_date'].strftime(DATE_FORMAT_DISPLAY)
            lines.append(f"{next_idx}. Giá bắt đầu vào vùng {self.current_status['ref_percentile']:,.0f}% từ ngày: {date_str} ở mức {self.current_status['entry_price']:,.2f} USD")
            next_idx += 1
            if self.current_status.get('days_in_current_zone') is not None:
                lines.append(f"{next_idx}. Giá đã ở vùng hiện tại: {self.current_status['days_in_current_zone']} phiên")
                next_idx += 1
            
            max_dd_display = -self.current_status['historical_max_dd_of_zone'] * 100
            dd_from_curr_display = ""
            if self.current_status.get('drawdown_from_current') is not None:
                dd_pct = -self.current_status['drawdown_from_current'] * 100
                dd_from_curr_display = f"~ giảm {dd_pct:.2f}% từ hiện tại"
            
            lines.append(f"{next_idx}. Giá có thể giảm đến {self.current_status['target_price']:,.2f} USD, {dd_from_curr_display}, Max DD: {max_dd_display:.2f}%")
        else:
            lines.append(f"{next_idx}. Trạng thái: An toàn (Chưa vào vùng rủi ro cao)")

        lines.append("")
        
        # Detailed Drawdown History Table (Section 2)
        lines.append(f"## TOP Drawdown Period & Chưa phục hồi ({len(self.detailed_drawdown_history)} sự kiện)")
        lines.append("<details>")
        lines.append("<summary>Bấm để xem chi tiết</summary>")
        lines.append("")
        lines.append(f"| Ngày bắt đầu | Giá | Percentile | Giá đáy | Ngày đáy | MDD (%) | Số ngày đến đáy | Ngày phục hồi | Số ngày phục hồi | Trạng thái |")
        lines.append(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        
        for event in self.detailed_drawdown_history:
             price_str = f"{event['entry_price']:,.2f}"
             min_price_str = f"{event['min_price']:,.2f}"
             dd_str = f"{event['max_dd_pct']:.2f}%"
             status_str = event['status']
             
             # Format Dates
             start_date_str = event['start_date'].strftime(DATE_FORMAT_DISPLAY)
             min_date_str = event['min_date'].strftime(DATE_FORMAT_DISPLAY)
             if event['recovery_date']:
                 recovery_date_str = event['recovery_date'].strftime(DATE_FORMAT_DISPLAY)
             else:
                 recovery_date_str = "Chưa phục hồi"
            
             days_to_recover = event['days_to_recover'] if event['days_to_recover'] is not None else "-"

             # Tô đỏ dòng chưa phục hồi
             if event['status'] == "Chưa phục hồi":
                 status_str = f"<span style='color:red'>**{status_str} ({event['total_days']} phiên)**</span>"
                 dd_str = f"<span style='color:red'>**{dd_str}**</span>"
             
             row = f"| {start_date_str} | {price_str} | {event['percentile']}% | {min_price_str} | {min_date_str} | {dd_str} | {event['days_to_bottom']} | {recovery_date_str} | {days_to_recover} | {status_str} |"
             lines.append(row)
        
        lines.append("")
        lines.append("</details>")
        lines.append("")

        # Section 3: Full History per Percentile (New)
        lines.append(f"## Lịch sử Drawdown theo từng Percentile")
        
        for p in DRAWDOWN_PERCENTILES:
            # Calculate threshold directly
            threshold = np.percentile(self.signal_series.dropna(), p)
            events = calculate_drawdown_events(self.df['Close'], self.signal_series, threshold)
            
            # Filter noise (<= MIN_RECOVERY_DAYS_THRESHOLD)
            filtered_events = []
            quick_count = 0
            last_date = self.df.index[-1]
            for e in events:
                should_keep = False
                if e['status'] == "Chưa phục hồi":
                    age_days = (last_date - e['start_date']).days
                    if age_days > MIN_RECOVERY_DAYS_THRESHOLD:
                        should_keep = True
                else:
                    days_recover = e.get('days_to_recover')
                    # Check if numeric and > threshold
                    if isinstance(days_recover, (int, float)) and days_recover > MIN_RECOVERY_DAYS_THRESHOLD:
                         should_keep = True
                    else:
                         if isinstance(days_recover, (int, float)):
                             quick_count += 1
                
                if should_keep:
                    filtered_events.append(e)
            
            lines.append(f"### Percentile {p}% (Ngưỡng: {self.strategy.format_value(threshold)}, {len(filtered_events)} sự kiện, {quick_count} phục hồi nhanh)")
            lines.append("<details>")
            lines.append(f"<summary>Xem danh sách ({len(filtered_events)} sự kiện, {quick_count} phục hồi nhanh)</summary>")
            lines.append("")
            
            if not filtered_events:
                lines.append("Không có dữ liệu phù hợp (đã lọc nhiễu < 5 ngày).")
            else:
                lines.append(f"| Ngày bắt đầu | Giá | Percentile | Giá đáy | Ngày đáy | Max DD (%) | Số ngày đến đáy | Ngày phục hồi | Số ngày phục hồi | Trạng thái |")
                lines.append(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
                
                for event in filtered_events:
                     price_str = f"{event['entry_price']:,.2f}"
                     min_price_str = f"{event['min_price']:,.2f}"
                     dd_str = f"{event['max_dd_pct']:.2f}%"
                     status_str = event['status']

                     # Format Dates
                     start_date_str = event['start_date'].strftime(DATE_FORMAT_DISPLAY)
                     min_date_str = event['min_date'].strftime(DATE_FORMAT_DISPLAY)
                     if event['recovery_date']:
                         recovery_date_str = event['recovery_date'].strftime(DATE_FORMAT_DISPLAY)
                     else:
                         recovery_date_str = "Chưa phục hồi"

                     days_to_recover = event['days_to_recover'] if event['days_to_recover'] is not None else "-"
                     
                     if event['status'] == "Chưa phục hồi":
                         status_str = f"<span style='color:red'>**{status_str} ({event['total_days']} phiên)**</span>"
                         dd_str = f"<span style='color:red'>**{dd_str}**</span>"
                     
                     row = f"| {start_date_str} | {price_str} | {event['percentile']}% | {min_price_str} | {min_date_str} | {dd_str} | {event['days_to_bottom']} | {recovery_date_str} | {days_to_recover} | {status_str} |"
                     lines.append(row)

            lines.append("")
            lines.append("</details>")
            lines.append("")

        return "\n".join(lines)
    
    def save_to_file(self, chart_filename: str = None, image_filename: str = None, dist_chart_filename: str = None, dist_image_filename: str = None):
        """Lưu báo cáo ra file .md trong folder re/report"""
        report_text = self.generate_text_report()
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        
        # Tạo folder re/report nếu chưa tồn tại
        report_dir = os.path.join(os.getcwd(), "re", "report")
        os.makedirs(report_dir, exist_ok=True)
        
        filename = f"{timestamp}_{self.ticker}_{self.strategy.report_name}.md"
        file_path = os.path.join(report_dir, filename)
        
        # Thêm biểu đồ phân phối vào báo cáo (Section mới)
        report_text += f"\n\n## BIỂU ĐỒ PHÂN PHỐI\n"
        if dist_image_filename:
             relative_dist_image_path = f"../charts/{dist_image_filename}"
             report_text += f"![Biểu đồ phân phối]({relative_dist_image_path})\n\n"
        
        if dist_chart_filename:
            relative_dist_html_path = f"../charts/{dist_chart_filename}"
            report_text += f"Xem biểu đồ phân phối tương tác: [{dist_chart_filename}]({relative_dist_html_path})\n"

        # Thêm biểu đồ tín hiệu vào cuối file report
        report_text += f"\n\n## BIỂU ĐỒ TÍN HIỆU\n"
        
        # 1. Nhúng ảnh tĩnh trực tiếp (hiển thị luôn trong Markdown)
        if image_filename:
            # Đường dẫn tương đối từ re/report sang re/charts
            # image_filename dự kiến nằm trong re/charts
            relative_image_path = f"../charts/{image_filename}"
            report_text += f"![Biểu đồ phân tích]({relative_image_path})\n\n"
            
        # 2. Link đến biểu đồ tương tác HTML
        if chart_filename:
            # Đường dẫn tương đối từ re/report sang re/charts
            relative_html_path = f"../charts/{chart_filename}"
            report_text += f"Xem biểu đồ tương tác (Zoom/Pan): [{chart_filename}]({relative_html_path})\n"
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_text)
            return file_path
        except Exception as e:
            print(f"Lỗi khi lưu file: {e}")
            return None
