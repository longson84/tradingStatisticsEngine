import numpy as np
import pandas as pd

class AnalyticsEngine:
    @staticmethod
    def calculate_percentiles(signal_series: pd.Series, percentiles=[1, 5, 10, 20, 50]) -> pd.DataFrame:
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
            "entry_price": None,
            "entry_date": None,
            "target_price": None,
            "historical_max_dd_of_zone": 0.0,
            "drawdown_from_current": None
        }
        
        # 4. Nếu đang trong vùng rủi ro (active_stat tìm thấy)
        if active_stat:
            result['ref_percentile'] = active_stat['percentile']
            result['historical_max_dd_of_zone'] = active_stat['max_dd'] * 100
            
            thresh = active_stat['threshold']
            
            # Align dữ liệu để tìm Entry Date
            common_idx = price_series.index.intersection(signal_series.index)
            s_aligned = signal_series.loc[common_idx]
            p_aligned = price_series.loc[common_idx]
            
            # Boolean mask: Những ngày nào nằm trong vùng này
            is_in_zone = s_aligned <= thresh
            
            # Tìm điểm bắt đầu của đợt (block) hiện tại
            # Chúng ta biết điểm cuối cùng (iloc[-1]) là True (do logic tìm active_stat)
            # Ta scan ngược lại tìm điểm False gần nhất
            
            # Convert to numpy for speed
            not_in_zone_indices = np.where(~is_in_zone)[0]
            
            if len(not_in_zone_indices) > 0:
                # Điểm False cuối cùng
                last_false_idx = not_in_zone_indices[-1]
                # Điểm Entry là điểm ngay sau đó
                entry_idx = last_false_idx + 1
            else:
                # Toàn bộ lịch sử đều nằm trong zone (hiếm)
                entry_idx = 0
            
            if entry_idx < len(common_idx):
                entry_date = common_idx[entry_idx]
                entry_price = p_aligned.iloc[entry_idx]
                
                result['entry_date'] = entry_date
                result['entry_price'] = entry_price
                
                # Target Price = Entry * (1 + Max_DD_History)
                # Max_DD_History là số âm (ví dụ -0.5)
                target_price = entry_price * (1 + active_stat['max_dd'])
                result['target_price'] = target_price

                # Tính Drawdown từ giá hiện tại đến Target Price
                if current_price > 0:
                    result['drawdown_from_current'] = (target_price / current_price) - 1
                
        return result

    @staticmethod
    def get_current_status(signal_series: pd.Series) -> dict:
        current_val = signal_series.iloc[-1]
        # Tính độ hiếm (Rarity): Giá trị hiện tại thấp hơn bao nhiêu % lịch sử
        rarity = (signal_series < current_val).mean() * 100
        return {
            "current_value": current_val,
            "rarity_score": rarity
        }
