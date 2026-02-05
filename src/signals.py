import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from datetime import datetime

class SignalStrategy(ABC):
    """Lớp trừu tượng cho mọi loại tín hiệu."""
    
    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def get_additional_info(self, df: pd.DataFrame) -> dict:
        """
        Trả về thông tin bổ sung:
        - ref_date: Ngày tham chiếu
        - ref_value: Giá trị tham chiếu
        - days_since_ref: Số phiên từ ngày tham chiếu
        - days_remaining: Số ngày hiệu lực còn lại
        """
        return None

class AHR999Signal(SignalStrategy):
    def __init__(self):
        self._name = "AHR999"

    @property
    def name(self) -> str:
        return self._name

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        # Clone để không ảnh hưởng dữ liệu gốc
        data = df.copy()
        
        # Logic tính AHR999
        genesis_date = datetime(2009, 1, 3)
        days_passed = (data.index - genesis_date).days
        
        # Tránh log(0) hoặc số âm
        days_passed = np.maximum(days_passed, 1)
        
        p_est = 10**(5.84 * np.log10(days_passed) - 17.01)
        ma200 = data['Close'].rolling(window=200).mean()
        
        ahr_values = (data['Close'] / p_est) * (data['Close'] / ma200)
        return ahr_values.dropna()

class DistanceFromPeakSignal(SignalStrategy):
    def __init__(self, window_days: int = 200):
        self.window = window_days
        self._name = f"Dist_Peak_{window_days}D"

    @property
    def name(self) -> str:
        return self._name

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        # Logic: (Giá / Max N ngày) - 1
        # Lưu ý: Theo yêu cầu cũ của bạn là Max, tôi sẽ sửa lại là Max cho chuẩn
        rolling_max = df['Close'].rolling(window=self.window).max()
        signal = (df['Close'] / rolling_max) - 1
        return signal.dropna()

    def get_additional_info(self, df: pd.DataFrame) -> dict:
        """
        Với Distance from peak N ngày:
        - Ngày tham chiếu = Ngày là peak N ngày được xác lập
        - Giá trị tham chiếu = Giá trị của peak N ngày
        - Số phiên tính từ ngày tham chiếu = số phiên từ ngày tham chiếu đến nay
        - Số ngày hiệu lực còn lại = N - số phiên tính từ ngày tham chiếu
        """
        # Lấy window dữ liệu gần nhất để tìm Peak
        recent_data = df.tail(self.window)
        
        if recent_data.empty:
             return super().get_additional_info(df)
             
        peak_price = recent_data['Close'].max()
        peak_date = recent_data['Close'].idxmax()
        
        current_date = df.index[-1]
        
        # Số phiên (trading days) từ peak date đến hiện tại
        # Cần đếm số lượng bản ghi trong df nằm giữa peak_date và current_date
        days_since_ref = len(df.loc[peak_date:current_date]) - 1 # Trừ 1 vì không tính chính nó nếu muốn khoảng cách
        
        # Tuy nhiên yêu cầu là "Số phiên tính từ ngày tham chiếu", ta hiểu là khoảng cách index
        # days_remaining = window - days_since_ref
        days_remaining = self.window - days_since_ref
        
        return {
            "ref_date": peak_date.strftime('%Y-%m-%d'),
            "ref_value": f"{peak_price:,.2f} USD",
            "days_since_ref": days_since_ref,
            "days_remaining": days_remaining
        }