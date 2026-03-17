import os
from datetime import datetime
import pandas as pd
import numpy as np
from src.signal.analytics import (
    calculate_signal_percentiles,
    calculate_np_events_tree,
    get_detailed_current_status,
)
from src.constants import DATE_FORMAT_DISPLAY, fmt_price, fmt_pct
from src.signal.constants import (
    CALCULATE_PERCENTILES,
    MAE_PERCENTILES,
    MIN_RECOVERY_DAYS_THRESHOLD,
)

class ReportGenerator:
    def __init__(self, ticker, strategy, df, signal_series, qr_threshold: int = MIN_RECOVERY_DAYS_THRESHOLD):
        self.ticker = ticker
        self.strategy = strategy
        self.df = df
        self.signal_series = signal_series
        self.qr_threshold = max(2, int(qr_threshold))
        self.stats_df = None
        self.stats_history = []
        self.current_status = None
        self.add_info = None
        self.np_events = []
        self.np_stats = {}

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

        # 4. Derive current status from the already-computed tree (no double work)
        self.current_status = get_detailed_current_status(
            self.df['Close'], self.signal_series, self.np_events, self.qr_threshold
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
                
            qr_count = sum(1 for e in events if e.days_to_recover is not None and e.days_to_recover <= self.qr_threshold)
            
            # Count 5y/10y (Total and QR)
            count_5y = 0
            qr_5y = 0
            count_10y = 0
            qr_10y = 0
            
            for e in events:
                is_qr_event = e.days_to_recover is not None and e.days_to_recover <= self.qr_threshold
                
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
                    # Active — count trading days via index position
                    last_idx = len(self.df) - 1
                    start_idx = self.df.index.get_loc(e.start_date)
                    total_days += last_idx - start_idx
                
                # Filter out Quick Recovery events for MAE stats
                is_qr = e.days_to_recover is not None and e.days_to_recover <= self.qr_threshold
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

    def _compute_highlight_p(self) -> int | None:
        """Return the smallest percentile zone above the current rarity, or None."""
        current_rarity = self.current_status.get("rarity", 100) if self.current_status else 100
        candidates = [p for p in CALCULATE_PERCENTILES if p > current_rarity]
        return min(candidates) if candidates else None

    def build_stats_df(self):
        """Return (DataFrame, highlight_p) for the NP statistics summary table."""
        sorted_mae = sorted(MAE_PERCENTILES, reverse=True)

        highlight_p = self._compute_highlight_p()

        rows = []
        for p in CALCULATE_PERCENTILES:
            stat = self.np_stats.get(p)
            if not stat:
                continue
            row = {
                "PCT": f"{p}%",
                "Signal": self.strategy.format_value(stat["threshold"]),
                "Count": stat["count"],
                "QR": stat["qr"],
                "QR %": fmt_pct(stat['qr_pct']),
                "5Y": f"{stat['count_5y']}/{stat['qr_5y']}",
                "10Y": f"{stat['count_10y']}/{stat['qr_10y']}",
                "Days": stat["total_days"],
                "MMAE %": fmt_pct(stat['mmae']),
                "_highlight": p == highlight_p,
            }
            for mp in sorted_mae:
                val = stat["mae_stats"].get(mp, 0)
                row[f"MAE-{mp}%"] = fmt_pct(val)
            rows.append(row)

        return pd.DataFrame(rows), highlight_p

    # ------------------------------------------------------------------
    # Private section builders
    # ------------------------------------------------------------------

    def _header_lines(self) -> list:
        return [
            f"## {self.ticker} — {self.strategy.name}",
            f"Ngày thống kê: {datetime.now().strftime(DATE_FORMAT_DISPLAY)}  ",
            f"Ngày dữ liệu đầu tiên: {self.df.index.min().strftime(DATE_FORMAT_DISPLAY)}  ",
            f"Ngày dữ liệu cuối cùng: {self.df.index[-1].strftime(DATE_FORMAT_DISPLAY)}  ",
            f"Tổng số phiên: {len(self.df):,}  ",
            "",
        ]

    def _current_status_lines(self) -> list:
        lines = ["## Trạng thái hiện tại"]
        lines.append(f"1. Giá hiện tại: {fmt_price(self.current_status['current_price'])}")
        display_current_signal = self.strategy.format_value(self.current_status['current_signal'])
        lines.append(f"2. {self.strategy.name} hiện tại: {display_current_signal}")
        lines.append(f"3. Độ hiếm hiện tại: {fmt_pct(self.current_status['rarity'])}")

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
            lines.append(f"{next_idx}. Giá bắt đầu vào vùng {self.current_status['ref_percentile']:,.0f}% từ ngày: {date_str} ở mức {fmt_price(self.current_status['entry_price'])}")
            next_idx += 1
            if self.current_status.get('days_in_current_zone') is not None:
                lines.append(f"{next_idx}. Giá đã ở vùng hiện tại: {self.current_status['days_in_current_zone']} phiên")
                next_idx += 1
            max_dd_display = -self.current_status['historical_max_dd_of_zone'] * 100
            dd_from_curr_display = ""
            if self.current_status.get('drawdown_from_current') is not None:
                dd_pct = -self.current_status['drawdown_from_current'] * 100
                dd_from_curr_display = f"~ giảm {fmt_pct(dd_pct)} từ hiện tại"
            lines.append(f"{next_idx}. Giá có thể giảm đến {fmt_price(self.current_status['target_price'])}, {dd_from_curr_display}, Max DD: {fmt_pct(max_dd_display)}")
        else:
            lines.append(f"{next_idx}. Trạng thái: An toàn (Chưa vào vùng rủi ro cao)")
        return lines

    def _render_event_lines(self, event, level: int = 0) -> list:
        """Return markdown table row(s) for *event* and all its non-QR children."""
        if event.days_to_recover is not None and event.days_to_recover <= self.qr_threshold:
            return []

        indent = "&nbsp;&nbsp;" * level + "- " if level > 0 else ""
        display_date = f"{indent}{event.start_date.strftime(DATE_FORMAT_DISPLAY)}"
        mae_str = fmt_pct(event.mae_pct)
        rec_date_str = event.recovery_date.strftime(DATE_FORMAT_DISPLAY) if event.recovery_date else "-"
        days_rec_str = str(event.days_to_recover) if event.days_to_recover is not None else "-"

        if event.status == "Chưa phục hồi":
            display_date = f"**{display_date}**"
            mae_str = f"<span style='color:red'>{mae_str}</span>"
            days_active = len(self.df) - 1 - self.df.index.get_loc(event.start_date)
            days_rec_str = f"<span style='color:red'>{days_active} (chưa phục hồi)</span>"

        row = [
            display_date,
            f"{event.percentile}%",
            fmt_price(event.entry_price),
            fmt_price(event.min_price),
            event.min_date.strftime(DATE_FORMAT_DISPLAY),
            mae_str,
            str(event.days_to_bottom),
            rec_date_str,
            days_rec_str,
            str(event.p_coverage),
        ]
        result = ["| " + " | ".join(row) + " |"]

        children = sorted(
            [e for e in self.np_events if e.upline_id == event.id],
            key=lambda x: x.start_date,
        )
        for child in children:
            result.extend(self._render_event_lines(child, level + 1))
        return result

    # ------------------------------------------------------------------

    def generate_display_report(self) -> str:
        """Header + current status only — for UI display (stats table rendered separately)."""
        if not self.np_events:
            self.calculate()
        lines = self._header_lines() + self._current_status_lines()
        return "\n".join(lines)

    def generate_text_report(self):
        """Tạo nội dung báo cáo dạng text (dùng cho print và save file)."""
        if not self.np_events:
            self.calculate()

        lines = self._header_lines()

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
        
        highlight_p = self._compute_highlight_p()
        
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
            row.append(fmt_pct(stat['qr_pct']))
            row.append(f"{stat['count_5y']}/{stat['qr_5y']}")
            row.append(f"{stat['count_10y']}/{stat['qr_10y']}")
            row.append(f"{stat['total_days']:,}")
            row.append(fmt_pct(stat['mmae']))
            
            for mp in sorted_mae_percentiles:
                val = stat['mae_stats'].get(mp, 0)
                row.append(fmt_pct(val))
            
            # Highlight row if it matches the target percentile
            if p == highlight_p:
                # Use Gold background and Black text to highlight
                row = [f"<span style='background-color: #FFD700; color: black; padding: 2px 4px; border-radius: 4px;'><b>{cell}</b></span>" for cell in row]
                
            lines.append("| " + " | ".join(row) + " |")
            
        lines.append("")


        lines.extend(self._current_status_lines())
        
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
        
        for event in top_events:
            lines.extend(self._render_event_lines(event))
            
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
