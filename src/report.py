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
                'historical_max_drawdown': dd_result['historical_max_drawdown'],
                'dd_result': dd_result  # Store full result for display
            })

        # 3. Calculate Current Status
        # AnalyticsEngine.get_detailed_current_status expects stats_history with keys 'percentile', 'threshold', 'historical_max_drawdown'
        self.current_status = AnalyticsEngine.get_detailed_current_status(
            self.df['Close'], self.signal_series, self.stats_history
        )
        
        # 3.1 Calculate Detailed Drawdown History (New Section)
        # Các percentile quan trọng cần theo dõi chi tiết
        detailed_percentiles = [20, 15, 10, 5, 1]
        self.detailed_drawdown_history = []
        for p in detailed_percentiles:
             events = AnalyticsEngine.analyze_entry_points_drawdown(
                self.df['Close'], 
                self.signal_series, 
                p
            )
             self.detailed_drawdown_history.extend(events)
        
        # Sắp xếp theo ngày bắt đầu giảm dần (gần nhất trước)
        self.detailed_drawdown_history.sort(key=lambda x: (x['start_date'], -x['percentile']), reverse=True)

        # 4. Additional Info
        self.add_info = self.strategy.get_additional_info(self.df)

    def generate_text_report(self):
        """Tạo nội dung báo cáo dạng text (dùng cho print và save file)."""
        if self.current_status is None:
            self.calculate()
            
        lines = []
        # Header
        lines.append(f"# TRADING STATISTICS REPORT")
        lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
        lines.append(f"Ticker: {self.ticker}  ")
        
        # Lấy ngày bắt đầu dữ liệu
        start_date_str = self.df.index.min().strftime('%Y-%m-%d')
        lines.append(f"Data History From: {start_date_str}  ")
        
        lines.append(f"Strategy: {self.strategy.name}  ")
        lines.append("")

        # Risk History Table
        lines.append(f"## BẢNG THỐNG KÊ RỦI RO LỊCH SỬ")
        # Markdown Table Header
        lines.append(f"| PERCENTILE | TÍN HIỆU | SỐ NGÀY | MAX DD TỪ PERCENTILE |")
        lines.append(f"| :--- | :--- | :--- | :--- |")

        for item in self.stats_history:
            row = item
            dd_result = item['dd_result']
            thresh = row['threshold']
            
            # Use strategy's format_value method
            display_thresh = self.strategy.format_value(thresh)
            
            days_info = f"{dd_result['days_in_zone']}/{dd_result['total_days']}"
            
            # Markdown Table Row
            lines.append(f"| {row['percentile']:.0f}% | {display_thresh} | {days_info} | {dd_result['formatted_drawdown']} |")
        
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
            # Kiểm tra nếu có key 'days_remaining' (cho strategy 2)
            if 'days_remaining' in self.add_info:
                next_idx += 1
                lines.append(f"{next_idx}. Số ngày hiệu lực còn lại: {self.add_info['days_remaining']}")

        lines.append("")
        
        # Detailed Drawdown History Table (New Section)
        lines.append(f"## LỊCH SỬ CÁC LẦN DRAWDOWN CHI TIẾT (VÙNG HIẾM)")
        lines.append(f"| Ngày bắt đầu | Giá | Percentile | Giá đáy | Ngày đáy | Max DD (%) | Số ngày đến đáy | Ngày phục hồi | Số ngày phục hồi | Trạng thái |")
        lines.append(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        
        for event in self.detailed_drawdown_history:
             price_str = f"{event['entry_price']:,.2f}"
             min_price_str = f"{event['min_price']:,.2f}"
             dd_str = f"{event['max_dd_pct']:.2f}%"
             
             row = f"| {event['start_date_str']} | {price_str} | {event['percentile']}% | {min_price_str} | {event['min_date_str']} | {dd_str} | {event['days_to_bottom']} | {event['recovery_date_str']} | {event['days_to_recover']} | {event['status']} |"
             lines.append(row)

        # 5. Target Drawdown Analysis
        if self.current_status.get('ref_percentile') is not None and self.current_status.get('target_drawdown') is not None:
            lines.append("")
            lines.append("## PHÂN TÍCH RỦI RO TIỀM NĂNG")
            
            ref_p = self.current_status['ref_percentile']
            target_dd = self.current_status['target_drawdown']
            
            lines.append(f"Tín hiệu đang nằm trong nhóm {ref_p}% thấp nhất lịch sử.")
            lines.append(f"- Max Drawdown lịch sử vùng này: {target_dd:.2f}%")
            
            if self.current_status.get('entry_price_at_threshold'):
                entry_price = self.current_status['entry_price_at_threshold']
                target_price = entry_price * (1 + target_dd / 100.0)
                current_price = self.current_status['current_price']
                
                lines.append(f"- Giá tham chiếu (vào vùng): {entry_price:,.2f}")
                lines.append(f"- Giá đáy tiềm năng (nếu lặp lại): {target_price:,.2f}")
                
                downside_pct = ((target_price - current_price) / current_price) * 100
                lines.append(f"- Dư địa giảm từ giá hiện tại: {downside_pct:.2f}%")

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
