import os
from datetime import datetime
import pandas as pd
from src.analytics import AnalyticsEngine

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
        self.stats_df = AnalyticsEngine.calculate_percentiles(self.signal_series, percentiles=[1, 5, 10, 15, 20, 25, 30, 40, 50])
        
        # 2. Calculate History
        self.stats_history = []
        for index, row in self.stats_df.iterrows():
            thresh = row['Threshold']
            dd_result = AnalyticsEngine.analyze_drawdown_after_threshold(
                self.df['Close'], self.signal_series, thresh
            )
            self.stats_history.append({
                'percentile': row['Percentile'],
                'threshold': thresh,
                'max_dd': dd_result['historical_max_drawdown'],
                'dd_result': dd_result  # Store full result for display
            })

        # 3. Calculate Current Status
        # AnalyticsEngine.get_detailed_current_status expects stats_history with keys 'percentile', 'threshold', 'max_dd'
        self.current_status = AnalyticsEngine.get_detailed_current_status(
            self.df['Close'], self.signal_series, self.stats_history
        )

        # 4. Additional Info
        self.add_info = self.strategy.get_additional_info(self.df)

    def generate_text_report(self):
        """Tạo nội dung báo cáo dạng text (dùng cho print và save file)."""
        if self.current_status is None:
            self.calculate()
            
        lines = []
        # Header
        lines.append(f"# TRADING STATISTICS REPORT")
        lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Ticker: {self.ticker}")
        lines.append(f"Strategy: {self.strategy.name}")
        lines.append("")

        # Risk History Table
        lines.append(f"## BẢNG THỐNG KÊ RỦI RO LỊCH SỬ")
        # Markdown Table Header
        lines.append(f"| PERCENTILE | TÍN HIỆU | SỐ NGÀY | MAX DD TỪ PERCENTILE | TIME SPENT (%) |")
        lines.append(f"| :--- | :--- | :--- | :--- | :--- |")

        for item in self.stats_history:
            row = item
            dd_result = item['dd_result']
            thresh = row['threshold']
            
            # Use strategy's format_value method
            display_thresh = self.strategy.format_value(thresh)
            
            days_info = f"{dd_result['days_in_zone']}/{dd_result['total_days']}"
            # note = "Vùng đáy thế hệ" if row['percentile'] <= 5 else "Vùng mua tốt"
            time_spent = dd_result['days_in_zone']/dd_result['total_days']*100
            
            # Markdown Table Row
            lines.append(f"| {row['percentile']:.0f}% (Hiếm) | {display_thresh} | {days_info} | {dd_result['formatted_drawdown']} | {time_spent:.2f}% |")
        
        lines.append("")

        # Current Status
        lines.append("## HIỆN TRẠNG THỰC TẾ")
        lines.append(f"1. Giá hiện tại: {self.current_status['current_price']:,.2f} USD")
        
        display_current_signal = self.strategy.format_value(self.current_status['current_signal'])
        lines.append(f"2. Giá trị {self.strategy.name} hiện tại: {display_current_signal}")
        
        rarity_note = f"(Nhóm {self.current_status['ref_percentile']:.0f}% tệ nhất)" if self.current_status['ref_percentile'] else "(An toàn)"
        lines.append(f"3. Độ hiếm hiện tại: {self.current_status['rarity']:.0f}% {rarity_note}")
        
        next_idx = 4
        if self.add_info:
            lines.append(f"{next_idx}. Ngày tham chiếu: {self.add_info['ref_date']}")
            next_idx += 1
            lines.append(f"{next_idx}. Giá trị tham chiếu: {self.add_info['ref_value']}")
            next_idx += 1
            lines.append(f"{next_idx}. Số phiên tính từ ngày tham chiếu: {self.add_info['days_since_ref']}")
            next_idx += 1
            lines.append(f"{next_idx}. Số ngày hiệu lực còn lại: {self.add_info['days_remaining']}")
            next_idx += 1

        if self.current_status['entry_date']:
            date_str = self.current_status['entry_date'].strftime('%Y-%m-%d')
            lines.append(f"{next_idx}. Giá bắt đầu vào vùng {self.current_status['ref_percentile']:,.0f}%: {self.current_status['entry_price']:,.2f} USD (Ngày: {date_str})")
            next_idx += 1
            
            max_dd_display = -self.current_status['historical_max_dd_of_zone']
            dd_from_curr_display = ""
            if self.current_status.get('drawdown_from_current') is not None:
                dd_pct = -self.current_status['drawdown_from_current'] * 100
                dd_from_curr_display = f" | Cần giảm thêm {dd_pct:.2f}% từ giá hiện tại"
            
            lines.append(f"{next_idx}. Target Drawdown tiềm năng: {self.current_status['target_price']:,.2f} USD (Mức giảm tệ nhất lịch sử {max_dd_display:.2f}%{dd_from_curr_display})")
        else:
            lines.append(f"{next_idx}. Trạng thái: An toàn (Chưa vào vùng rủi ro cao)")

        return "\n".join(lines)
    
    def save_to_file(self, chart_filename: str = None, image_filename: str = None):
        """Lưu báo cáo ra file .md trong folder re/report"""
        report_text = self.generate_text_report()
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        
        # Tạo folder re/report nếu chưa tồn tại
        report_dir = os.path.join(os.getcwd(), "re", "report")
        os.makedirs(report_dir, exist_ok=True)
        
        filename = f"{timestamp}_{self.ticker}_{self.strategy.report_name}.md"
        file_path = os.path.join(report_dir, filename)
        
        # Thêm biểu đồ vào cuối file report
        report_text += f"\n\n## BIỂU ĐỒ\n"
        
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
