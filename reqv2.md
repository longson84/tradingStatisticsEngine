## Dữ liệu đầu vào

- Đường giá
- Đường signal, tương ứng với đường giá tại mỗi thời điểm
- NP percentiles array [a, b, c, d, e, f, g, h] a < b < c < d < e < f < g < h

Thông thường h<=50%

Nghĩa là, tại mỗi thời điểm, chúng ta biết giá trị của giá, và của tín hiệu.
Từ đây, chúng ta có thể tính những vùng percentile của tín hiệu. Chúng ta sẽ tập trung vào những vùng percentile thấp, tức là hiếm khi tín hiệu đạt đến, để stress test đường giá.

## NP events

Chúng ta sẽ gọi những NP events là những sự kiện khi
- Đường tín hiệu (signal) đi xuống mức percentile x nào đó. Khi đó chúng ta gọi là sự kiện NP-x với x là một giá trị nào đó trong array percentile đầu vào.
- Giá giảm so với phiên trước đó.
- Nếu đường tín hiệu đồng thời thỏa mãn nhiều mức percentile (ví dụ thỏa mãn cả 20%, 30%, 40%...) thì chỉ kích hoạt sự kiện cho mức percentile thấp nhất (nhỏ nhất) mà nó thỏa mãn.

Chúng ta sẽ phân tích cách mà đường giá vận động, đặc biệt là theo chiều đi xuống, khi sự kiện NP xảy ra.

Ngày sự kiện NP bắt đầu gọi là ngày T0.
Giá tại ngày T0 gọi là X0.
Để dễ hiểu, chúng ta sẽ xem xét sự kiện NP-e, có nghĩa là e chính là mức percentile mà sự kiện này được trigger.

Chúng ta sẽ xem xét biến động giá từ ngày T0 trở đi. Có 2 trường hợp xảy ra.

Trường hợp A: Giá chưa bao giờ phục hồi về mức X0. Chúng ta gọi đây là một sự kiện NP chưa phục hồi.
Trường hợp B: Giá phục hồi về X0 tại ngày Tn. Đây là trường hợp sự kiện NP đã phục hồi.

Lưu ý rằng: chúng ta không quan trọng tại ngày Tn, đường tín hiệu đang ở ngưỡng percentile nào. Bất kể nó ở percentile nào, sự kiện NP-e cũng đã kết thúc. 
Nếu tại ngày T_(n+1) tín hiệu đang ở trong percentile d (tín hiệu <=d và > e), thì nó sẽ trigger một event tiếp theo tính từ ngày T_(n+1), nếu như giá tại ngày T_(n+1) nhỏ hơn giá ngày Tn, tức là sự kiện NP-d.

Trong cả 2 trường hợp A và B, chúng ta tính một số chỉ số sau
- Lowest Price: giá tại đáy Xm
- Date of Lowest Price: ngày mà giá tại đáy, nếu có nhiều lần thì lấy ngày đầu tiên
- Time to Trough: Số phiên từ T0 xuống đến ngày đáy
- Date of Breakevent: ngày mà giá phục hồi về X0, tức là ngày Tn, nếu có
- Time to Breakeven: Số phiên từ T0 đến Tn (ngày phục hồi) nếu có
- MAE (%): 1 - Xm/X0 tính theo %
- P-Coverage (sẽ giải thích phía dưới) - lúc đầu là 0

Trong quá trình sự kiện NP-e chưa kết thúc, đường tín hiệu có thể tiếp tục chạm đến các mốc percentile khác (thấp hơn hoặc cao hơn)
Khi đường tín hiệu chạm đến mốc percentile khác, ví dụ d, tại ngày T1, ở giá X1, nó trigger một sự kiện NP riêng mà chúng ta sẽ thống kê những chỉ số tương tự như với sự kiện NP-e.

Và trong trường hợp này, sự kiện NP-d là một sự kiện lồng trong sự kiện NP-e. 

Nếu NP-e tiếp tục có một đợt drawdown nữa nằm trong, ví dụ NP-h, khi tín hiệu chạm xuống mốc percentile h, tại ngày T2, ở giá X2, X2 < X1 < X0, thì chúng ta tiếp tục thống kê NP-h với các chỉ số như trên.

P-Coverage của một sự kiện NP là số sự kiện NP lồng trong nó.

Lưu ý rằng, khi một sự kiện NP-x nằm lồng trong một sự kiện NP-y thì x có thể lớn hơn hoặc nhỏ hơn y, nhưng giá mà tại đó NP-y được kích hoạt sẽ luôn lớn hơn giá mà NP-x được kích hoạt (nếu không thì NP-y đã kết thúc trước khi NP-x bắt đầu). Do đó, NP-x phải luôn kết thúc trước NP-y.

Để thực hiện cấu trúc cây này, với mỗi sự kiện NP chúng ta cần 2 cột
- id: tự gắn, theo cấu trúc làm sao cho duy nhất
- upline: là id của sự kiện NP mẹ.

## Thống kê các NP-events tại các mức percentile

Khi input một percentile, ví dụ x, chúng ta sẽ tính toán những thống kê trên toàn bộ các sự kiện NP-x.

Dữ liệu đầu vào sẽ là một mức Recovery Time (RT) ví dụ 5 phiên.
Và một array bao gồm các percentile rất thấp [m, n, p, q] m < n < p < q gọi là MAE percentiles array
Lưu ý rằng MAE percentiles array này khác với NP percentiles array để tính các sự kiện NP.

Nếu một sự kiện NP kết thúc với thời gian <= RT chúng ta sẽ gọi đó là QR (quick recovery)

Các thống kê bao gồm

- N: số lượng sự kiện NP-x
- QR: số lượng sự kiện NP-x  phục hồi nhanh
- QR (%) = QR/N tính theo %
- 5 năm: số sự kiện xuất hiện trong 5 năm gần nhất
- 10 năm: số sự kiện xuất hiện trong 10 năm gần nhất
- Ngày: tổng số ngày của các sự kiện này
- MMAE (%): MAE cao nhất trong các MAE (%) của các sự kiện
- MAE (%) -m: ngưỡng percentile m của các MAE (%)
- MAE (%) - n: ngưỡng percentile n của các MAE (%)
-  MAE (%) - p: ngưỡng percentile p của các MAE (%)
-  MAE (%) - q: ngưỡng percentile q của các MAE (%)

**Lưu ý quan trọng về Quick Recovery (QR):**
- Trong bảng thống kê MAE percentiles (các cột MAE-m, MAE-n...), chúng ta **loại bỏ** các sự kiện Quick Recovery (có thời gian hồi phục <= RT). Điều này giúp các chỉ số MAE phản ánh chính xác rủi ro của các đợt sụt giảm thực sự thay vì bị nhiễu bởi các dao động ngắn hạn.
- Tuy nhiên, chỉ số MMAE (%) vẫn tính toán trên toàn bộ các sự kiện (bao gồm cả QR) để phản ánh rủi ro tối đa tuyệt đối, hoặc có thể thống nhất loại bỏ QR tùy theo nhu cầu phân tích (trong implementation hiện tại: đã loại bỏ QR khỏi danh sách tính toán phân phối MAE, MMAE cũng được lấy max từ danh sách đã lọc này).

## Bảng thể hiện thống kê các sự kiện NP tổng hợp

Với NP percentiles array [a, b, c, d, e, f, g, h] và MAE percentiles array [m, n, p, q] chúng ta sẽ thể hiện một bảng thống kê tổng hợp như sau

Các hàng là các giá trị percentiles trong array, từ nhỏ đến lớn

Các cột bao gồm
- PCT: giá trị percentile
- Tín hiệu: giá trị của tín hiệu khi đạt percentile này
- Lần: Số sự kiện NP của percentile này
- QR: Số lần phục hồi nhanh
- QR (%)
- 5 năm (QR): số sự kiện trong 5 năm gần nhất (Tổng số / Số QR)
- 10 năm (QR): số sự kiện trong 10 năm gần nhất (Tổng số / Số QR)
- Ngày: tổng số ngày đường giá nằm trong những sự kiện này 
- MMAE (%): MAE cao nhất trong các MAE (%) của các sự kiện
- MAE (%) - q: ngưỡng percentile q của các MAE (%) (Sắp xếp ngược từ cao xuống thấp)
- MAE (%) - p: ngưỡng percentile p của các MAE (%)
- MAE (%) - n: ngưỡng percentile n của các MAE (%)
- MAE (%) - m: ngưỡng percentile m của các MAE (%)


## Bảng liệt kê các sự kiện NP

Bảng này liệt kê tất cả các sự kiện NP với các percentiles trong NP percentiles array [a, b, c, d, e, f, g, h]

Thứ tự thể hiện
- Chúng ta bắt đầu từ những sự kiện NP tầng trên cùng (không có upline) từ những ngày gần đây nhất

Cấu trúc bảng (Tree View) để thể hiện sự lồng ghép của các sự kiện.
Các sự kiện Quick Recovery (QR) sẽ được ẩn đi để bảng báo cáo gọn gàng và tập trung vào các đợt sụt giảm đáng chú ý.

- Ngày bắt đầu (indent theo level, level 1 thụt vào và thêm dấu -)
- NP (Percentile)
- Giá (entry)
- Giá tại đáy
- Ngày giá ở đáy
- MAE (%)
- Số phiên đến đáy
- Ngày phục hồi
- Số phiên phục hồi (T-Hồi). Đối với sự kiện chưa phục hồi: Ghi số ngày từ đầu đến nay, tô đỏ và ghi chú (chưa phục hồi).
- P-Coverage

Lồng trong bảng này là một bảng những sự kiện NP con, theo cấu trúc thư mục cây, theo thứ tự diễn ra của chúng, và cũng với các cột như trên.


## Báo cáo tổng hợp

Làm giống như trong bảng report hiện tại, với các số liệu hiện trạng hiện tại. 
Nhưng bảng thống kê sự kiện NP nhóm theo từng percentiles và bảng liệt kê các sự kiện NP được thực hiện như trên.

Mỗi cái là một section riêng có thể đóng mở.