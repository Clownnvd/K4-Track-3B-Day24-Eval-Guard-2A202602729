"""Render Phase B evidence into a human-readable Vietnamese report."""
from __future__ import annotations

import json
from pathlib import Path


def short(value: object, limit: int = 90) -> str:
    text = " ".join(str(value).split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = json.loads((root / "artifacts/judge_results.json").read_text(encoding="utf-8"))
    meta = result["metadata"]
    bias = result["bias_report"]
    calibration = result["calibration"]
    details = bias["verbosity_details"]
    longer_wins = details["a_wins_a_longer"] + details["b_wins_b_longer"]
    lines = [
        "# Đánh giá LLM Judge — Phase B", "",
        "Người thực hiện: Nguyễn Văn Duy (2A202602729). Nhóm một thành viên.",
        f"Nguồn: `artifacts/judge_results.json`, chạy thật lúc `{meta['created_at']}`.",
        f"Model sinh câu trả lời: {', '.join(meta['models']['generation'])}; model chấm: {', '.join(meta['models']['judge'])}.",
        "", "## Năm cặp A/B và phép đảo vị trí", "",
        "A lấy từ `artifacts/answers_50q.json:answer`; B lấy từ `fixtures/human_labels_10q.json:model_answer`; reference là `fixtures/test_set_50q.json:ground_truth`. Cả hai lượt nhận cùng question/reference, lượt thứ hai đổi chỗ A và B rồi quy kết quả về thứ tự gốc.",
        "", "| ID | A (trích) | B (trích) | Lượt 1 | Lượt 2 đã quy đổi | Kết quả | Điểm lượt 1 A/B | Điểm lượt 2 A/B |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in result["pairwise_results"]:
        first, second = item["scores_pass1"], item["scores_pass2"]
        lines.append(
            f"| {item['question_id']} | {short(item['answer_a'])} | {short(item['answer_b'])} | "
            f"{item['winner_pass1']} | {item['winner_pass2']} | {item['final_winner']} | "
            f"{first['A']:.2f}/{first['B']:.2f} | {second['A']:.2f}/{second['B']:.2f} |"
        )
    lines += [
        "",
        f"Có {bias['position_bias_count']}/5 cặp thay đổi quyết định khi đảo vị trí ({bias['position_bias_rate']:.0%}). "
        f"Câu trả lời dài hơn thắng {longer_wins}/{details['total_decisive']} ca có người thắng rõ "
        f"({bias['verbosity_bias']:.0%}). Đây chỉ là tín hiệu từ mẫu rất nhỏ, không chứng minh nguyên nhân là vị trí hay độ dài.",
        "",
        "ID 1 nhất quán chọn B: A chỉ nêu ba ngày, còn B nói rõ đây là ngày làm việc có lương. ID 5 nhất quán chọn A (Tổng Giám đốc); B chỉ nêu Giám đốc phòng ban nên sai ngưỡng trên 50 triệu. ID 12 nhất quán chọn A vì nêu điều kiện thâm niên sáu tháng của thưởng Tết. ID 21 nhất quán chọn B do câu hỏi cần cả phép năm và khung lương. ID 41 liên quan bẫy chính sách nghỉ phép phiên bản cũ/mới; lượt một chọn B, lượt hai chọn A, nên kết quả cuối là hòa và cần kiểm chứng lại nguồn. Lý do nguyên văn của judge nằm trong JSON.",
        "", "## Calibration theo đúng `model_answer`", "",
        "Helper nhận question, `model_answer` gốc và ground_truth; nhãn và ghi chú của người không được đưa vào prompt. Nhãn người chỉ được đọc để so sánh sau khi có đủ 10 kết quả judge.",
        "", "| ID | `model_answer` (trích) | Judge | Người | Khớp | Lý do judge (trích) |",
        "|---|---|---:|---:|---|---|",
    ]
    for item, human in zip(result["binary_judgments"], calibration["human_labels"]):
        lines.append(
            f"| {item['question_id']} | {short(item['model_answer'], 80)} | {item['label']} | {human} | "
            f"{'Có' if item['label'] == human else 'Không'} | {short(item['reasoning'], 120)} |"
        )
    lines += [
        "",
        f"Observed agreement = 10/10 = 1,00. Human có 6 nhãn 1 và 4 nhãn 0; judge cũng vậy, "
        f"nên chance agreement = (6×6 + 4×4)/100 = 0,52. Cohen’s κ = (1,00 − 0,52)/(1 − 0,52) = "
        f"**{calibration['cohen_kappa']:.2f}**.",
        "", "## Giới hạn và cách dùng", "",
        "Chỉ có 5 cặp và 10 nhãn, vì vậy κ = 1,00 chưa chứng minh judge đáng tin trên tập mới. Đặc biệt ID 41 có bẫy phiên bản chính sách và cặp A/B không ổn định; khi dùng thực tế cần review những ca đảo vị trí bất đồng, lưu trích dẫn cùng phiên bản tài liệu, rồi đánh giá trên mẫu đa dạng hơn.",
    ]
    (root / "doc/reports/bias_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
