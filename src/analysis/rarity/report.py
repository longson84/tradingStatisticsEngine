"""Report generation — combines data into markdown text."""
import os
from datetime import datetime

import pandas as pd

from src.shared.constants import (
    CALCULATE_PERCENTILES,
    DATE_FORMAT_DISPLAY,
    MAE_PERCENTILES,
)
from src.shared.fmt import fmt_pct, fmt_price
from src.analysis.rarity.events import EventStatus, calculate_np_events_tree
from src.analysis.rarity.percentiles import calculate_signal_percentiles, get_detailed_current_status
from src.analysis.rarity.stats import calculate_np_stats


class ReportGenerator:
    def __init__(self, ticker, indicator, df, signal_series, qr_threshold: int = 5):
        self.ticker = ticker
        self.indicator = indicator
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
        self.stats_df = calculate_signal_percentiles(self.signal_series, percentiles=CALCULATE_PERCENTILES)

        self.np_events = calculate_np_events_tree(
            self.df['Close'],
            self.signal_series,
            percentiles=CALCULATE_PERCENTILES
        )

        self.np_stats = calculate_np_stats(self.np_events, self.df, self.qr_threshold)

        self.current_status = get_detailed_current_status(
            self.df['Close'], self.signal_series, self.np_events, self.qr_threshold
        )

        self.add_info = self.indicator.get_additional_info(self.df)

    def _compute_highlight_p(self) -> int | None:
        current_rarity = self.current_status.get("rarity", 100) if self.current_status else 100
        candidates = [p for p in CALCULATE_PERCENTILES if p > current_rarity]
        return min(candidates) if candidates else None

    def build_stats_df(self):
        """Return (DataFrame, highlight_p) for the NP statistics summary table."""
        from src.analysis.rarity.tables import build_stats_df
        return build_stats_df(self.np_stats, self.indicator, self.current_status)

    def _header_lines(self) -> list:
        return [
            f"## {self.ticker} — {self.indicator.name}",
            f"Ngày thống kê: {datetime.now().strftime(DATE_FORMAT_DISPLAY)}  ",
            f"Ngày dữ liệu đầu tiên: {self.df.index.min().strftime(DATE_FORMAT_DISPLAY)}  ",
            f"Ngày dữ liệu cuối cùng: {self.df.index[-1].strftime(DATE_FORMAT_DISPLAY)}  ",
            f"Tổng số phiên: {len(self.df):,}  ",
            "",
        ]

    def _current_status_lines(self) -> list:
        lines = ["## Trạng thái hiện tại"]
        lines.append(f"1. Giá hiện tại: {fmt_price(self.current_status['current_price'])}")
        display_current_signal = self.indicator.format_value(self.current_status['current_signal'])
        lines.append(f"2. {self.indicator.name} hiện tại: {display_current_signal}")
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
        if event.days_to_recover is not None and event.days_to_recover <= self.qr_threshold:
            return []

        indent = "&nbsp;&nbsp;" * level + "- " if level > 0 else ""
        display_date = f"{indent}{event.start_date.strftime(DATE_FORMAT_DISPLAY)}"
        mae_str = fmt_pct(event.mae_pct)
        rec_date_str = event.recovery_date.strftime(DATE_FORMAT_DISPLAY) if event.recovery_date else "-"
        days_rec_str = str(event.days_to_recover) if event.days_to_recover is not None else "-"

        if event.status == EventStatus.UNRECOVERED:
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

    def generate_display_report(self) -> str:
        if not self.np_events:
            self.calculate()
        lines = self._header_lines() + self._current_status_lines()
        return "\n".join(lines)

    def generate_text_report(self):
        if not self.np_events:
            self.calculate()

        lines = self._header_lines()

        lines.append(f"## Thống kê các sự kiện NP tổng hợp")

        header = ["PCT", "Tín hiệu", "Lần", "QR", "QR (%)", "5 năm", "10 năm", "Ngày", "MMAE (%)"]
        sorted_mae_percentiles = sorted(MAE_PERCENTILES, reverse=True)
        for mp in sorted_mae_percentiles:
            header.append(f"MAE-{mp}%")

        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join([":---"] * len(header)) + " |")

        highlight_p = self._compute_highlight_p()

        for p in CALCULATE_PERCENTILES:
            stat = self.np_stats.get(p)
            if not stat:
                continue

            row = []
            row.append(f"{p}%")
            row.append(self.indicator.format_value(stat['threshold']))
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

            if p == highlight_p:
                row = [f"<span style='background-color: #FFD700; color: black; padding: 2px 4px; border-radius: 4px;'><b>{cell}</b></span>" for cell in row]

            lines.append("| " + " | ".join(row) + " |")

        lines.append("")

        lines.extend(self._current_status_lines())

        lines.append(f"## Danh sách các sự kiện NP (Chi tiết)")
        lines.append("<details>")
        lines.append("<summary>Bấm để xem danh sách chi tiết</summary>")
        lines.append("")

        tree_header = ["Ngày bắt đầu", "NP", "Giá", "Đáy", "Ngày đáy", "MAE (%)", "T đến đáy", "Phục hồi", "T phục hồi", "P-Cov"]
        lines.append("| " + " | ".join(tree_header) + " |")
        lines.append("| " + " | ".join([":---"] * len(tree_header)) + " |")

        top_events = [e for e in self.np_events if e.upline_id is None]
        top_events.sort(key=lambda x: x.start_date, reverse=True)

        for event in top_events:
            lines.extend(self._render_event_lines(event))

        lines.append("")
        lines.append("</details>")
        lines.append("")

        return "\n".join(lines)

    def save_to_file(self, chart_filename: str = None, image_filename: str = None, dist_chart_filename: str = None, dist_image_filename: str = None):
        report_text = self.generate_text_report()
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")

        report_dir = os.path.join(os.getcwd(), "re", "report")
        os.makedirs(report_dir, exist_ok=True)

        filename = f"{timestamp}_{self.ticker}_{self.indicator.report_name}.md"
        file_path = os.path.join(report_dir, filename)

        report_text += f"\n\n## BIỂU ĐỒ PHÂN PHỐI\n"
        if dist_image_filename:
            relative_dist_image_path = f"../charts/{dist_image_filename}"
            report_text += f"![Biểu đồ phân phối]({relative_dist_image_path})\n\n"

        if dist_chart_filename:
            relative_dist_html_path = f"../charts/{dist_chart_filename}"
            report_text += f"Xem biểu đồ phân phối tương tác: [{dist_chart_filename}]({relative_dist_html_path})\n"

        report_text += f"\n\n## BIỂU ĐỒ TÍN HIỆU\n"

        if image_filename:
            relative_image_path = f"../charts/{image_filename}"
            report_text += f"![Biểu đồ phân tích]({relative_image_path})\n\n"

        if chart_filename:
            relative_html_path = f"../charts/{chart_filename}"
            report_text += f"Xem biểu đồ tương tác (Zoom/Pan): [{chart_filename}]({relative_html_path})\n"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_text)
            return file_path
        except Exception as e:
            print(f"Error saving file: {e}")
            return None
