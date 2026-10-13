# Day 24 — trạng thái thực hiện

1. [x] Fork starter và nộp link VLearn trước hạn. Mã bài nộp `BN-261012-40847`, 22:51 ngày 12/10/2026; link repo đã được VLearn lưu.
2. [x] Chuẩn bị m1–m5 từ Day 18, môi trường và tạo 50 answers từ pipeline thật. Đủ 20/20/10; 50 lượt sinh Gemini, 3 tài liệu nguồn mỗi câu. Bản thứ hai mở rộng toàn văn tài liệu đã truy hồi để giữ quy định bị cắt qua đoạn.
3. [x] Phase A: Tasks 1–4, RAGAS thật trên 50 câu, `ragas_50q.json` đủ bốn metric hữu hạn, phân tích lỗi. Factual 0,901; multi-hop 0,635; adversarial 0,716. Ba model Groq được chia theo metric và ghi rõ trong báo cáo.
4. [x] Phase B: Tasks 5–8, judge thật, `judge_results.json`, bias report. Năm cặp hai chiều, mười nhãn, κ=1,00; một cặp bất đồng vị trí trên dữ liệu cuối.
5. [x] Phase C: Tasks 9–12, guardrails thật, `guard_results.json`, latency. Groq GPT-OSS 120B: 18/20 attacks, 8/8 clean, 4/4 output; input P95 = 5.430 ms nên chưa đạt target 500 ms. Presidio chỉ chặn đúng CCCD/CMND, số điện thoại Việt Nam và email, tránh nhận nhầm tiếng Việt thành PERSON.
6. [x] Task 13, `TEAM.md`, checker, kiểm tra bí mật, commit và push cập nhật vào repo đã nộp. Commit bằng chứng `f49358d992621a9f466eff78ae5147cfee0730aa`; checker 0 lỗi, 93 test offline đạt.

Không thay dữ liệu thực nghiệm bằng fixture/mock. Các ca kiểm thử offline được báo riêng với lần chạy API/model thật.
