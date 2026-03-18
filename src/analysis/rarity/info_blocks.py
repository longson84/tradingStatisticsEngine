"""Markdown info block builders for rarity report sections."""
from src.shared.constants import DATE_FORMAT_DISPLAY
from src.shared.fmt import fmt_pct, fmt_price


def build_current_status_lines(current_status: dict, factor, add_info: dict | None) -> list[str]:
    """Build the current status section lines for the rarity report."""
    lines = ["### Trạng thái hiện tại"]
    lines.append(f"1. Giá hiện tại: {fmt_price(current_status['current_price'])}")
    display_current_factor = factor.format_value(current_status['current_factor'])
    lines.append(f"2. {factor.name} hiện tại: {display_current_factor}")
    lines.append(f"3. Độ hiếm hiện tại: {fmt_pct(current_status['rarity'])}")

    next_idx = 4
    if add_info:
        lines.append(f"{next_idx}. Ngày tham chiếu: {add_info['ref_date']}")
        next_idx += 1
        lines.append(f"{next_idx}. Giá trị tham chiếu: {add_info['ref_value']}")
        next_idx += 1
        lines.append(f"{next_idx}. Số phiên tính từ ngày tham chiếu: {add_info['days_since_ref']}")
        if 'days_remaining' in add_info:
            next_idx += 1
            lines.append(f"{next_idx}. Số ngày hiệu lực còn lại: {add_info['days_remaining']}")

    if current_status.get('entry_date'):
        date_str = current_status['entry_date'].strftime(DATE_FORMAT_DISPLAY)
        lines.append(f"{next_idx}. Giá bắt đầu vào vùng {current_status['ref_percentile']:,.0f}% từ ngày: {date_str} ở mức {fmt_price(current_status['entry_price'])}")
        next_idx += 1
        if current_status.get('days_in_current_zone') is not None:
            lines.append(f"{next_idx}. Giá đã ở vùng hiện tại: {current_status['days_in_current_zone']} phiên")
            next_idx += 1
        max_dd_display = -current_status['historical_max_dd_of_zone'] * 100
        dd_from_curr_display = ""
        if current_status.get('drawdown_from_current') is not None:
            dd_pct = -current_status['drawdown_from_current'] * 100
            dd_from_curr_display = f"~ giảm {fmt_pct(dd_pct)} từ hiện tại"
        lines.append(f"{next_idx}. Giá có thể giảm đến {fmt_price(current_status['target_price'])}, {dd_from_curr_display}, Max DD: {fmt_pct(max_dd_display)}")
    else:
        lines.append(f"{next_idx}. Trạng thái: An toàn (Chưa vào vùng rủi ro cao)")
    return lines
