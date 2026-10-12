"""Module 4: genuine RAGAS scores; disabled/error results are explicitly labeled."""
import json
import hashlib
import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from config import TEST_SET_PATH, ENABLE_LLM_EVAL, GEMINI_API_KEY, EVAL_MODEL

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

METRICS = ('faithfulness', 'answer_relevancy', 'context_precision', 'context_recall')


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path=TEST_SET_PATH):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def evaluate_ragas(questions, answers, contexts, ground_truths):
    if not (len(questions) == len(answers) == len(contexts) == len(ground_truths)):
        raise ValueError('Danh sách câu hỏi, câu trả lời, ngữ cảnh và đáp án chuẩn phải cùng độ dài.')
    unavailable = {**{name: 0.0 for name in METRICS}, 'per_question': [], 'status': 'disabled',
                   'judge': EVAL_MODEL, 'scores_valid': False,
                   'metadata': {'evaluator_models': []}}
    if not questions:
        return {**unavailable, 'status': 'empty'}
    if not ENABLE_LLM_EVAL or not GEMINI_API_KEY:
        return {**unavailable, 'reason': 'Chưa bật đánh giá hoặc thiếu GEMINI_API_KEY; các số 0 không phải điểm đo.'}
    try:
        import copy
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.run_config import RunConfig
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from src.judge import GeminiJudge
        from src import llm as gemini_transport
        judge = GeminiJudge()
        embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2',
                                           model_kwargs={'device': 'cpu'},
                                           encode_kwargs={'normalize_embeddings': True})
        source = {'question': questions, 'answer': answers,
                  'contexts': contexts, 'ground_truth': ground_truths}
        fingerprint = hashlib.sha256(json.dumps(
            {'source': source, 'model': EVAL_MODEL, 'embedding': 'sentence-transformers/all-MiniLM-L6-v2'},
            ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
        checkpoint = Path(__file__).resolve().parents[1] / '.cache' / 'ragas_progress.json'
        scores = [{} for _ in questions]
        if checkpoint.exists():
            saved = json.loads(checkpoint.read_text(encoding='utf-8'))
            if saved.get('fingerprint') == fingerprint and len(saved.get('scores', [])) == len(questions):
                scores = saved['scores']

        metric_templates = dict(zip(METRICS, (faithfulness, answer_relevancy,
                                             context_precision, context_recall)))
        for round_number in range(2):
            for name, template in metric_templates.items():
                pending = [index for index, row in enumerate(scores)
                           if not isinstance(row.get(name), (float, int))
                           or not math.isfinite(row[name]) or not 0 <= row[name] <= 1]
                for start in range(0, len(pending), 10 if round_number == 0 else 1):
                    indices = pending[start:start + (10 if round_number == 0 else 1)]
                    dataset = Dataset.from_dict({key: [values[index] for index in indices]
                                                 for key, values in source.items()})
                    metric = copy.deepcopy(template)
                    # Retain RAGAS AnswerRelevancy, with one generated question
                    # per answer to respect the free-tier request budget.
                    if hasattr(metric, 'strictness'):
                        metric.strictness = 1
                    result = evaluate(dataset, metrics=[metric], llm=judge,
                                      embeddings=LangchainEmbeddingsWrapper(embeddings),
                                      run_config=RunConfig(max_workers=1, timeout=120,
                                                           max_retries=1),
                                      raise_exceptions=False)
                    frame = result.to_pandas()
                    for local_index, index in enumerate(indices):
                        value = float(frame.iloc[local_index].get(name, float('nan')))
                        if math.isfinite(value) and 0 <= value <= 1:
                            scores[index][name] = value
                    checkpoint.parent.mkdir(parents=True, exist_ok=True)
                    temporary = checkpoint.with_suffix('.tmp')
                    temporary.write_text(json.dumps({'fingerprint': fingerprint,
                                                     'scores': scores}, ensure_ascii=False), encoding='utf-8')
                    temporary.replace(checkpoint)
                    if gemini_transport.DAILY_QUOTA_EXHAUSTED:
                        break
                if gemini_transport.DAILY_QUOTA_EXHAUSTED:
                    break
            if gemini_transport.DAILY_QUOTA_EXHAUSTED or all(
                all(name in row for name in METRICS) for row in scores):
                break

        items, missing = [], []
        for index, row in enumerate(scores):
            values = {}
            for name in METRICS:
                value = float(row.get(name, float('nan')))
                if not math.isfinite(value):
                    missing.append({'index': index, 'metric': name})
                values[name] = value
            items.append(EvalResult(str(questions[index]), str(answers[index]), list(contexts[index]),
                                    str(ground_truths[index]), **values))
        aggregate = {name: sum(getattr(item, name) for item in items
                               if math.isfinite(getattr(item, name))) /
                     max(1, sum(math.isfinite(getattr(item, name)) for item in items))
                     for name in METRICS}
        return {**aggregate, 'per_question': items, 'status': 'complete' if not missing else 'partial',
                 'scores_valid': not missing, 'missing_metrics': missing, 'judge': EVAL_MODEL,
                 'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2', 'ragas_version': '0.1.x',
                 'metadata': {'evaluator_models': [EVAL_MODEL, 'sentence-transformers/all-MiniLM-L6-v2']}}
    except Exception as exc:
        # Do not print transport errors containing URLs/credentials.
        return {**unavailable, 'status': 'error', 'error_type': type(exc).__name__,
                'reason': 'Đánh giá thật thất bại. Không thay bằng điểm giả hoặc điểm từ đáp án chuẩn.'}


def failure_analysis(eval_results, bottom_n=10):
    tree = {
        'faithfulness': ('Câu trả lời có nội dung không được tài liệu đỡ.', 'Siết hướng dẫn chỉ dùng bằng chứng và giữ trích dẫn.'),
        'context_recall': ('Thiếu đoạn chứa dữ kiện cần thiết.', 'Kiểm tra đoạn cha, thêm tìm kiếm từ khóa và dữ liệu còn thiếu.'),
        'context_precision': ('Đoạn không phù hợp đứng trước bằng chứng cần dùng.', 'Kiểm tra xếp hạng lại, phiên bản và bộ lọc siêu dữ liệu.'),
        'answer_relevancy': ('Câu trả lời chưa giải quyết đúng điều được hỏi.', 'Viết hướng dẫn trả lời trực tiếp và làm rõ câu hỏi nhập nhằng.'),
    }
    failures = []
    for index, item in enumerate(eval_results):
        values = {name: getattr(item, name) for name in METRICS}
        if not all(math.isfinite(value) for value in values.values()):
            failures.append({'question': item.question, 'worst_metric': 'evaluation_error', 'score': None,
                             'diagnosis': 'Một phép chấm không có kết quả hợp lệ.',
                             'suggested_fix': 'Kiểm tra quota, timeout và JSON trả về; chấm lại trước khi kết luận chất lượng.',
                             'error_tree': 'Có đủ điểm đo? -> Không -> kiểm tra tầng đánh giá', 'index': index})
            continue
        worst = min(values, key=values.get)
        diagnosis, fix = tree[worst]
        failures.append({'question': item.question, 'answer': item.answer, 'ground_truth': item.ground_truth,
                         'contexts': item.contexts, 'worst_metric': worst,
                         'score': sum(values.values())/4, 'metrics': values, 'diagnosis': diagnosis,
                         'suggested_fix': fix, 'index': index,
                         'error_tree': f'Câu trả lời đúng? -> Kiểm tra bằng chứng -> Chỉ số thấp nhất: {worst} -> {fix}'})
    failures.sort(key=lambda row: (row['score'] is not None, row['score'] if row['score'] is not None else 0, row['index']))
    return failures[:max(0, bottom_n)]


def save_report(results, failures, path='reports/ragas_report.json'):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, dict):
            return {key: finite(item) for key, item in value.items()}
        if isinstance(value, list):
            return [finite(item) for item in value]
        return value
    per_question = [asdict(item) for item in results.get('per_question', [])]
    report = {'aggregate': {key: value for key, value in results.items() if key != 'per_question'},
              'num_questions': len(per_question), 'per_question': per_question, 'failures': failures}
    target.write_text(json.dumps(finite(report), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Đã lưu báo cáo: {target}', flush=True)


if __name__ == '__main__':
    print(f'Có {len(load_test_set())} câu hỏi trong bộ kiểm thử.')
