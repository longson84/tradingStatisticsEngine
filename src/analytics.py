import numpy as np
import pandas as pd
from src.constants import (
    CALCULATE_PERCENTILES, 
    DRAWDOWN_PERCENTILES, 
    TOP_N_DRAWDOWN,
    MIN_RECOVERY_DAYS_THRESHOLD,
    DRAWDOWN_PERCENTILES_FOR_THRESHOLD
)

import uuid
from typing import List, Dict, Optional

class NPEvent:
    def __init__(self, percentile: float, threshold: float, start_date, entry_price: float, upline_id: Optional[str] = None):
        self.id = str(uuid.uuid4())
        self.percentile = percentile
        self.threshold = threshold
        self.start_date = start_date
        self.entry_price = entry_price
        self.upline_id = upline_id
        
        self.min_price = entry_price
        self.min_date = start_date
        
        self.status = "Chưa phục hồi"
        self.recovery_date = None
        self.days_to_recover = None
        self.days_to_bottom = 0
        
        self.children_ids = [] # List of child event IDs
        self.p_coverage = 0

    def update_price(self, date, price):
        if price < self.min_price:
            self.min_price = price
            self.min_date = date
            
    def close(self, recovery_date, price_series):
        self.status = "Đã phục hồi"
        self.recovery_date = recovery_date
        
        # Calculate days based on trading days (index difference)
        try:
            start_idx = price_series.index.get_loc(self.start_date)
            rec_idx = price_series.index.get_loc(recovery_date)
            self.days_to_recover = rec_idx - start_idx
            
            min_idx = price_series.index.get_loc(self.min_date)
            self.days_to_bottom = min_idx - start_idx
        except:
            # Fallback if index lookup fails (rare)
            self.days_to_recover = (recovery_date - self.start_date).days
            self.days_to_bottom = (self.min_date - self.start_date).days

    @property
    def mae_pct(self):
        return (1 - self.min_price / self.entry_price) * 100

def calculate_signal_percentiles(signal_series: pd.Series, percentiles=CALCULATE_PERCENTILES) -> pd.DataFrame:
    """Tính các ngưỡng giá trị tín hiệu tại các mốc percentile."""
    results = []
    # Drop NA to ensure percentile calculation is correct
    clean_signals = signal_series.dropna()
    for p in percentiles:
        threshold = np.percentile(clean_signals, p)
        results.append({
            "Percentile": p,
            "Threshold": threshold
        })
    return pd.DataFrame(results)

def calculate_np_events_tree(price_series: pd.Series, signal_series: pd.Series, percentiles: list) -> List[NPEvent]:
    """
    Tính toán các sự kiện NP theo logic mới (reqv2.md):
    - Trigger: Signal <= Percentile AND Price < Prev Price
    - Structure: Tree (Cha-Con)
    - Output: Danh sách phẳng các sự kiện (có link ID)
    """
    # 1. Align Data
    common_idx = price_series.index.intersection(signal_series.index)
    if len(common_idx) < 2:
        return []
        
    prices = price_series.loc[common_idx]
    signals = signal_series.loc[common_idx]
    
    # 2. Pre-calculate Thresholds
    clean_signals = signal_series.dropna()
    # Sort percentiles descending to check logic if needed, but for triggering we iterate all
    # Use a map for O(1) lookup
    threshold_map = {p: np.percentile(clean_signals, p) for p in percentiles}
    sorted_percentiles = sorted(percentiles) 

    active_events: List[NPEvent] = []
    closed_events: List[NPEvent] = []
    
    # 3. Iterate through time
    # Start from index 1 because we need prev_price
    for i in range(1, len(common_idx)):
        current_date = common_idx[i]
        current_price = prices.iloc[i]
        prev_price = prices.iloc[i-1]
        current_signal = signals.iloc[i]
        
        # A. Check Recovery for Active Events
        # Iterate backward to allow safe removal or use a new list
        still_active = []
        for event in active_events:
            event.update_price(current_date, current_price)
            
            if current_price >= event.entry_price:
                # Recovered!
                event.close(current_date, prices)
                closed_events.append(event)
            else:
                still_active.append(event)
        
        active_events = still_active
        
        # B. Check New Triggers
        # Condition 1: Price Drop
        if current_price < prev_price:
            
            # Condition 2: Signal <= Threshold
            # Priority Rule: Only trigger the LOWEST applicable percentile event (smallest p).
            
            target_p = None
            target_threshold = None
            
            # Since sorted_percentiles is ascending [1, 5, 10...], the first match is the smallest p.
            for p in sorted_percentiles:
                if current_signal <= threshold_map[p]:
                    target_p = p
                    target_threshold = threshold_map[p]
                    break # FOUND THE TIGHTEST MATCH, STOP SEARCHING
            
            if target_p is not None:
                p = target_p
                t = target_threshold
                
                # Check if an event for this percentile is already active
                is_already_active = False
                for event in active_events:
                    if event.percentile == p:
                        is_already_active = True
                        break
                
                if not is_already_active:
                    # CREATE NEW EVENT
                    
                    # Find Parent (Upline)
                    # Parent is an ACTIVE event with entry_price > current_price
                    # If multiple, pick the one with smallest entry_price (closest container)
                    # Also, parent must strictly be active (not closed this step).
                    
                    potential_parents = [e for e in active_events if e.entry_price > current_price]
                    parent = None
                    if potential_parents:
                        # Sort by entry_price ascending (closest to current)
                        potential_parents.sort(key=lambda e: e.entry_price)
                        parent = potential_parents[0]
                    
                    new_event = NPEvent(
                        percentile=p,
                        threshold=t,
                        start_date=current_date,
                        entry_price=current_price,
                        upline_id=parent.id if parent else None
                    )
                    
                    if parent:
                        parent.children_ids.append(new_event.id)
                        
                    active_events.append(new_event)
    
    # 4. Finalize
    # Move remaining active events to result (they are Type A: Unrecovered)
    # We need to calculate their current stats (days to bottom etc) up to now
    for event in active_events:
        # Calculate stats up to end of data
        try:
            start_idx = prices.index.get_loc(event.start_date)
            min_idx = prices.index.get_loc(event.min_date)
            event.days_to_bottom = min_idx - start_idx
        except:
             event.days_to_bottom = (event.min_date - event.start_date).days
             
        closed_events.append(event)
        
    # 5. Calculate P-Coverage (Total Descendants)
    event_map = {e.id: e for e in closed_events}
    
    # Memoization for performance
    memo_coverage = {}

    def get_coverage(e_id):
        if e_id in memo_coverage:
            return memo_coverage[e_id]
        
        if e_id not in event_map:
            return 0
            
        event = event_map[e_id]
        count = len(event.children_ids)
        for child_id in event.children_ids:
            count += get_coverage(child_id)
        
        memo_coverage[e_id] = count
        return count

    for event in closed_events:
        event.p_coverage = get_coverage(event.id)

    return closed_events


def _find_event_indices(prices: np.ndarray, signals: np.ndarray, threshold: float) -> list:
    """
    Helper function: Tìm kiếm các sự kiện drawdown sử dụng Numpy operations để tối ưu tốc độ.
    Trả về list các dict chứa thông tin index của sự kiện.
    """
    # Find all potential start indices where signal <= threshold
    is_in_zone = signals <= threshold
    if not np.any(is_in_zone):
        return []
    
    # Get all indices where condition is met
    zone_indices = np.flatnonzero(is_in_zone)
    
    events_indices = []
    n = len(prices)
    next_available_idx = 0
    
    for start_idx in zone_indices:
        if start_idx < next_available_idx:
            continue
            
        entry_price = prices[start_idx]
        
        # Slice for future prices (from start_idx + 1)
        future_prices = prices[start_idx+1:]
        
        # 1. Find recovery: first index where price >= entry_price
        recovery_mask = future_prices >= entry_price
        
        recovery_idx = -1 # Not recovered
        cutoff_idx = n - 1 # Default to end of data
        status = "Chưa phục hồi"
        
        if np.any(recovery_mask):
            # relative index in future_prices
            rel_recovery_idx = np.argmax(recovery_mask) 
            recovery_idx = (start_idx + 1) + rel_recovery_idx
            status = "Đã phục hồi"
            cutoff_idx = recovery_idx
            next_available_idx = recovery_idx + 1
        else:
            # Not recovered, event goes until end
            next_available_idx = n
            
        # 2. Determine active zone status
        future_signals = signals[start_idx+1:]
        exit_zone_mask = future_signals > threshold
        
        is_active_zone = False
        zone_end_idx = n - 1
        days_in_zone_raw = 0
        
        if np.any(exit_zone_mask):
            rel_exit_idx = np.argmax(exit_zone_mask)
            zone_end_idx = (start_idx + 1) + rel_exit_idx
            # Logic cũ: days_in_zone = end - start
            days_in_zone_raw = zone_end_idx - start_idx
        else:
            # Never exits zone
            if n > 0 and signals[-1] <= threshold:
                is_active_zone = True
            # Logic cũ: days_in_zone = end - start + 1 if not exit
            days_in_zone_raw = zone_end_idx - start_idx + 1
                
        events_indices.append({
            'start_idx': start_idx,
            'recovery_idx': recovery_idx,
            'cutoff_idx': cutoff_idx,
            'status': status,
            'is_active_zone': is_active_zone,
            'days_in_zone_raw': days_in_zone_raw
        })
        
    return events_indices

def _compute_event_metrics(event_idx_info: dict, price_series: pd.Series, threshold: float, matched_percentile: float) -> dict:
    """
    Helper function: Tính toán các chỉ số thống kê chi tiết cho một sự kiện dựa trên index.
    """
    start_idx = event_idx_info['start_idx']
    cutoff_idx = event_idx_info['cutoff_idx']
    recovery_idx = event_idx_info['recovery_idx']
    status = event_idx_info['status']
    
    # Lấy dữ liệu thực tế từ Series để giữ index Date
    start_date = price_series.index[start_idx]
    entry_price = price_series.iloc[start_idx]
    
    # Drawdown window
    # loc slicing includes 'stop', but iloc slicing excludes 'stop'.
    # Here we use iloc: prices[start:cutoff+1] to include cutoff
    drawdown_window = price_series.iloc[start_idx : cutoff_idx + 1]
    
    min_price = drawdown_window.min()
    min_date = drawdown_window.idxmin()
    max_dd_pct = (min_price / entry_price) - 1
    
    # Calculate days (Trading days based on index difference)
    min_idx = price_series.index.get_loc(min_date)
    days_to_bottom = min_idx - start_idx
    
    final_recovery_date = None
    days_to_recover = None
    total_days = 0
    
    if status == "Đã phục hồi":
        final_recovery_date = price_series.index[recovery_idx]
        days_to_recover = recovery_idx - start_idx
        total_days = days_to_recover
    else:
        total_days = len(drawdown_window)
        
    return {
        "start_date": start_date,
        "entry_price": float(entry_price),
        "min_price": float(min_price),
        "min_date": min_date,
        "max_dd_pct": float(max_dd_pct * 100), # % format as requested
        "days_to_bottom": int(days_to_bottom),
        "recovery_date": final_recovery_date,
        "days_to_recover": int(days_to_recover) if days_to_recover is not None else None,
        "status": status,
        "is_active": bool(event_idx_info['is_active_zone']),
        "days_in_zone": int(event_idx_info['days_in_zone_raw']),
        "total_days": int(total_days),
        "threshold": float(threshold),
        "percentile": float(matched_percentile) if matched_percentile is not None else None
    }

def calculate_drawdown_events(price_series: pd.Series, signal_series: pd.Series, threshold: float) -> list:
    """
    Core Logic: Tìm tất cả các đợt sụt giảm (Drawdown Events) với một ngưỡng threshold cụ thể.
    và tính toán các số liệu cho từng đợt drawdown
    Logic:
    - Tự động map threshold sang percentile tương ứng trong CALCULATE_PERCENTILES.
    - Entry: Ngày đầu tiên signal <= threshold.
    - Recovery: Ngày giá quay lại >= Giá Entry (bất kể signal).
    - Window: Từ Entry -> Recovery (hoặc hết dữ liệu).
    """
    # Align data
    common_idx = price_series.index.intersection(signal_series.index)
    prices = price_series.loc[common_idx]
    signals = signal_series.loc[common_idx]
    
    # Determine Percentile from Threshold
    matched_percentile = None
    clean_signals = signal_series.dropna()
    percentile_map = {p: np.percentile(clean_signals, p) for p in CALCULATE_PERCENTILES}
    
    potential_ps = [p for p, val in percentile_map.items() if threshold <= val]
    if potential_ps:
        matched_percentile = min(potential_ps)

    # 1. Find Event Indices (Fast / Vectorized where possible)
    # Convert to numpy for speed
    prices_arr = prices.values
    signals_arr = signals.values
    
    event_indices_list = _find_event_indices(prices_arr, signals_arr, threshold)
    
    # 2. Compute Detailed Metrics (Slower, per event)
    events = []
    for info in event_indices_list:
        event_data = _compute_event_metrics(info, prices, threshold, matched_percentile)
        events.append(event_data)
        
    # Sắp xếp: Gần nhất lên đầu (Start Date giảm dần)
    events.sort(key=lambda x: x['start_date'], reverse=True)
        
    return events

def calculate_drawdown_statistics(price_series: pd.Series, signal_series: pd.Series, threshold: float) -> dict:
    """
    Tìm kiếm tất cả các đợt drawdown cho một threshold cụ thể
    và tính toán thống kê cho tất cả các đợt drawdown đó
    Backtest: Khi Signal <= Threshold, giá Price còn giảm thêm bao nhiêu % (Max Drawdown)?
    """
    # Align data for days_in_zone and total_days calculation
    common_idx = price_series.index.intersection(signal_series.index)
    signals = signal_series.loc[common_idx]
    
    # 1. Gọi Core Logic để lấy toàn bộ sự kiện
    events = calculate_drawdown_events(price_series, signal_series, threshold)
    
    # 2. Tính tổng hợp metrics
    if not events:
        # Check if there is any signal <= threshold to return correct days_in_zone even if no event created (rare)
        is_in_zone = signals <= threshold
        days_in_zone = is_in_zone.sum()
        total_days = len(common_idx)
        
        return {
            "threshold": threshold,
            "historical_max_drawdown": 0.0,
            "days_in_zone": days_in_zone,
            "total_days": total_days,
            "total_events": 0,
            "quick_recoveries": 0,
            "events_5y": 0 if (price_series.index[-1] - price_series.index[0]).days >= 365*5 else "NA",
            "events_10y": 0 if (price_series.index[-1] - price_series.index[0]).days >= 365*10 else "NA",
            "filtered_events_count": 0,
            "top_drawdown_percentiles": {}
        }
        
    # Tìm sự kiện có Max Drawdown tồi tệ nhất (min của số âm)
    # events trả về max_dd_pct dạng % (VD: -25.5), cần chia 100 để về dạng thập phân (-0.255)
    worst_dd_pct = min(e['max_dd_pct'] for e in events) 
    historical_max_drawdown = worst_dd_pct / 100.0

    # Tính số lần trong 5 năm, 10 năm
    last_date = price_series.index[-1]
    first_date = price_series.index[0]
    
    date_5y = last_date - pd.DateOffset(years=5)
    date_10y = last_date - pd.DateOffset(years=10)
    
    has_5y = first_date <= date_5y
    has_10y = first_date <= date_10y
    
    count_5y = 0
    count_10y = 0
    quick_recoveries = 0
    dd_values = []
    
    for e in events:
        if e['start_date'] >= date_5y:
            count_5y += 1
        if e['start_date'] >= date_10y:
            count_10y += 1
        if e.get('status') == "Đã phục hồi":
            dr = e.get('days_to_recover')
            if isinstance(dr, (int, float)) and dr <= MIN_RECOVERY_DAYS_THRESHOLD:
                quick_recoveries += 1
            else:
                dd_values.append(e.get('max_dd_pct'))
        else:
            dd_values.append(e.get('max_dd_pct'))
    
    dd_values = [v for v in dd_values if isinstance(v, (int, float))]
    filtered_events_count = len(dd_values)
    
    top_drawdown_percentiles = {}
    if filtered_events_count > 0:
        for p in DRAWDOWN_PERCENTILES_FOR_THRESHOLD:
            val_pct = float(np.percentile(dd_values, p))
            top_drawdown_percentiles[p] = val_pct / 100.0
    
    # Tổng hợp days_in_zone từ tất cả events (hoặc tính thủ công để chính xác tuyệt đối)
    is_in_zone = signals <= threshold
    days_in_zone = is_in_zone.sum()
    total_days = len(common_idx)
    
    return {
        "threshold": threshold,
        "historical_max_drawdown": historical_max_drawdown,
        "days_in_zone": days_in_zone,
        "total_days": total_days,
        "total_events": len(events),
        "quick_recoveries": quick_recoveries,
        "events_5y": count_5y if has_5y else "NA",
        "events_10y": count_10y if has_10y else "NA",
        "filtered_events_count": filtered_events_count,
        "top_drawdown_percentiles": top_drawdown_percentiles
    }

def get_detailed_current_status(price_series: pd.Series, signal_series: pd.Series) -> dict:
    """
    Trả về thông tin chi tiết về trạng thái hiện tại
    """
    current_price = price_series.iloc[-1]
    current_signal = signal_series.iloc[-1]
    
    # 1. Tính độ hiếm (Percentile Rank)
    rarity = (signal_series < current_signal).mean() * 100
    
    # 2. Xác định Reference Percentile (Vùng rủi ro hiện tại)
    percentile_df = calculate_signal_percentiles(signal_series, percentiles=CALCULATE_PERCENTILES)
    percentile_map = percentile_df.to_dict('records')
        
    active_stat = None
    percentile_map.sort(key=lambda x: x['Percentile'])
    
    for stat in percentile_map:
        if current_signal <= stat['Threshold']:
            active_stat = stat
            break
    
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
        "drawdown_from_current": None,
        "days_in_current_zone": None
    }
    
    if active_stat:
        result['ref_percentile'] = active_stat['Percentile']
        threshold = active_stat['Threshold']
        
        # 4. Gọi Core Logic để lấy dữ liệu lịch sử và hiện tại
        events = calculate_drawdown_events(price_series, signal_series, threshold)
        
        # Tính historical max drawdown từ events
        if events:
            worst_dd_pct = min(e['max_dd_pct'] for e in events)
            result['historical_max_dd_of_zone'] = worst_dd_pct / 100.0
        
        # 5. Tìm Entry Point & Status hiện tại
        # Sự kiện đang diễn ra sẽ nằm ở cuối list (vì events được sort theo thời gian)
        if events:
            latest_event = events[-1]
            
            if latest_event['is_active']:
                entry_price = latest_event['entry_price']
                entry_date = latest_event['start_date']
                
                result['entry_date'] = entry_date
                result['entry_price'] = entry_price
                result['entry_price_at_threshold'] = entry_price
                
                # Calculate Target Price based on Historical Max Drawdown
                target_price = entry_price * (1 + result['historical_max_dd_of_zone'])
                result['target_price'] = target_price
                
                # Drawdown from current to target
                if current_price > 0:
                    drawdown_from_current = (target_price / current_price) - 1
                    result['drawdown_from_current'] = drawdown_from_current
                    result['target_drawdown'] = drawdown_from_current
                
                try:
                    start_idx = price_series.index.get_loc(entry_date)
                    end_idx = len(price_series) - 1
                    result['days_in_current_zone'] = end_idx - start_idx + 1
                except Exception:
                    result['days_in_current_zone'] = (price_series.index[-1] - entry_date).days + 1
        
    return result

def get_consolidated_drawdown_analysis(price_series: pd.Series, signal_series: pd.Series, percentiles: list = DRAWDOWN_PERCENTILES, top_n: int = TOP_N_DRAWDOWN) -> list:
    """
    Tổng hợp, deduplicate và lọc danh sách drawdown từ nhiều ngưỡng percentile.
    """
    all_events = []
    for p in percentiles:
        threshold = np.percentile(signal_series.dropna(), p)
        events = calculate_drawdown_events(price_series, signal_series, threshold)
        all_events.extend(events)
        
    # 1. Deduplicate
    unique_events_map = {}
    for event in all_events:
        d = event['start_date']
        if d not in unique_events_map or event['percentile'] < unique_events_map[d]['percentile']:
            unique_events_map[d] = event
    
    # Lọc bỏ nhiễu
    cleaned_all_events = []
    last_date = price_series.index[-1]
    for event in unique_events_map.values():
        should_keep = False
        
        if event['status'] == "Chưa phục hồi":
            age_days = (last_date - event['start_date']).days
            # Giữ lại nếu thỏa mãn ngưỡng thời gian HOẶC đang là active zone (bất kể ngắn hay dài)
            if age_days > MIN_RECOVERY_DAYS_THRESHOLD or event.get('is_active', False):
                should_keep = True
        else:
            days_recover = event.get('days_to_recover')
            if isinstance(days_recover, (int, float)) and days_recover > MIN_RECOVERY_DAYS_THRESHOLD:
                should_keep = True
        
        if should_keep:
            cleaned_all_events.append(event)
    
    # 2. Tách nhóm
    must_show_events = [e for e in cleaned_all_events if e['status'] == "Chưa phục hồi" or e.get('is_active', False)]
    
    must_show_ids = {e['start_date'] for e in must_show_events}
    history_recovered = [e for e in cleaned_all_events if e['start_date'] not in must_show_ids]
    
    # 3. Sort nhóm đã phục hồi lịch sử theo mức độ giảm giá
    history_recovered.sort(key=lambda x: x['max_dd_pct']) 
    
    # 4. Lấy Top N
    top_history = history_recovered[:top_n]
    
    # 5. Kết quả cuối cùng
    final_list = must_show_events + top_history
    
    # 6. Sort theo thời gian
    final_list.sort(key=lambda x: x['start_date'], reverse=True)
    
    return final_list
