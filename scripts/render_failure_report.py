"""Render the measured Phase A artifact without recomputing scores or diagnoses."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def cell(value: object, length: int = 110) -> str:
    result = " ".join(str(value).split()).replace("|", "\\|")
    return result if len(result) <= length else result[: length - 1] + "…"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root / "artifacts/ragas_50q.json").read_text(encoding="utf-8"))
    answers = json.loads((root / "artifacts/answers_50q.json").read_text(encoding="utf-8"))
    meta = report["metadata"]
    distribution = report["per_distribution"]
    clusters = report["failure_clusters"]
    modes = Counter(row["generation_mode"] for row in answers)
    abstentions = sum(row["answer"].strip().casefold() == "không tìm thấy." for row in answers)
    metrics = ("faithfulness", "answer_relevancy", "context_precision", "context_recall", "avg_score")
    groups = ("factual", "multi_hop", "adversarial")
    lines = [
        "# Phân tích lỗi Phase A", "",
        "Người thực hiện: Nguyễn Văn Duy (2A202602729). Nhóm một thành viên.",
        f"Nguồn số đo: `artifacts/ragas_50q.json`, chạy thật lúc `{meta['created_at']}`.",
        f"Model sinh: {', '.join(meta['models']['generation'])}; model chấm RAGAS: {', '.join(meta['models']['evaluator'])}.",
        "Phân công evaluator: Faithfulness — `openai/gpt-oss-20b`; Answer Relevancy và Context Precision — `qwen/qwen3.8-27b`; Context Recall — `openai/gpt-oss-120b`; embedding RAGAS — `sentence-transformers/all-MiniLM-L6-v2`. Các prompt chấm giữ schema/tiêu chí RAGAS nhưng bỏ ví dụ dài để phù hợp hạn mức token Groq Free.",
        f"Chế độ sinh: {dict(modes)}. Có {abstentions}/50 câu trả lời đúng chuỗi “Không tìm thấy.”; hai PDF scan ảnh không vào tập 104 đoạn vì chưa OCR.",
        "Pipeline tìm bằng BM25 + dense trong Qdrant, rerank bằng Flashrank và mở rộng toàn văn tài liệu nguồn đã truy hồi để giữ quy định nằm qua ranh giới đoạn.",
        "", "## Điểm theo nhóm", "",
        "| Chỉ số | factual (20) | multi_hop (20) | adversarial (10) |",
        "|---|---:|---:|---:|",
    ]
    for metric in metrics:
        lines.append("| " + metric + " | " + " | ".join(f"{distribution[group][metric]:.3f}" for group in groups) + " |")
    lines += [
        "", "## Mười câu thấp nhất và hướng sửa", "",
        "Các hàng dưới đây được lấy nguyên thứ tự, chỉ số thấp nhất, chẩn đoán và đề xuất từ Task 3 trong artifact; bảng này không tính lại điểm.",
        "", "| Hạng | ID | Nhóm | Điểm TB | Chỉ số thấp nhất | Câu hỏi | Chẩn đoán | Hướng sửa |",
        "|---:|---:|---|---:|---|---|---|---|",
    ]
    for row in report["bottom_10"]:
        lines.append(
            f"| {row['rank']} | {row['question_id']} | {row['distribution']} | {row['avg_score']:.4f} | "
            f"{row['worst_metric']} | {cell(row['question'], 100)} | {cell(row['diagnosis'], 120)} | "
            f"{cell(row['suggested_fix'], 120)} |"
        )
    by_id = {row["question_id"]: row for row in report["per_question"]}
    lines += ["", "### Đối chiếu ba trường hợp đại diện", ""]
    expected_sources = {31: "cong_tac_phi.md", 32: "dao_tao_noi_bo.md", 40: "bao_mat_su_co.md"}
    for bottom in report["bottom_10"][:3]:
        row = by_id[bottom["question_id"]]
        sources = [context.splitlines()[0].rstrip(".") for context in row["contexts"]]
        expected_source = expected_sources.get(row["question_id"])
        cause = (
            f"Nguồn chứa quy định là `{expected_source}` nhưng không xuất hiện trong ba context; "
            "đây trước hết là lỗi truy hồi/rerank khiến model phải từ chối, không phải bằng chứng model bịa nội dung."
            if expected_source and all(expected_source not in source for source in sources)
            else "Cần kiểm tra từng context để tách lỗi truy hồi khỏi lỗi sinh câu trả lời."
        )
        lines += [
            f"- **ID {row['question_id']} ({row['distribution']}, {bottom['worst_metric']})**: "
            f"Câu hỏi: {cell(row['question'], 200)} Câu trả lời: {cell(row['answer'], 240)} "
            f"Đáp án tham chiếu: {cell(row['ground_truth'], 240)} "
            f"Nguồn context: {'; '.join(cell(source, 80) for source in sources)}. "
            f"{cause} Điểm {bottom['worst_metric']}={row[bottom['worst_metric']]:.3f}; "
            f"hướng sửa: {cell(bottom['suggested_fix'], 150)}"
        ]
    lines += ["", "## Ma trận và nhóm yếu", "",
              "Mỗi câu được đếm một lần theo chỉ số thấp nhất, không coi toàn bộ 50 câu là lỗi.",
              "", "| Chỉ số thấp nhất | factual | multi_hop | adversarial | Tổng |",
              "|---|---:|---:|---:|---:|"]
    for metric, counts in clusters["matrix"].items():
        lines.append(f"| {metric} | {counts['factual']} | {counts['multi_hop']} | {counts['adversarial']} | {sum(counts.values())} |")
    weakest = clusters["dominant_failure_distribution"]
    dominant = clusters["dominant_failure_metric"]
    lines += [
        "",
        f"Nhóm yếu nhất theo điểm trung bình là **{weakest}** ({clusters['distribution_avg_scores'][weakest]:.3f}). "
        f"Chỉ số thấp nhất xuất hiện nhiều nhất là **{dominant}** "
        f"({sum(clusters['matrix'][dominant].values())}/50).",
        "",
        "## Bẫy adversarial và giới hạn", "",
        f"Adversarial đạt {distribution['adversarial']['avg_score']:.3f} so với factual "
        f"{distribution['factual']['avg_score']:.3f} và multi_hop {distribution['multi_hop']['avg_score']:.3f}. "
        "So sánh này chỉ phản ánh tập 10 câu adversarial, không chứng minh pipeline đã nhận ra mọi bẫy phiên bản hay phủ định.",
        "Trong bộ đo này, các câu từ chối thiếu căn cứ nhận điểm thấp; cách một evaluator chấm câu từ chối có thể khác nhau, nên phải đọc cùng answer_relevancy, context_precision và context_recall. Không dùng faithfulness riêng lẻ để kết luận chất lượng.",
        "Ưu tiên tiếp theo: truy hồi nhiều nguồn hơn cho câu nhiều bước, kiểm tra phiên bản chính sách hiện hành, OCR hai PDF scan ảnh, rồi chạy lại cùng 50 câu và so từng ID với điểm trước khi kết luận cải thiện.",
    ]
    (root / "doc/reports/failure_clusters.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
