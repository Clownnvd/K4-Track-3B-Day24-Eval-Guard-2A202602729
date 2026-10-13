from __future__ import annotations

"""Phase A: RAGAS Production Evaluation — 50q, 3 distributions, cluster analysis."""

import json
import os
import sys
from dataclasses import asdict, dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH, ANSWERS_PATH, ARTIFACTS_DIR
from src.experiment_support import write_json

Distribution = str  # "factual" | "multi_hop" | "adversarial"

DIAGNOSTIC_TREE = {
    "faithfulness":      ("Câu trả lời chưa được nguồn hỗ trợ, hoặc từ chối do truy hồi thiếu nguồn.", "Đối chiếu context với đáp án chuẩn; sửa truy hồi nếu thiếu nguồn, sửa prompt sinh nếu nguồn đã đủ."),
    "context_recall":    ("Context chưa chứa đủ dữ kiện cần thiết.", "Bổ sung đoạn/tài liệu còn thiếu rồi đo lại cùng câu hỏi."),
    "context_precision": ("Đoạn ít liên quan đang đứng trước nguồn cần dùng.", "Rà rerank, phiên bản tài liệu và bộ lọc metadata."),
    "answer_relevancy":  ("Câu trả lời chưa giải quyết trực tiếp câu hỏi.", "Đối chiếu từng ý được hỏi và sửa prompt trả lời đủ ý."),
}


@dataclass
class RagasResult:
    question_id: int
    distribution: Distribution
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float

    @property
    def avg_score(self) -> float:
        return (self.faithfulness + self.answer_relevancy +
                self.context_precision + self.context_recall) / 4

    @property
    def worst_metric(self) -> str:
        scores = {
            "faithfulness":      self.faithfulness,
            "answer_relevancy":  self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall":    self.context_recall,
        }
        return min(scores, key=scores.get)


# ─── Đã implement sẵn ────────────────────────────────────────────────────────

@dataclass
class RagasEvaluation:
    """Task 2 output: measured rows plus model identifiers reported by m4."""
    results: list[RagasResult]
    evaluator_models: list[str]

def load_test_set_50q(path: str = TEST_SET_PATH) -> list[dict]:
    """Load 50q test set với 3 distributions."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_answers(path: str = ANSWERS_PATH) -> list[dict]:
    """Load pre-generated answers từ setup_answers.py."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"answers_50q.json không tìm thấy tại {path}\n"
            "→ Chạy trước: python scripts/setup_answers.py --live"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_phase_a_report(results: list[RagasResult], clusters: dict, bottom: list[dict]) -> dict:
    """Provided exporter: preserve the student-produced Task 3 rows verbatim."""
    per_dist: dict[str, dict] = {}
    for dist in ["factual", "multi_hop", "adversarial"]:
        subset = [r for r in results if r.distribution == dist]
        if subset:
            per_dist[dist] = {
                "count": len(subset),
                "faithfulness":      sum(r.faithfulness for r in subset) / len(subset),
                "answer_relevancy":  sum(r.answer_relevancy for r in subset) / len(subset),
                "context_precision": sum(r.context_precision for r in subset) / len(subset),
                "context_recall":    sum(r.context_recall for r in subset) / len(subset),
                "avg_score":         sum(r.avg_score for r in subset) / len(subset),
            }

    report = {
        "total_questions": len(results),
        "per_question": [asdict(r) for r in results],
        "per_distribution": per_dist,
        "failure_clusters": clusters,
        "bottom_10": bottom,
    }
    return report


def save_phase_a_report(results: list[RagasResult], clusters: dict, bottom: list[dict],
                        path: str = os.path.join(ARTIFACTS_DIR, "ragas_50q.json")) -> None:
    write_json(path, build_phase_a_report(results, clusters, bottom))



# ─── Tasks 1-4: Sinh viên implement ──────────────────────────────────────────

def group_by_distribution(test_set: list[dict]) -> dict[str, list[dict]]:
    """Group supplied questions without changing their contents or order."""
    groups = {name: [] for name in ("factual", "multi_hop", "adversarial")}
    for item in test_set:
        distribution = item["distribution"]
        if distribution not in groups:
            raise ValueError(f"Unknown distribution: {distribution}")
        groups[distribution].append(item)
    return groups


def run_ragas_50q(answers: list[dict]) -> RagasEvaluation:
    """Adapt the actual m4 output; do not substitute judge-model metadata."""
    import math
    from src.m4_eval import evaluate_ragas

    if len(answers) != 50:
        raise ValueError(f"Expected 50 answers, got {len(answers)}")
    raw = evaluate_ragas(
        [item["question"] for item in answers],
        [item["answer"] for item in answers],
        [item["contexts"] for item in answers],
        [item["ground_truth"] for item in answers],
    )
    measured = raw.get("per_question", [])
    models = raw.get("metadata", {}).get("evaluator_models", [])
    if len(measured) != len(answers) or not isinstance(models, list) or not models:
        raise ValueError("m4 must return 50 measured rows and its actual evaluator_models")

    def score(row, name: str) -> float:
        value = row[name] if isinstance(row, dict) else getattr(row, name)
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 1:
            raise ValueError(f"Invalid measured {name}: {value!r}")
        return number

    results = [
        RagasResult(
            question_id=item["id"], distribution=item["distribution"],
            question=item["question"], answer=item["answer"],
            contexts=list(item["contexts"]), ground_truth=item["ground_truth"],
            faithfulness=score(row, "faithfulness"),
            answer_relevancy=score(row, "answer_relevancy"),
            context_precision=score(row, "context_precision"),
            context_recall=score(row, "context_recall"),
        )
        for item, row in zip(answers, measured)
    ]
    return RagasEvaluation(results, models)


def bottom_10(results: list[RagasResult]) -> list[dict]:
    """Keep the ten weakest measured rows and actionable diagnoses."""
    rows = []
    for rank, result in enumerate(sorted(results, key=lambda row: (row.avg_score, row.question_id))[:10], 1):
        diagnosis, suggested_fix = DIAGNOSTIC_TREE[result.worst_metric]
        rows.append({
            "rank": rank, "question_id": result.question_id,
            "distribution": result.distribution, "question": result.question,
            "avg_score": round(result.avg_score, 4),
            "worst_metric": result.worst_metric,
            "diagnosis": diagnosis, "suggested_fix": suggested_fix,
        })
    return rows


def cluster_analysis(results: list[RagasResult]) -> dict:
    """Count every worst metric; choose weakest distribution by mean quality."""
    distributions = ("factual", "multi_hop", "adversarial")
    matrix = {metric: {name: 0 for name in distributions} for metric in DIAGNOSTIC_TREE}
    totals = {name: [] for name in distributions}
    for result in results:
        if result.distribution not in totals:
            raise ValueError(f"Unknown distribution: {result.distribution}")
        matrix[result.worst_metric][result.distribution] += 1
        totals[result.distribution].append(result.avg_score)
    means = {name: sum(values) / len(values) for name, values in totals.items() if values}
    weakest = min(means, key=means.get) if means else None
    dominant_metric = max(matrix, key=lambda metric: sum(matrix[metric].values())) if results else None
    insight = (
        f"Nhóm {weakest} có điểm trung bình thấp nhất ({means[weakest]:.3f}); "
        f"{dominant_metric} là chỉ số thấp nhất xuất hiện nhiều nhất. "
        f"Cần thử: {DIAGNOSTIC_TREE[dominant_metric][1]}."
        if weakest and dominant_metric else "Chưa có kết quả đo để phân tích cụm lỗi."
    )
    return {
        "matrix": matrix, "distribution_avg_scores": means,
        "dominant_failure_distribution": weakest,
        "dominant_failure_metric": dominant_metric, "insight": insight,
    }


if __name__ == "__main__":
    from scripts.run_experiments import main
    raise SystemExit(main(["--phase", "a", *sys.argv[1:]]))
