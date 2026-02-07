import numpy as np
import pandas as pd
from src.constants import (
    CALCULATE_PERCENTILES, 
    DRAWDOWN_PERCENTILES, 
    TOP_N_DRAWDOWN,
    DATE_FORMAT_DISPLAY
)

class AnalyticsEngine:
    @staticmethod
    def calculate_percentiles(signal_series: pd.Series, percentiles=CALCULATE_PERCENTILES) -> pd.DataFrame:
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
            "entry_price_at_threshold": None,
            "entry_date": None,
            "entry_price": None,
            "historical_max_dd_of_zone": 0.0,
            "target_price": 0.0,
            "drawdown_from_current": None
        }
        
        if active_stat:
            result['ref_percentile'] = active_stat['percentile']
            result['target_drawdown'] = active_stat['historical_max_drawdown']
            result['historical_max_dd_of_zone'] = active_stat['historical_max_drawdown']
            
            # Tìm giá Entry gần nhất vào vùng này
            # Logic: Scan backwards từ hiện tại để tìm điểm bắt đầu chuỗi signal <= threshold
            threshold = active_stat['threshold']
            
            # Align data
            common_idx = price_series.index.intersection(signal_series.index)
            # Chỉ lấy dữ liệu đến thời điểm hiện tại (nếu series dài hơn)
            # Tuy nhiên ở đây assume series là lịch sử đến hiện tại
            
            signals = signal_series.loc[common_idx]
            prices = price_series.loc[common_idx]
            
            # Check if currently in zone
            if signals.iloc[-1] <= threshold:
                # Find the start of this block
                # is_below: Series boolean
                is_below = signals <= threshold
                
                # Find last False before the end
                # Lấy các index mà NOT below
                not_below_indices = is_below[~is_below].index
                
                # Filter indices before the last index
                valid_indices = not_below_indices[not_below_indices < signals.index[-1]]
                
                if not valid_indices.empty:
                    last_safe_date = valid_indices[-1]
                    # Entry date is the next available date
                    # Find position of last_safe_date
                    loc = signals.index.get_loc(last_safe_date)
                    if loc + 1 < len(signals):
                        entry_date = signals.index[loc + 1]
                    else:
                        entry_date = signals.index[-1]
                else:
                    # Nếu toàn bộ lịch sử đều below threshold (hiếm)
                    entry_date = signals.index[0]
                
                entry_price = prices.loc[entry_date]
                result['entry_date'] = entry_date
                result['entry_price'] = entry_price
                result['entry_price_at_threshold'] = entry_price
                
                # Calculate Target Price
                # historical_max_dd is negative (e.g. -0.25)
                target_price = entry_price * (1 + result['historical_max_dd_of_zone'])
                result['target_price'] = target_price
                
                # Drawdown from current to target
                if current_price > 0:
                    result['drawdown_from_current'] = (target_price / current_price) - 1

            
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
            
            # Slice dữ liệu từ ngày bắt đầu trở đi
            future_prices = prices.loc[start_date:]
            future_signals = signals.loc[start_date:]
            
            # 1. Tìm ngày kết thúc Zone (Signal Exit Date)
            # Là ngày đầu tiên Signal > Threshold kể từ Start Date
            exit_zone_mask = future_signals > threshold
            if exit_zone_mask.any():
                zone_end_date = exit_zone_mask.idxmax()
            else:
                zone_end_date = future_signals.index[-1] # Zone kéo dài đến hết dữ liệu

            # 2. Tìm ngày phục hồi (Price Recovery)
            recovery_mask = (future_prices >= entry_price) & (future_prices.index > start_date)
            
            if recovery_mask.any():
                first_recovery_date = recovery_mask.idxmax()
                
                # QUAN TRỌNG: Drawdown Window phải kéo dài ít nhất đến hết Zone
                # Lý do: Ngay cả khi giá đã hồi (bull trap), nếu Signal vẫn xấu thì vẫn có rủi ro sập tiếp.
                # Ta muốn capture đáy sâu nhất trong suốt thời gian Signal cảnh báo.
                cutoff_date = max(zone_end_date, first_recovery_date)
                
                # Nếu Cutoff Date xa hơn dữ liệu hiện có (vô lý nhưng check cho chắc)
                if cutoff_date > future_prices.index[-1]:
                    cutoff_date = future_prices.index[-1]
                    
                drawdown_window = future_prices.loc[:cutoff_date]
                
                # Status logic:
                # Nếu hiện tại (Last Date) vẫn nằm trong Zone (Zone chưa kết thúc)
                # VÀ giá hiện tại < Entry -> Vẫn coi là Chưa phục hồi (để cảnh báo rủi ro)
                is_zone_active = (zone_end_date == future_prices.index[-1]) and (future_signals.iloc[-1] <= threshold)
                current_price = future_prices.iloc[-1]
                
                if is_zone_active and current_price < entry_price:
                    status = "Chưa phục hồi"
                    # Mặc dù đã có lúc hồi, nhưng hiện tại lại lỗ và Signal xấu -> Cảnh báo!
                    days_to_recover = None 
                    recovery_date_str = "Chưa phục hồi"
                else:
                    status = "Đã phục hồi"
                    days_to_recover = (first_recovery_date - start_date).days
                    recovery_date_str = first_recovery_date.strftime(DATE_FORMAT_DISPLAY)

            else:
                # Chưa bao giờ hồi phục
                drawdown_window = future_prices
                status = "Chưa phục hồi"
                days_to_recover = None
                recovery_date_str = "Chưa phục hồi"
                
            min_price = drawdown_window.min()
            min_date = drawdown_window.idxmin()
            
            max_dd_pct = (min_price / entry_price) - 1
            days_to_bottom = (min_date - start_date).days
            
            # Format ngày tháng năm
            fmt = DATE_FORMAT_DISPLAY
            
            events.append({
                "start_date": start_date, # Giữ object datetime để sort
                "start_date_str": start_date.strftime(fmt),
                "entry_price": entry_price,
                "percentile": percentile, # Cố định theo input
                "min_price": min_price,
                "min_date_str": min_date.strftime(fmt),
                "max_dd_pct": max_dd_pct * 100, # %
                "days_to_bottom": days_to_bottom,
                "recovery_date_str": recovery_date_str,
                "days_to_recover": days_to_recover if days_to_recover is not None else "-",
                "status": status
            })
            
        # Sắp xếp: Gần nhất lên đầu (Start Date giảm dần)
        events.sort(key=lambda x: x['start_date'], reverse=True)
        
        return events

    @staticmethod
    def get_consolidated_drawdown_analysis(price_series: pd.Series, signal_series: pd.Series, percentiles: list = DRAWDOWN_PERCENTILES, top_n: int = TOP_N_DRAWDOWN) -> list:
        """
        Tổng hợp, deduplicate và lọc danh sách drawdown từ nhiều ngưỡng percentile.
        
        Logic:
        1. Quét qua tất cả percentile để tìm các sự kiện.
        2. Tách nhóm "Đã phục hồi" và "Chưa phục hồi".
        3. Nhóm "Đã phục hồi": Deduplicate (lấy percentile thấp nhất cho mỗi ngày), Sort theo Max DD, Lấy Top N.
        4. Nhóm "Chưa phục hồi": Lấy toàn bộ (để cảnh báo rủi ro đầy đủ).
        5. Gộp lại và sort theo thời gian.
        """
        all_events = []
        for p in percentiles:
            events = AnalyticsEngine.analyze_entry_points_drawdown(price_series, signal_series, p)
            all_events.extend(events)
            
        # 1. Deduplicate toàn bộ sự kiện: Giữ lại sự kiện có percentile thấp nhất (nghiêm trọng nhất) cho mỗi start_date
        # Logic này áp dụng cho cả "Đã phục hồi" và "Chưa phục hồi"
        unique_events_map = {}
        for event in all_events:
            d = event['start_date']
            # Nếu chưa có hoặc tìm thấy percentile nhỏ hơn (rủi ro hơn) -> Update
            if d not in unique_events_map or event['percentile'] < unique_events_map[d]['percentile']:
                unique_events_map[d] = event
        
        cleaned_all_events = list(unique_events_map.values())
        
        # 2. Tách nhóm từ danh sách đã làm sạch
        recovered = [e for e in cleaned_all_events if e['status'] != "Chưa phục hồi"]
        unrecovered = [e for e in cleaned_all_events if e['status'] == "Chưa phục hồi"]
        
        # 3. Sort nhóm đã phục hồi theo mức độ giảm giá (max_dd_pct là số âm, càng nhỏ càng tệ -> sort tăng dần)
        recovered.sort(key=lambda x: x['max_dd_pct']) 
        
        # 4. Lấy Top N tệ nhất cho nhóm đã phục hồi
        top_recovered = recovered[:top_n]
        
        # 5. Kết quả cuối cùng = Top Recovered + All Unrecovered (đã deduplicated)
        final_list = top_recovered + unrecovered
        
        # 6. Sort theo thời gian (gần nhất lên đầu)
        final_list.sort(key=lambda x: x['start_date'], reverse=True)
        
        return final_list
