# Nhóm thực hiện K4 Track 3B Day 24

Tên nhóm: Nguyễn Văn Duy (bài cá nhân theo xác nhận của người nộp).

Repo nộp: https://github.com/Clownnvd/K4-Track-3B-Day24-Eval-Guard-2A202602729

Người nộp: Nguyễn Văn Duy, MSSV 2A202602729. Link repo được nộp trên VLearn lúc 22:51 ngày 12/10/2026 (mã BN-261012-40847). Commit dùng để chấm là HEAD của nhánh main trong repo trên sau khi hoàn thiện; ghi lại SHA cụ thể ở bản cập nhật cuối.

## Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò / công việc | Bằng chứng |
|---|---|---|---|---|
| 1 | Nguyễn Văn Duy | 2A202602729 | Tích hợp m1–m5, tạo 50 câu trả lời, thực hiện Phase A/B/C, phân tích kết quả và nộp bài | `src/phase_a_ragas.py`, `src/phase_b_judge.py`, `src/phase_c_guard.py`, `artifacts/`, `doc/reports/` |

## Môi trường và chuẩn bị

Máy Windows, Python 3.11 từ môi trường lab Day 18. Qdrant chạy bằng Docker tại cổng 6333. Tài liệu được chia thành 104 đoạn và lập chỉ mục BM25 + dense. Vì bộ nhớ máy giới hạn, lần chạy 50 câu sử dụng `sentence-transformers/all-MiniLM-L6-v2` cho embedding, Flashrank cho rerank; không nhận đó là BGE-M3/CrossEncoder mặc định. Hai PDF chỉ có ảnh bị bỏ qua vì chưa OCR. Nguồn dữ liệu và các giới hạn này được giữ rõ trong báo cáo.

Các bài kiểm thử offline: `python -m pytest -q` — 93 passed, 3 deselected. Đây là kiểm thử mã với mock, tách biệt với bằng chứng chạy API/model thật trong `artifacts/`.

Phase A đã chạy đủ bốn metric RAGAS trên 50 câu bằng Groq: Faithfulness dùng `openai/gpt-oss-20b`, Answer Relevancy và Context Precision dùng `qwen/qwen3.8-27b`, Context Recall dùng `openai/gpt-oss-120b`; embedding chấm là `sentence-transformers/all-MiniLM-L6-v2`. Prompt chấm giữ schema và tiêu chí RAGAS nhưng lược các ví dụ dài để phù hợp hạn mức Free. Trung bình factual 0,901; multi-hop 0,635; adversarial 0,716. Nhóm multi-hop yếu nhất. Model evaluator được ghi theo từng metric trong báo cáo; không coi đây là một judge duy nhất.

Phase C đã chạy bằng Groq `openai/gpt-oss-120b`: 18/20 tấn công bị chặn, 8/8 câu sạch được cho qua, 4/4 kiểm tra đầu ra đạt; P95 input guard 5.430 ms trên 20 mẫu sau 2 warm-up. Hai tấn công ID 11 và 14 chưa bị chặn; mốc 500 ms chưa đạt vì có thời gian chờ hạn mức API.

## INDIVIDUAL

### NguyenVanDuy-2A202602729

- Công việc: hoàn thiện Tasks 1–13, tích hợp pipeline RAG Day 18, chạy RAGAS, LLM judge, Presidio và NeMo, viết ba báo cáo và kiểm chứng bằng checker.
- Bằng chứng: các tệp nguồn trong `src/`, kết quả `artifacts/answers_50q.json`, `artifacts/ragas_50q.json`, `artifacts/judge_results.json`, `artifacts/guard_results.json` và `doc/reports/`; mỗi kết quả chỉ được gọi là đã hoàn thành khi tệp thật tồn tại và qua checker.
- Cách kiểm tra: `python -m pytest -q` cho logic offline, `python scripts/check_lab.py` cho bộ bài nộp; lệnh runner `--live` mới là phép thử model/API.
- Điều đã học: so sánh đầu ra với đáp án tham chiếu, tách chất lượng truy hồi và sinh, đảo thứ tự A/B để quan sát thiên lệch vị trí, đối chiếu nhãn bằng Cohen’s kappa và đo false positive của guardrails bằng câu sạch.
- Giới hạn: tài liệu scan thiếu OCR; bộ 50/20/8/4 mẫu nhỏ; số đo latency input không đại diện cho thời gian toàn request; chi tiết được trình bày trong báo cáo tương ứng.
- AI hỗ trợ: Codex hỗ trợ viết và rà soát mã; Gemini được dùng cho generation/judge khi chạy live. Không dùng nội dung AI tự tạo để thay thế bằng chứng thực nghiệm.

## Cập nhật sau khi nộp link

Link fork được nộp trước khi hoàn thiện mã theo yêu cầu người nộp. Các commit tiếp theo trong cùng repo bổ sung thí nghiệm và báo cáo; người đọc cần đối chiếu thời gian commit với hạn áp dụng của lớp.
