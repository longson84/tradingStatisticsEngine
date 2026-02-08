# Analytics Constants
# Đây là những percentiles dùng để tính toán
CALCULATE_PERCENTILES = [1, 5, 10, 15, 20, 25, 30, 40, 50]

# Đây là những percentiles để thể hiện bảng drawdown, nó phải là một rút gọn của array percentiles đã tính, không được có giá trị ngoài
DRAWDOWN_PERCENTILES = [20, 15, 10, 5, 1] 
DRAWDOWN_PERCENTILES_FOR_THRESHOLD = [5, 10, 15, 20, 25, 30]

# Thể hiện TOP bao nhiêu đợt drawdown tệ hại nhất
TOP_N_DRAWDOWN = 10

# Chỉ xem xét những đợt drawdown mà thời gian về bờ lâu hơn mức này
MIN_RECOVERY_DAYS_THRESHOLD = 5

# Visualization Constants
# Tương ứng với Top 1%, 5%, 10%
VISUALIZATION_THRESHOLDS = [0.01, 0.05, 0.10]
VISUALIZATION_COLORS = ["green", "#ffd700", "red"]

# Date/Time Formats
DATE_FORMAT_DISPLAY = '%d/%m/%y'      # dd/mm/yy (e.g. 25/12/23)



# Start Date for Historical Data
HISTORICAL_DATA_START_DATE = '1980-01-01'
