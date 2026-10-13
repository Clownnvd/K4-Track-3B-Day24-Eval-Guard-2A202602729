"""RAGAS list outputs must survive JSON-object-only providers."""

import json

from src.llm import normalize_ragas_json


def test_statement_decomposition_object_becomes_list():
    source = '{"sentence_index":0,"simpler_statements":["A"]}'
    assert json.loads(normalize_ragas_json(source)) == [json.loads(source)]


def test_context_precision_object_stays_object():
    source = '{"reason":"relevant","verdict":1}'
    assert json.loads(normalize_ragas_json(source)) == json.loads(source)


def test_nli_verdict_object_becomes_list():
    source = '{"statement":"A","reason":"supported","verdict":1}'
    assert json.loads(normalize_ragas_json(source)) == [json.loads(source)]


def test_context_recall_attribution_object_becomes_list():
    source = '{"statement":"A","attributed":1,"reason":"supported"}'
    assert json.loads(normalize_ragas_json(source)) == [json.loads(source)]


def test_fenced_json_list_is_unwrapped():
    source = '```json\n[{"statement":"A","attributed":1}]\n```'
    assert json.loads(normalize_ragas_json(source)) == [{"statement": "A", "attributed": 1}]
