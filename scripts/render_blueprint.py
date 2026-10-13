"""Render Task 13 from the three measured experiment artifacts."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    ragas = json.loads((artifacts / "ragas_50q.json").read_text(encoding="utf-8"))
    judge = json.loads((artifacts / "judge_results.json").read_text(encoding="utf-8"))
    guard = json.loads((artifacts / "guard_results.json").read_text(encoding="utf-8"))
    latency = guard["latency"]
    attacks, clean = guard["adversarial"], guard["clean"]
    output_passed = sum(row["passed"] for row in guard["output_results"])
    weakest = ragas["failure_clusters"]["dominant_failure_distribution"]
    overall = sum(row["faithfulness"] + row["answer_relevancy"] + row["context_precision"] +
                  row["context_recall"] for row in ragas["per_question"]) / (4 * ragas["total_questions"])
    failed_attacks = [row["id"] for row in attacks["results"] if not row["passed"]]
    blocked_clean = [row["id"] for row in clean["results"] if row["actual"] == "blocked"]
    failed_output = [row["id"] for row in guard["output_results"] if not row["passed"]]
    lines = [
        "# Blueprint CI/CD cho RAG và guardrails", "",
        "Người thực hiện: Nguyễn Văn Duy (2A202602729). Nhóm một thành viên.",
        "Đây là **đề xuất CI/CD**, chưa phải workflow đang chạy. Số đo lấy từ ba artifact thật trong `artifacts/`.",
        f"Thời gian chạy: RAGAS `{ragas['metadata']['created_at']}`; judge `{judge['metadata']['created_at']}`; guard `{guard['metadata']['created_at']}`.",
        f"Model generation: {', '.join(ragas['metadata']['models']['generation'])}; evaluator: {', '.join(ragas['metadata']['models']['evaluator'])}; judge: {', '.join(judge['metadata']['models']['judge'])}; guard: {', '.join(guard['metadata']['models']['guard'])}.",
        "Phân công chấm RAGAS: Faithfulness dùng GPT-OSS 20B; Answer Relevancy và Context Precision dùng Qwen 3.8 27B; Context Recall dùng GPT-OSS 120B. Prompt evaluator giữ schema và phép tính RAGAS, lược ví dụ dài để không vượt hạn mức token Groq Free. Điểm giữa các metric cần đọc theo model tương ứng, không coi là do một judge duy nhất chấm.",
        "", "## Luồng và hành động khi lỗi", "",
        "```text\nNgười dùng → Presidio (PII) → NeMo input → RAG (BM25 + dense Qdrant → Flashrank → tài liệu nguồn → Gemini) → NeMo output → câu trả lời\n```",
        "Trong phép thử, Presidio phát hiện và ẩn CCCD/CMND, số điện thoại Việt Nam và email; NeMo input kiểm tra jailbreak, vượt phạm vi và yêu cầu dữ liệu nhạy cảm. Bản triển khai đề xuất dừng request có PII không cần thiết hoặc bị NeMo chặn, chỉ gửi nội dung đã lọc tới RAG. Nếu không đủ nguồn, trả lời chưa có căn cứ và ghi loại thất bại để bổ sung tài liệu. NeMo output kiểm tra câu trả lời có sẵn trước khi trả về.",
        "API key chỉ đọc từ biến môi trường hoặc kho bí mật khi chạy; không lưu trong repo, artifact hay log. Log đề xuất chỉ giữ request ID, loại rail, phiên bản policy/model và số đo; ẩn nội dung định danh. Nếu dịch vụ guard lỗi, đề xuất fail closed cho yêu cầu cần bảo vệ dữ liệu và phát cảnh báo vận hành, không âm thầm cho qua. Đây là chính sách đề xuất, chưa phải logic request production của bài lab.",
        "", "## Kết quả tấn công, câu sạch và đầu ra", "",
        f"Attacks: **{attacks['passed']}/{attacks['total']}** đạt; ID chưa chặn: {failed_attacks or 'không có'}. "
        f"Clean controls: **{clean['passed']}/{clean['total']}** được phép; false-positive rate **{clean['false_positive_rate']:.3f}**; ID bị chặn nhầm: {blocked_clean or 'không có'}. "
        f"Output cases: **{output_passed}/{len(guard['output_results'])}** đạt; ID lỗi: {failed_output or 'không có'}.",
        "Chỉ đánh giá 20 attack, 8 clean và 4 output cố định. Kết quả này không đại diện mọi yêu cầu người dùng; khi tăng policy cần bổ sung câu sạch để phát hiện chặn nhầm.",
        "", "## Phạm vi và số đo độ trễ", "",
        f"Task 12 đo `scope={latency['scope']}`: Presidio rồi NeMo input, không short-circuit; "
        f"{latency['warmup_runs']} warm-up bị loại, {latency['n_samples']} mẫu timed; percentile `{latency['percentile_method']}`. "
        "Tổng input được tính trên từng mẫu trước khi lấy percentile, không cộng hai P95.",
        "", "| Lớp / phạm vi | P50 ms | P95 ms | P99 ms | Tình trạng |",
        "|---|---:|---:|---:|---|",
    ]
    for key, label in (("presidio_ms", "Presidio"), ("nemo_input_ms", "NeMo input"),
                       ("input_guard_ms", "Input guard tuần tự")):
        row = latency[key]
        lines.append(f"| {label} | {row['p50']:.1f} | {row['p95']:.1f} | {row['p99']:.1f} | Đã đo |")
    lines += [
        "| RAG | chưa đo | chưa đo | chưa đo | Ngoài Task 12 |",
        "| NeMo output | chưa đo | chưa đo | chưa đo | Ngoài Task 12 |",
        "| Full guard / request có dừng sớm | chưa đo | chưa đo | chưa đo | Không suy từ input guard |",
        "",
        f"Target input-layer P95 < {latency['budget_ms']} ms; đo được {latency['input_guard_ms']['p95']:.1f} ms, "
        f"`latency_budget_ok={str(latency['latency_budget_ok']).lower()}`. "
        "Thời gian NeMo còn chịu giới hạn request/phút của Groq; khoảng chờ quota được tính trong số đo vì người dùng cũng phải chờ. Cần đo thêm RAG, output rail và request toàn luồng với timestamp từng bước, ít nhất 2 warm-up và mẫu đủ cho P95 trước khi tuyên bố SLO 500 ms.",
        "", "## Cổng CI đề xuất", "",
        f"Điểm RAGAS trung bình hiện tại là **{overall:.3f}**; faithfulness toàn bộ "
        f"{sum(row['faithfulness'] for row in ragas['per_question']) / 50:.3f}; nhóm yếu nhất là "
        f"**{weakest}** ({ragas['per_distribution'][weakest]['avg_score']:.3f}). "
        f"Cohen’s κ = **{judge['calibration']['cohen_kappa']:.3f}**.",
        "Đề xuất pipeline CI chạy tests offline, xác minh schema/hash bằng `python scripts/check_lab.py`, rồi trên lịch riêng chạy batch API thật. Job trả nonzero khi faithfulness <0,75, avg_score <0,65, attacks <18/20, clean <8/8 hoặc output <4/4. Đây là ngưỡng đề xuất, không phải gate đã cài; điểm faithfulness hiện tại 0,725 sẽ **không đạt** gate đề xuất này. Bài lab chỉ yêu cầu tối thiểu attacks 15/20. Chỉ áp ngưỡng full-guard P95 <500 ms sau khi đo đúng full guard; Task 12 hiện mới đo input layers.",
        "", "## Giám sát và bước cải thiện có thể kiểm chứng", "",
        "Theo dõi theo tuần: điểm RAGAS từng distribution và top lỗi, số câu không có câu trả lời, tỉ lệ chặn attack/clean/output, P50/P95/P99 mỗi lớp, lỗi 429, phiên bản model/policy và tỉ lệ bất đồng khi đảo A/B. Lưu mẫu đã ẩn PII để review thủ công; khi false positive tăng, bổ sung control cùng loại trước khi sửa prompt. Khi tài liệu đổi phiên bản, gắn ngày hiệu lực vào index và chạy lại tập 50 câu trước khi phát hành.",
        "1. Mở rộng nguồn cho câu nhiều bước và so lại context_recall từng ID yếu trong `failure_clusters.md`.",
        "2. OCR hai PDF scan ảnh bị bỏ qua, lập chỉ mục lại, sau đó kiểm tra liệu các câu thiếu nguồn có tăng điểm recall hay không.",
        "3. Đặt bài kiểm tra riêng cho chính sách cũ/mới và phủ định; so sánh từng câu adversarial trước/sau, không chỉ nhìn điểm trung bình.",
        "4. Kiểm tra các cặp A/B bất đồng sau đảo vị trí bằng người đánh giá và tăng số mẫu calibration trước khi tin vào κ.",
        "5. Đo full request, phân biệt thời gian chờ quota với thời gian model xử lý; tối ưu hoặc đổi tầng guard khi có bằng chứng P95 vượt budget.",
    ]
    (root / "doc/reports/blueprint.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
