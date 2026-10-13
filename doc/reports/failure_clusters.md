# Phân tích lỗi Phase A

Người thực hiện: Nguyễn Văn Duy (2A202602729). Nhóm một thành viên.
Nguồn số đo: `artifacts/ragas_50q.json`, chạy thật lúc `2026-10-13T02:11:36.014205+00:00`.
Model sinh: gemini-3.5-flash-lite; model chấm RAGAS: openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b, sentence-transformers/all-MiniLM-L6-v2.
Phân công evaluator: Faithfulness — `openai/gpt-oss-20b`; Answer Relevancy và Context Precision — `qwen/qwen3.8-27b`; Context Recall — `openai/gpt-oss-120b`; embedding RAGAS — `sentence-transformers/all-MiniLM-L6-v2`. Các prompt chấm giữ schema/tiêu chí RAGAS nhưng bỏ ví dụ dài để phù hợp hạn mức token Groq Free.
Chế độ sinh: {'llm': 50}. Có 5/50 câu trả lời đúng chuỗi “Không tìm thấy.”; hai PDF scan ảnh không vào tập 104 đoạn vì chưa OCR.
Pipeline tìm bằng BM25 + dense trong Qdrant, rerank bằng Flashrank và mở rộng toàn văn tài liệu nguồn đã truy hồi để giữ quy định nằm qua ranh giới đoạn.

## Điểm theo nhóm

| Chỉ số | factual (20) | multi_hop (20) | adversarial (10) |
|---|---:|---:|---:|
| faithfulness | 0.896 | 0.592 | 0.650 |
| answer_relevancy | 0.866 | 0.650 | 0.654 |
| context_precision | 0.842 | 0.575 | 0.850 |
| context_recall | 1.000 | 0.721 | 0.708 |
| avg_score | 0.901 | 0.635 | 0.716 |

## Mười câu thấp nhất và hướng sửa

Các hàng dưới đây được lấy nguyên thứ tự, chỉ số thấp nhất, chẩn đoán và đề xuất từ Task 3 trong artifact; bảng này không tính lại điểm.

| Hạng | ID | Nhóm | Điểm TB | Chỉ số thấp nhất | Câu hỏi | Chẩn đoán | Hướng sửa |
|---:|---:|---|---:|---|---|---|---|
| 1 | 31 | multi_hop | 0.0000 | faithfulness | Nhân viên đi công tác trong nước, ở khách sạn 2 đêm với giá 1.500.000 VNĐ/đêm. Công ty thanh toán t… | Câu trả lời chưa được nguồn hỗ trợ, hoặc từ chối do truy hồi thiếu nguồn. | Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ. |
| 2 | 32 | multi_hop | 0.0000 | faithfulness | Nhân viên mới cấp Manager có thời hạn thử việc 90 ngày, đang trong tháng thứ 3, có BẮT BUỘC tham dự… | Câu trả lời chưa được nguồn hỗ trợ, hoặc từ chối do truy hồi thiếu nguồn. | Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ. |
| 3 | 40 | multi_hop | 0.0000 | faithfulness | Nhân viên cấp Manager có thời hạn thử việc 90 ngày, đang trong tháng thứ 3, phát hiện vi phạm bảo m… | Câu trả lời chưa được nguồn hỗ trợ, hoặc từ chối do truy hồi thiếu nguồn. | Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ. |
| 4 | 41 | adversarial | 0.0000 | faithfulness | Nhân viên được nghỉ bao nhiêu ngày phép năm? | Câu trả lời chưa được nguồn hỗ trợ, hoặc từ chối do truy hồi thiếu nguồn. | Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ. |
| 5 | 21 | multi_hop | 0.3750 | answer_relevancy | Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào? | Câu trả lời chưa giải quyết trực tiếp câu hỏi. | Đối chiếu từng ý được hỏi và sửa prompt trả lời đủ ý. |
| 6 | 46 | adversarial | 0.4375 | faithfulness | Nhân viên thử việc có được nghỉ phép năm không? | Câu trả lời chưa được nguồn hỗ trợ, hoặc từ chối do truy hồi thiếu nguồn. | Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ. |
| 7 | 33 | multi_hop | 0.4702 | faithfulness | Nhân viên Manager có thâm niên 12 năm: tổng phụ cấp hàng tháng và số ngày phép năm theo v2024 là ba… | Câu trả lời chưa được nguồn hỗ trợ, hoặc từ chối do truy hồi thiếu nguồn. | Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ. |
| 8 | 35 | multi_hop | 0.4802 | context_recall | Nhân viên Junior P1 có lương cơ bản 12 triệu vừa vào thử việc: nhận lương bao nhiêu và phụ cấp gì t… | Context chưa chứa đủ dữ kiện cần thiết. | Bổ sung đoạn/tài liệu còn thiếu rồi đo lại cùng câu hỏi. |
| 9 | 39 | multi_hop | 0.5952 | context_precision | So sánh yêu cầu mật khẩu giữa policy v1.0 và v2.0 về độ dài tối thiểu, thời hạn đổi và MFA. | Đoạn ít liên quan đang đứng trước nguồn cần dùng. | Rà rerank, phiên bản tài liệu và bộ lọc metadata. |
| 10 | 48 | adversarial | 0.5974 | faithfulness | Nhân viên thử việc có được hưởng bảo hiểm sức khỏe PVI không? | Câu trả lời chưa được nguồn hỗ trợ, hoặc từ chối do truy hồi thiếu nguồn. | Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ. |

### Đối chiếu ba trường hợp đại diện

- **ID 31 (multi_hop, faithfulness)**: Câu hỏi: Nhân viên đi công tác trong nước, ở khách sạn 2 đêm với giá 1.500.000 VNĐ/đêm. Công ty thanh toán tối đa bao nhiêu cho tiền khách sạn? Câu trả lời: Không tìm thấy. Đáp án tham chiếu: Mức tối đa thanh toán khách sạn trong nước là 1.200.000 VNĐ/đêm. Cho 2 đêm: tối đa 2 × 1.200.000 = 2.400.000 VNĐ. Phần vượt (300.000 VNĐ/đêm) nhân viên tự chi trả. Nguồn context: Trích từ tài liệu bao_hiem_suc_khoe.md; Trích từ tài liệu hoan_chi_dao_tao.md; Trích từ tài liệu dao_tao_noi_bo.md. Nguồn chứa quy định là `cong_tac_phi.md` nhưng không xuất hiện trong ba context; đây trước hết là lỗi truy hồi/rerank khiến model phải từ chối, không phải bằng chứng model bịa nội dung. Điểm faithfulness=0.000; hướng sửa: Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ.
- **ID 32 (multi_hop, faithfulness)**: Câu hỏi: Nhân viên mới cấp Manager có thời hạn thử việc 90 ngày, đang trong tháng thứ 3, có BẮT BUỘC tham dự buổi đào tạo nội bộ của phòng ban không? Tại sao? Câu trả lời: Không tìm thấy. Đáp án tham chiếu: Có, BẮT BUỘC. Theo chính sách đào tạo nội bộ, nhân viên mới trong 6 tháng đầu phải tham gia tất cả các buổi đào tạo của phòng ban. Nhân viên tháng thứ 3 (đang thử việc) vẫn nằm trong phạm vi 6 tháng đầu. Nguồn context: Trích từ tài liệu thu_viec.md; Trích từ tài liệu phu_cap.md; Trích từ tài liệu bang_luong_2024.md. Nguồn chứa quy định là `dao_tao_noi_bo.md` nhưng không xuất hiện trong ba context; đây trước hết là lỗi truy hồi/rerank khiến model phải từ chối, không phải bằng chứng model bịa nội dung. Điểm faithfulness=0.000; hướng sửa: Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ.
- **ID 40 (multi_hop, faithfulness)**: Câu hỏi: Nhân viên cấp Manager có thời hạn thử việc 90 ngày, đang trong tháng thứ 3, phát hiện vi phạm bảo mật. Họ nên và không nên làm gì theo chính sách? Câu trả lời: Không tìm thấy. Đáp án tham chiếu: NÊN: báo cáo ngay trong vòng 1 giờ qua helpdesk@cty.vn hoặc hotline CNTT (ext. 9999). KHÔNG được: tự xử lý malware, xóa dấu vết, hoặc chia sẻ thông tin sự cố rộng rãi. Không báo cáo hoặc tự xử lý = vi phạm nghiêm trọng, có thể bị kỷ luật. Nguồn context: Trích từ tài liệu thu_viec.md; Trích từ tài liệu phu_cap.md; Trích từ tài liệu bang_luong_2024.md. Nguồn chứa quy định là `bao_mat_su_co.md` nhưng không xuất hiện trong ba context; đây trước hết là lỗi truy hồi/rerank khiến model phải từ chối, không phải bằng chứng model bịa nội dung. Điểm faithfulness=0.000; hướng sửa: Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ.

## Ma trận và nhóm yếu

Mỗi câu được đếm một lần theo chỉ số thấp nhất, không coi toàn bộ 50 câu là lỗi.

| Chỉ số thấp nhất | factual | multi_hop | adversarial | Tổng |
|---|---:|---:|---:|---:|
| faithfulness | 2 | 9 | 5 | 16 |
| context_recall | 0 | 3 | 2 | 5 |
| context_precision | 5 | 4 | 1 | 10 |
| answer_relevancy | 13 | 4 | 2 | 19 |

Nhóm yếu nhất theo điểm trung bình là **multi_hop** (0.635). Chỉ số thấp nhất xuất hiện nhiều nhất là **answer_relevancy** (19/50).

## Bẫy adversarial và giới hạn

Adversarial đạt 0.716 so với factual 0.901 và multi_hop 0.635. So sánh này chỉ phản ánh tập 10 câu adversarial, không chứng minh pipeline đã nhận ra mọi bẫy phiên bản hay phủ định.
Trong bộ đo này, các câu từ chối thiếu căn cứ nhận điểm thấp; cách một evaluator chấm câu từ chối có thể khác nhau, nên phải đọc cùng answer_relevancy, context_precision và context_recall. Không dùng faithfulness riêng lẻ để kết luận chất lượng.
Ưu tiên tiếp theo: truy hồi nhiều nguồn hơn cho câu nhiều bước, kiểm tra phiên bản chính sách hiện hành, OCR hai PDF scan ảnh, rồi chạy lại cùng 50 câu và so từng ID với điểm trước khi kết luận cải thiện.
