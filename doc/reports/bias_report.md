# Đánh giá LLM Judge — Phase B

Người thực hiện: Nguyễn Văn Duy (2A202602729). Nhóm một thành viên.
Nguồn: `artifacts/judge_results.json`, chạy thật lúc `2026-10-12T17:24:55.207943+00:00`.
Model sinh câu trả lời: gemini-3.5-flash-lite; model chấm: gemini-3.5-flash-lite.

## Năm cặp A/B và phép đảo vị trí

A lấy từ `artifacts/answers_50q.json:answer`; B lấy từ `fixtures/human_labels_10q.json:model_answer`; reference là `fixtures/test_set_50q.json:ground_truth`. Cả hai lượt nhận cùng question/reference, lượt thứ hai đổi chỗ A và B rồi quy kết quả về thứ tự gốc.

| ID | A (trích) | B (trích) | Lượt 1 | Lượt 2 đã quy đổi | Kết quả | Điểm lượt 1 A/B | Điểm lượt 2 A/B |
|---|---|---|---|---|---|---|---|
| 1 | 3 ngày làm việc | Nhân viên được nghỉ 3 ngày làm việc có lương khi kết hôn. | B | B | B | 0.70/1.00 | 0.70/1.00 |
| 5 | Tổng Giám đốc (CEO) | Cần Giám đốc phòng ban phê duyệt. | A | A | A | 1.00/0.00 | 1.00/0.00 |
| 12 | Thưởng Tết tối thiểu cho nhân viên chính thức có từ 6 tháng trở lên là **1 tháng lương**. | Nhân viên được thưởng Tết tối thiểu 1 tháng lương. | A | A | A | 1.00/0.70 | 1.00/0.80 |
| 21 | Theo tài liệu chính sách nghỉ phép năm (Phiên bản 2024), nhân viên có thâm niên từ 3 năm … | Được nghỉ 18 ngày phép (15 cơ bản + 3 thâm niên). Lương Senior từ 20 đến 35 triệu. | B | B | B | 0.50/1.00 | 0.40/1.00 |
| 41 | Không tìm thấy. | Nhân viên được nghỉ 12 ngày phép năm. | B | A | tie | 0.00/0.20 | 0.50/0.00 |

Có 1/5 cặp thay đổi quyết định khi đảo vị trí (20%). Câu trả lời dài hơn thắng 2/4 ca có người thắng rõ (50%). Đây chỉ là tín hiệu từ mẫu rất nhỏ, không chứng minh nguyên nhân là vị trí hay độ dài.

ID 1 nhất quán chọn B: A chỉ nêu ba ngày, còn B nói rõ đây là ngày làm việc có lương. ID 5 nhất quán chọn A (Tổng Giám đốc); B chỉ nêu Giám đốc phòng ban nên sai ngưỡng trên 50 triệu. ID 12 nhất quán chọn A vì nêu điều kiện thâm niên sáu tháng của thưởng Tết. ID 21 nhất quán chọn B do câu hỏi cần cả phép năm và khung lương. ID 41 liên quan bẫy chính sách nghỉ phép phiên bản cũ/mới; lượt một chọn B, lượt hai chọn A, nên kết quả cuối là hòa và cần kiểm chứng lại nguồn. Lý do nguyên văn của judge nằm trong JSON.

## Calibration theo đúng `model_answer`

Helper nhận question, `model_answer` gốc và ground_truth; nhãn và ghi chú của người không được đưa vào prompt. Nhãn người chỉ được đọc để so sánh sau khi có đủ 10 kết quả judge.

| ID | `model_answer` (trích) | Judge | Người | Khớp | Lý do judge (trích) |
|---|---|---:|---:|---|---|
| 1 | Nhân viên được nghỉ 3 ngày làm việc có lương khi kết hôn. | 1 | 1 | Có | Câu trả lời đã nêu đúng số ngày nghỉ (3 ngày làm việc có lương khi kết hôn) theo reference, mặc dù thiếu chi tiết 'khôn… |
| 5 | Cần Giám đốc phòng ban phê duyệt. | 0 | 0 | Có | Thiết bị trị giá 55 triệu (trên 50 triệu) theo reference cần Tổng Giám đốc (CEO) phê duyệt, nhưng answer lại trả lời là… |
| 12 | Nhân viên được thưởng Tết tối thiểu 1 tháng lương. | 1 | 1 | Có | Answer trả lời chính xác và đầy đủ ý thiết yếu theo reference, đúng mức thưởng Tết tối thiểu 1 tháng lương cho nhân viê… |
| 21 | Được nghỉ 18 ngày phép (15 cơ bản + 3 thâm niên). Lương Senior từ 20 đến 35 tri… | 1 | 1 | Có | Câu trả lời đáp ứng chính xác số ngày phép (18 ngày) và khoảng lương (20 đến 35 triệu) dựa trên reference, sử dụng đúng… |
| 23 | Hoàn trả 25 triệu vì chưa đủ 1 năm cam kết. | 1 | 1 | Có | Câu trả lời đã chính xác theo reference, trả lời đúng số tiền phải hoàn trả (25 triệu) và lý do nghỉ sau 8 tháng là chư… |
| 29 | Trưởng phòng phê duyệt. Phạt 2% tháng trên 8 triệu. | 0 | 0 | Có | Thiếu người phê duyệt là Kế toán trưởng và tính sai phí phạt (trong reference là 15 ngày quá hạn nhưng câu hỏi giả định… |
| 33 | Phép: 19 ngày. Phụ cấp: 1.500.000 VNĐ/tháng. | 1 | 1 | Có | Câu trả lời đã nêu chính xác tổng số ngày phép là 19 ngày và tổng phụ cấp hàng tháng là 1.500.000 VNĐ, hoàn toàn khớp v… |
| 41 | Nhân viên được nghỉ 12 ngày phép năm. | 0 | 0 | Có | Câu trả lời sử dụng thông tin từ chính sách v2023 cũ (12 ngày) thay vì chính sách v2024 hiện hành (15 ngày cơ bản) theo… |
| 46 | Nhân viên thử việc không được nghỉ phép năm và phải xin nghỉ không lương nếu cầ… | 1 | 1 | Có | Câu trả lời hoàn toàn chính xác theo reference, nêu đúng việc nhân viên thử việc không được nghỉ phép năm và phải xin n… |
| 50 | Được, miễn là đảm bảo kết nối an toàn. | 0 | 0 | Có | Reference cấm sử dụng VPN cá nhân, trong khi answer lại cho phép. |

Observed agreement = 10/10 = 1,00. Human có 6 nhãn 1 và 4 nhãn 0; judge cũng vậy, nên chance agreement = (6×6 + 4×4)/100 = 0,52. Cohen’s κ = (1,00 − 0,52)/(1 − 0,52) = **1.00**.

## Giới hạn và cách dùng

Chỉ có 5 cặp và 10 nhãn, vì vậy κ = 1,00 chưa chứng minh judge đáng tin trên tập mới. Đặc biệt ID 41 có bẫy phiên bản chính sách và cặp A/B không ổn định; khi dùng thực tế cần review những ca đảo vị trí bất đồng, lưu trích dẫn cùng phiên bản tài liệu, rồi đánh giá trên mẫu đa dạng hơn.
