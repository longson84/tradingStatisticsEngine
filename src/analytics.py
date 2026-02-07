import numpy as np
import pandas as pd

class AnalyticsEngine:
    @staticmethod
    def calculate_percentiles(signal_series: pd.Series, percentiles=[1, 5, 10, 15, 20, 25, 30, 40, 50]) -> pd.DataFrame:
        """Tính các ngưỡng giá trị tại các mốc percentile."""
        results = []
        for p in percentiles:
            threshold = np.percentile(signal_series, p)
            results.append({
                "Percentile": p,
                "Threshold": threshold
            })
        return pd.DataFrame(results)

    @staticmethod
    def analyze_drawdown_after_threshold(price_series: pd.Series, signal_series: pd.Series, threshold: float) -> dict:
        """
        Backtest: Khi Signal <= Threshold, giá Price còn giảm thêm bao nhiêu % (Max Drawdown)?
        Đồng thời đếm số ngày (days_below) nằm dưới threshold.
        """
        # Cần align 2 series theo index để đảm bảo tính chính xác
        common_idx = price_series.index.intersection(signal_series.index)
        prices = price_series.loc[common_idx]
        signals = signal_series.loc[common_idx]
        
        # 1. Xác định vùng kích hoạt (Dip Zones)
        is_in_zone = signals <= threshold
        days_in_zone = is_in_zone.sum()
        total_days = len(common_idx)
        
        if not is_in_zone.any():
             return {
                "threshold": threshold,
                "historical_max_drawdown": 0.0,
                "formatted_drawdown": "0.00%",
                "days_in_zone": 0,
                "total_days": total_days
            }

        # 2. Tạo ID cho từng đợt (block) liên tiếp
        # Khi trạng thái thay đổi (True->False hoặc False->True), block_id tăng lên
        block_ids = (is_in_zone != is_in_zone.shift()).cumsum()
        
        # 3. Lọc lấy giá trong các vùng kích hoạt
        zone_prices = prices[is_in_zone]
        zone_blocks = block_ids[is_in_zone]
        
        # 4. Vectorized Logic: Tìm giá Entry của từng block
        # transform('first') sẽ gán giá trị đầu tiên của nhóm cho mọi hàng trong nhóm đó
        entry_prices = zone_prices.groupby(zone_blocks).transform('first')
        
        # 5. Tính Drawdown cho toàn bộ các điểm dữ liệu cùng lúc
        drawdowns = (zone_prices / entry_prices) - 1
        
        # 6. Tìm Max Drawdown (giá trị nhỏ nhất)
        max_dd = drawdowns.min() if not drawdowns.empty else 0.0
                
        return {
            "threshold": threshold,
            "historical_max_drawdown": max_dd,
            "formatted_drawdown": f"{-max_dd*100:.2f}%", # Format số dương
            "days_in_zone": days_in_zone,
            "total_days": total_days
        }

    @staticmethod
    def get_detailed_current_status(price_series: pd.Series, signal_series: pd.Series, stats_history: list) -> dict:
        """
        Trả về thông tin chi tiết về trạng thái hiện tại:
        - Giá, Signal Value, Rarity
        - Đang thuộc vùng percentile nào (Ref Percentile)
        - Giá Entry vào vùng đó (nếu có)
        - Target Drawdown (nếu có)
        """
        current_price = price_series.iloc[-1]
        current_signal = signal_series.iloc[-1]
        
        # 1. Tính độ hiếm (Percentile Rank)
        # Bao nhiêu % lịch sử có giá trị signal thấp hơn giá trị hiện tại?
        rarity = (signal_series < current_signal).mean() * 100
        
        # 2. Xác định Reference Percentile (Vùng rủi ro hiện tại)
        # Tìm threshold nhỏ nhất mà current_signal đang nằm dưới (hoặc bằng)
        # stats_history gồm các dict {'percentile': 1, 'threshold': -0.8, ...}
        sorted_stats = sorted(stats_history, key=lambda x: x['percentile'])
        
        active_stat = None
        for stat in sorted_stats:
            if current_signal <= stat['threshold']:
                active_stat = stat
                break # Tìm thấy bucket nhỏ nhất thỏa mãn
        
        # 3. Kết quả cơ bản
        result = {
            "current_price": current_price,
            "current_signal": current_signal,
            "rarity": rarity,
            "ref_percentile": None,
            "target_drawdown": None,
            "entry_price_at_threshold": None
        }
        
        if active_stat:
            result['ref_percentile'] = active_stat['percentile']
            result['target_drawdown'] = active_stat['historical_max_drawdown']
            # Tìm giá Entry gần nhất vào vùng này (logic đơn giản hóa: lấy giá hiện tại, thực tế nên trace ngược lại)
            # Tuy nhiên, ở đây chỉ để hiển thị cảnh báo
            
        return result

    @staticmethod
    def analyze_entry_points_drawdown(price_series: pd.Series, signal_series: pd.Series, percentile: int) -> list:
        """
        Phân tích chi tiết từng lần tín hiệu đi vào vùng percentile này.
        Trả về list các sự kiện (mỗi lần vào là một item).
        
        Logic:
        - Entry: Ngày đầu tiên signal <= threshold (cắt xuống).
        - Exit Zone: Ngày signal > threshold (thoát khỏi vùng).
        - Bottom: Giá thấp nhất kể từ Entry cho đến nay (hoặc đến khi phục hồi).
        - Recovery: Ngày giá quay lại >= Giá Entry.
        """
        threshold = np.percentile(signal_series, percentile)
        
        # Align data
        common_idx = price_series.index.intersection(signal_series.index)
        prices = price_series.loc[common_idx]
        signals = signal_series.loc[common_idx]
        
        # Xác định trạng thái "Trong vùng"
        is_in_zone = signals <= threshold
        
        # Tìm các điểm chuyển đổi trạng thái để xác định Start Date của từng đợt
        # shift(1) để so sánh với ngày hôm trước.
        # Start: Hôm qua False, Hôm nay True
        starts = (is_in_zone) & (~is_in_zone.shift(1).fillna(False))
        start_dates = starts[starts].index
        
        events = []
        
        for start_date in start_dates:
            entry_price = prices.loc[start_date]
            
            # Slice dữ liệu từ ngày bắt đầu trở đi để tìm đáy và phục hồi
            future_prices = prices.loc[start_date:]
            
            # 1. Tìm đáy (Min Price) & Max Drawdown
            # Lưu ý: Đáy có thể nằm rất xa, thậm chí sau khi tín hiệu đã thoát vùng.
            # Chúng ta sẽ tìm đáy trong khoảng thời gian cho đến khi phục hồi (hoặc hết dữ liệu)
            
            # Tìm ngày phục hồi đầu tiên
            recovery_mask = (future_prices >= entry_price) & (future_prices.index > start_date)
            if recovery_mask.any():
                recovery_date = recovery_mask.idxmax() # Ngày đầu tiên thỏa mãn
                # Chuỗi giá để tìm đáy là từ Start -> Recovery
                drawdown_window = future_prices.loc[:recovery_date]
                status = "Đã phục hồi"
                days_to_recover = (recovery_date - start_date).days
            else:
                recovery_date = None
                drawdown_window = future_prices # Chưa phục hồi -> Tìm đáy trong toàn bộ dữ liệu còn lại
                status = "Chưa phục hồi"
                days_to_recover = None
                
            min_price = drawdown_window.min()
            min_date = drawdown_window.idxmin()
            
            max_dd_pct = (min_price / entry_price) - 1
            days_to_bottom = (min_date - start_date).days
            
            # Format ngày tháng năm
            fmt = '%d/%m/%Y'
            
            events.append({
                "start_date": start_date, # Giữ object datetime để sort
                "start_date_str": start_date.strftime(fmt),
                "entry_price": entry_price,
                "percentile": percentile, # Cố định theo input
                "min_price": min_price,
                "min_date_str": min_date.strftime(fmt),
                "max_dd_pct": max_dd_pct * 100, # %
                "days_to_bottom": days_to_bottom,
                "recovery_date_str": recovery_date.strftime(fmt) if recovery_date else "Chưa phục hồi",
                "days_to_recover": days_to_recover if days_to_recover is not None else "-",
                "status": status
            })
            
        # Sắp xếp: Gần nhất lên đầu (Start Date giảm dần)
        events.sort(key=lambda x: x['start_date'], reverse=True)
        
        return events
