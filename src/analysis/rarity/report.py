"""Report generation — orchestrates computation and stores results as state."""
import pandas as pd

from src.shared.constants import CALCULATE_PERCENTILES
from src.shared.report_blocks import build_report_time_range_info
from src.analysis.rarity.events import calculate_np_events_tree
from src.analysis.rarity.compute import get_detailed_current_status, calculate_np_stats
from src.analysis.rarity.info_blocks import build_current_status_lines
from src.analysis.rarity.tables import build_np_stats_summary_table


class ReportGenerator:
    def __init__(self, ticker, factor, price, factor_series, qr_threshold: int = 5):
        self.ticker = ticker
        self.factor = factor
        self.price = price
        self.factor_series = factor_series
        self.qr_threshold = max(2, int(qr_threshold))
        self.np_events = []
        self.np_stats = {}
        self.current_status = None
        self.add_info = None
        self.np_stats = None
        self.highlight_p = None
        self.time_range_lines = []
        self.status_lines = []
        self.report_text = ""

    def calculate(self):
        self.np_events = calculate_np_events_tree(
            self.price['Close'],
            self.factor_series,
            percentiles=CALCULATE_PERCENTILES
        )

        self.np_stats = calculate_np_stats(self.np_events, self.price, self.qr_threshold)

        self.current_status = get_detailed_current_status(
            self.price['Close'], self.factor_series, self.np_events, self.qr_threshold
        )

        self.add_info = self.factor.get_additional_info(self.price)

        self.np_stats, self.highlight_p = build_np_stats_summary_table(self.np_stats, self.factor, self.current_status)

        self.time_range_lines = build_report_time_range_info(self.price['Close'])
        self.status_lines = build_current_status_lines(self.current_status, self.factor, self.add_info)
        self.report_text = "\n".join(self.time_range_lines + self.status_lines)
