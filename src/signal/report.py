import os
from datetime import datetime
import pandas as pd
import numpy as np
from src.analytics import (
    calculate_signal_percentiles,
    get_detailed_current_status,
    calculate_np_events_tree  # New function
)
from src.constants import (
    CALCULATE_PERCENTILES,
    DRAWDOWN_PERCENTILES,
    TOP_N_DRAWDOWN,
    DATE_FORMAT_DISPLAY,
    MIN_RECOVERY_DAYS_THRESHOLD,
    DRAWDOWN_PERCENTILES_FOR_THRESHOLD,
    MAE_PERCENTILES # New constant
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
        self.np_events = [] # Store NP Events
        self.np_stats = {} # Store Summary Stats

    def calculate(self):
        """Thực hiện toàn bộ các tính toán thống kê."""
        # 1. Calculate Percentiles (Legacy support for current status)
        self.stats_df = calculate_signal_percentiles(self.signal_series, percentiles=CALCULATE_PERCENTILES)
        
        # 2. Calculate NP Events (New Logic)
        self.np_events = calculate_np_events_tree(
            self.df['Close'], 
            self.signal_series, 
            percentiles=CALCULATE_PERCENTILES
        )
        
        # 3. Calculate NP Statistics Grouped by Percentile
        self.np_stats = self._calculate_np_stats()

        # 4. Calculate Current Status (Keep existing logic for now)
        self.current_status = get_detailed_current_status(
            self.df['Close'], self.signal_series
        )
        
        # 5. Additional Info
        self.add_info = self.strategy.get_additional_info(self.df)

    def _calculate_np_stats(self):
        stats = {}
        last_date = self.df.index[-1]
        date_5y = last_date - pd.DateOffset(years=5)
        date_10y = last_date - pd.DateOffset(years=10)
        
        for p in CALCULATE_PERCENTILES:
            # Filter events for this percentile
            events = [e for e in self.np_events if e.percentile == p]
            
            n_count = len(events)
            if n_count == 0:
                stats[p] = None
                continue
                
            qr_count = sum(1 for e in events if e.days_to_recover is not None and e.days_to_recover <= MIN_RECOVERY_DAYS_THRESHOLD)
            
            # Count 5y/10y (Total and QR)
            count_5y = 0
            qr_5y = 0
            count_10y = 0
            qr_10y = 0
            
            for e in events:
                is_qr_event = e.days_to_recover is not None and e.days_to_recover <= MIN_RECOVERY_DAYS_THRESHOLD
                
                if e.start_date >= date_5y:
                    count_5y += 1
                    if is_qr_event:
                        qr_5y += 1
                        
                if e.start_date >= date_10y:
                    count_10y += 1
                    if is_qr_event:
                        qr_10y += 1
            
            total_days = 0
            mae_values = []
            
            for e in events:
                # Total Days: If recovered, use days_to_recover. If active, days until now.
                # In NPEvent logic, days_to_recover is None if active.
                if e.days_to_recover is not None:
                    total_days += e.days_to_recover
                else:
                    # Active
                    # Calculate days active from start to last_date
                    days_active = (last_date - e.start_date).days # Or trading days if we want strict
                    # For simplicity use rough days or re-calc trading days. 
                    # Actually calculate_np_events_tree calculates days_to_bottom for active.
                    # Let's approximate or use existing fields if we added them.
                    # Ideally we should use index difference.
                    # Let's use (last_date - start_date).days for consistency with "Age"
                    total_days += (last_date - e.start_date).days
                
                # Filter out Quick Recovery events for MAE stats
                is_qr = e.days_to_recover is not None and e.days_to_recover <= MIN_RECOVERY_DAYS_THRESHOLD
                if not is_qr:
                    mae_values.append(e.mae_pct)
                
            # MAE Stats
            mmae = max(mae_values) if mae_values else 0
            mae_percentiles_vals = {}
            if mae_values:
                # percentiles of MAE
                # reqv2: MAE (%) - m: ngưỡng percentile m của các MAE (%)
                # m, n, p, q = MAE_PERCENTILES
                for mp in MAE_PERCENTILES:
                    mae_percentiles_vals[mp] = np.percentile(mae_values, mp)
            
            # Find signal threshold for this p
            # We can pick from first event or re-calculate
            threshold = events[0].threshold if events else 0
            
            stats[p] = {
                "threshold": threshold,
                "count": n_count,
                "qr": qr_count,
                "qr_pct": (qr_count / n_count) * 100,
                "count_5y": count_5y,
                "qr_5y": qr_5y,
                "count_10y": count_10y,
                "qr_10y": qr_10y,
                "total_days": total_days,
                "mmae": mmae,
                "mae_stats": mae_percentiles_vals
            }
        return stats

    def generate_text_report(self):
        """Tạo nội dung báo cáo dạng text (dùng cho print và save file)."""
        if not self.np_events:
            self.calculate()
            
        lines = []
        # Header
        lines.append(f"## {self.ticker} — {self.strategy.name}")
        lines.append(f"Ngày thống kê: {datetime.now().strftime(DATE_FORMAT_DISPLAY)}  ")
        # ... (keep existing basic info) ...
        start_date_str = self.df.index.min().strftime(DATE_FORMAT_DISPLAY)
        lines.append(f"Ngày dữ liệu đầu tiên: {start_date_str}  ")
        lines.append(f"Ngày dữ liệu cuối cùng: {self.df.index[-1].strftime(DATE_FORMAT_DISPLAY)}  ")
        lines.append(f"Tổng số phiên: {len(self.df):,}  ")
        lines.append("")

        # 1. Bảng thống kê tổng hợp (New Table)
        lines.append(f"## Thống kê các sự kiện NP tổng hợp")
        
        # Header
        # PCT | Tín hiệu | Lần | QR | QR(%) | 5 Năm | 10 Năm | Ngày | MMAE(%) | MAE-m | MAE-n ...
        header = ["PCT", "Tín hiệu", "Lần", "QR", "QR (%)", "5 năm", "10 năm", "Ngày", "MMAE (%)"]
        
        # Reverse MAE Percentiles
        sorted_mae_percentiles = sorted(MAE_PERCENTILES, reverse=True)
        
        for mp in sorted_mae_percentiles:
            header.append(f"MAE-{mp}%")
            
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join([":---"] * len(header)) + " |")
        
        # Determine highlight row based on current rarity
        current_rarity = self.current_status.get('rarity', 100) if self.current_status else 100
        highlight_p = None
        # Find the smallest percentile > current_rarity
        candidates = [p for p in CALCULATE_PERCENTILES if p > current_rarity]
        if candidates:
            highlight_p = min(candidates)
        
        # Rows
        for p in CALCULATE_PERCENTILES:
            stat = self.np_stats.get(p)
            if not stat:
                continue
                
            row = []
            row.append(f"{p}%")
            row.append(self.strategy.format_value(stat['threshold']))
            row.append(str(stat['count']))
            row.append(str(stat['qr']))
            row.append(f"{stat['qr_pct']:.1f}%")
            row.append(f"{stat['count_5y']}/{stat['qr_5y']}")
            row.append(f"{stat['count_10y']}/{stat['qr_10y']}")
            row.append(f"{stat['total_days']:,}")
            row.append(f"{stat['mmae']:.2f}%")
            
            for mp in sorted_mae_percentiles:
                val = stat['mae_stats'].get(mp, 0)
                row.append(f"{val:.2f}%")
            
            # Highlight row if it matches the target percentile
            if p == highlight_p:
                # Use Gold background and Black text to highlight
                row = [f"<span style='background-color: #FFD700; color: black; padding: 2px 4px; border-radius: 4px;'><b>{cell}</b></span>" for cell in row]
                
            lines.append("| " + " | ".join(row) + " |")
            
        lines.append("")


        # 3. Current Status (Keep existing)
        lines.append("## Trạng thái hiện tại")
        # ... (Reuse existing logic for Current Status display) ...
        # Copied from original file
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
        
        # 2. Bảng liệt kê sự kiện (Tree View)
        lines.append(f"## Danh sách các sự kiện NP (Chi tiết)")
        lines.append("<details>")
        lines.append("<summary>Bấm để xem danh sách chi tiết</summary>")
        lines.append("")
        
        # Table Header
        tree_header = ["Ngày bắt đầu", "NP", "Giá", "Đáy", "Ngày đáy", "MAE (%)", "T đến đáy", "Phục hồi", "T phục hồi", "P-Cov"]
        lines.append("| " + " | ".join(tree_header) + " |")
        lines.append("| " + " | ".join([":---"] * len(tree_header)) + " |")
        
        # Recursive Render
        # Filter top-level events
        top_events = [e for e in self.np_events if e.upline_id is None]
        # Sort by start_date desc
        top_events.sort(key=lambda x: x.start_date, reverse=True)
        
        event_map = {e.id: e for e in self.np_events}
        
        def render_event(event, level=0):
            # Skip Quick Recovery events
            if event.days_to_recover is not None and event.days_to_recover <= MIN_RECOVERY_DAYS_THRESHOLD:
                return

            # Format
            # Indent: Level 0 -> "", Level 1 -> "&nbsp;&nbsp;- ", Level 2 -> "&nbsp;&nbsp;&nbsp;&nbsp;- "
            indent = ""
            if level > 0:
                indent = "&nbsp;&nbsp;" * level + "- "
            
            start_str = event.start_date.strftime(DATE_FORMAT_DISPLAY)
            display_date = f"{indent}{start_str}"
            
            np_str = f"{event.percentile}%"
            
            price_str = f"{event.entry_price:,.2f}"
            min_price_str = f"{event.min_price:,.2f}"
            min_date_str = event.min_date.strftime(DATE_FORMAT_DISPLAY)
            mae_str = f"{event.mae_pct:.2f}%"
            
            rec_date_str = event.recovery_date.strftime(DATE_FORMAT_DISPLAY) if event.recovery_date else "-"
            
            days_rec_str = str(event.days_to_recover) if event.days_to_recover is not None else "-"
            
            # Highlight if active
            if event.status == "Chưa phục hồi":
                display_date = f"**{display_date}**"
                mae_str = f"<span style='color:red'>{mae_str}</span>"
                
                # Calculate days from start to now for unrecovered events
                days_active = (self.df.index[-1] - event.start_date).days
                days_rec_str = f"<span style='color:red'>{days_active} (chưa phục hồi)</span>"
            
            row = [
                display_date,
                np_str,
                price_str,
                min_price_str,
                min_date_str,
                mae_str,
                str(event.days_to_bottom),
                rec_date_str,
                days_rec_str,
                str(event.p_coverage)
            ]
            lines.append("| " + " | ".join(row) + " |")
            
            # Render Children
            # Find children
            children = [e for e in self.np_events if e.upline_id == event.id]
            # Sort children by date (req: "theo thứ tự diễn ra của chúng") -> Ascending?
            # Usually sub-events happen after start.
            children.sort(key=lambda x: x.start_date)
            
            for child in children:
                render_event(child, level + 1)

        for event in top_events:
            render_event(event)
            
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
