"""Student guards use injected fake engines/rails; no spaCy download or live API."""
import asyncio
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock

import pytest

from config import ADVERSARIAL_SET_PATH,CLEAN_SET_PATH
from src import phase_c_guard as phase
from src.experiment_support import read_json
from src.report_contracts import validate_input_results,validate_latency

pytestmark = pytest.mark.student


@pytest.fixture
def pii_engines():
    def analyze(*,text,language):
        rows=[]
        for kind,pattern in [("VN_CCCD",r"\b(?:\d{12}|\d{9})\b"),
                             ("VN_PHONE",r"\b0[3-9]\d{8}\b"),
                             ("EMAIL_ADDRESS",r"[\w.]+@[\w.]+")]:
            for match in re.finditer(pattern,text):
                rows.append(SimpleNamespace(entity_type=kind,start=match.start(),
                                            end=match.end(),score=.9))
        return rows
    def anonymize(*,text,analyzer_results):
        for row in sorted(analyzer_results,key=lambda r:r.start,reverse=True):
            text=text[:row.start]+"<"+row.entity_type+">"+text[row.end:]
        return SimpleNamespace(text=text)
    return SimpleNamespace(analyze=Mock(side_effect=analyze)),SimpleNamespace(anonymize=Mock(side_effect=anonymize))


@pytest.mark.parametrize("text,kind", [
    ("CCCD 034095001234.","VN_CCCD"),("CMND 012345678.","VN_CCCD"),
    ("Call 0987654321.","VN_PHONE"),("Email test@company.com","EMAIL_ADDRESS")])
def test_pii_detect_and_redact(pii_engines,text,kind):
    result=phase.pii_scan(text,*pii_engines)
    assert result["has_pii"] is True
    assert kind in [r["type"] for r in result["entities"]]
    assert result["anonymized"] != text
    pii_engines[0].analyze.assert_called_once()


def test_pii_clean(pii_engines):
    text="Policy 2024."
    result=phase.pii_scan(text,*pii_engines)
    assert result=={"has_pii":False,"entities":[],"anonymized":text}
    pii_engines[0].analyze.assert_called_once()


def test_english_ner_false_positives_do_not_block_vietnamese_policy_question(pii_engines):
    text = "Theo chính sách v2024, nhân viên có bao nhiêu ngày phép năm?"
    pii_engines[0].analyze.side_effect = None
    pii_engines[0].analyze.return_value = [
        SimpleNamespace(entity_type="PERSON", start=0, end=15, score=.85),
        SimpleNamespace(entity_type="US_DRIVER_LICENSE", start=16, end=21, score=.3),
    ]
    result = phase.pii_scan(text, *pii_engines)
    assert result == {"has_pii": False, "entities": [], "anonymized": text}
    pii_engines[1].anonymize.assert_not_called()


@pytest.mark.parametrize("blocked",[True,False])
def test_input_uses_rail_decision(blocked):
    result=SimpleNamespace(response=[{"role":"assistant","content":"policy response"}],
                           log=SimpleNamespace(activated_rails=[SimpleNamespace(stop=blocked)]))
    rails=SimpleNamespace(generate_async=AsyncMock(return_value=result))
    actual=asyncio.run(phase.check_input_rail("Xin lỗi, tôi không thể đi làm; nghỉ phép thế nào?",rails))
    assert actual["allowed"] is (not blocked)
    assert actual["response"] == "policy response"
    rails.generate_async.assert_awaited_once()
    assert rails.generate_async.call_args.kwargs["options"]["rails"] == ["input"]


@pytest.mark.parametrize("blocked",[True,False])
def test_output_checks_supplied_answer(blocked):
    response="refusal" if blocked else "answer"
    returned=SimpleNamespace(response=[{"content":response}],
                             log=SimpleNamespace(activated_rails=[SimpleNamespace(stop=blocked)]))
    rails=SimpleNamespace(generate_async=AsyncMock(return_value=returned))
    result=asyncio.run(phase.check_output_rail("question","answer",rails))
    assert result["safe"] is (not blocked)
    assert result["final_answer"]==response
    assert rails.generate_async.call_args.kwargs["messages"][-1]["content"]=="answer"
    assert rails.generate_async.call_args.kwargs["options"]["rails"]==["output"]


@pytest.fixture(scope="module")
def guard_batch():
    patch=pytest.MonkeyPatch()
    attacks,clean=read_json(ADVERSARIAL_SET_PATH),read_json(CLEAN_SET_PATH)
    clean_texts={row["input"] for row in clean}
    patch.setattr(phase,"pii_scan",Mock(side_effect=lambda text,*args: {
        "has_pii":bool(re.search(r"\b\d{9,12}\b|@",text)),"entities":[],"anonymized":text}))
    rail=AsyncMock(side_effect=lambda text,*args:{
        "allowed":text in clean_texts,"blocked_reason":None if text in clean_texts else "nemo_input",
        "response":"response"})
    patch.setattr(phase,"check_input_rail",rail)
    try:
        yield phase.run_adversarial_suite(attacks+clean,rails=object(),analyzer=object(),anonymizer=object()),attacks+clean,rail
    finally:
        patch.undo()


def test_input_suite_exact_rows(guard_batch):
    rows,source,_=guard_batch
    validate_input_results(rows,source)
    assert len(rows)==28


def test_attack_and_clean_control(guard_batch):
    rows,source,rail=guard_batch
    assert len(rows)==28 and all(row["passed"] for row in rows)
    assert sum(row["actual"]=="allowed" for row in rows)==8
    assert rail.await_count==24  # four attacks stopped at PII; 8 clean + 16 other attacks


def test_latency_real_warmup_and_sample_count(monkeypatch):
    pii=Mock(return_value={"has_pii":False,"entities":[],"anonymized":"clean"})
    nemo=AsyncMock(return_value={"allowed":True,"blocked_reason":None,"response":"clean"})
    monkeypatch.setattr(phase,"pii_scan",pii)
    monkeypatch.setattr(phase,"check_input_rail",nemo)
    monkeypatch.setattr(phase.time,"perf_counter",Mock(side_effect=[i*.002 for i in range(100)]))
    result=phase.measure_p95_latency(["clean"],n_runs=20,rails=object(),analyzer=object(),anonymizer=object())
    validate_latency(result)
    assert pii.call_count==22 and nemo.await_count==22
    assert result["input_guard_ms"]["p95"]==pytest.approx(4)
