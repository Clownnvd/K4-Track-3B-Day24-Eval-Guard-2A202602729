from __future__ import annotations

"""Phase C: Production Guardrails — Presidio PII + NeMo Guardrails + P95 Latency."""

import asyncio
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ADVERSARIAL_SET_PATH, GUARDRAILS_CONFIG_DIR, LATENCY_BUDGET_P95_MS, OPENAI_API_KEY, PRESIDIO_LANGUAGE

_LAST_NEMO_CALL_AT = 0.0


async def _generate_with_quota(rails, **kwargs):
    """Respect Gemini free-tier throughput; retry an explicit 429."""
    global _LAST_NEMO_CALL_AT
    gemini_endpoint = "generativelanguage.googleapis.com" in (
        os.getenv("OPENAI_API_BASE", "") + os.getenv("OPENAI_BASE_URL", ""))
    interval = float(os.getenv("GEMINI_GUARD_MIN_INTERVAL_SECONDS", "4.5")) if OPENAI_API_KEY and gemini_endpoint else 0.0
    for attempt in range(4):
        wait = interval - (time.monotonic() - _LAST_NEMO_CALL_AT)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            result = await rails.generate_async(**kwargs)
            _LAST_NEMO_CALL_AT = time.monotonic()
            return result
        except Exception as error:
            if attempt == 3 or not ("429" in str(error) or "RESOURCE_EXHAUSTED" in str(error)):
                raise
            await asyncio.sleep(max(60.0, interval))


# ─── Task 9a: Presidio PII Detection ─────────────────────────────────────────

def setup_presidio():
    """Khởi tạo Presidio engine với custom Vietnamese PII recognizers. (Đã implement sẵn)

    Custom recognizers thêm vào:
        VN_CCCD  — số CCCD 12 chữ số hoặc CMND 9 chữ số
        VN_PHONE — số điện thoại Việt Nam (0[3-9]xxxxxxxx)

    Các recognizers mặc định đã có sẵn: EMAIL, PHONE_NUMBER (international), ...
    """
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, Pattern, PatternRecognizer
    from presidio_anonymizer import AnonymizerEngine

    cccd_recognizer = PatternRecognizer(
        supported_entity="VN_CCCD",
        patterns=[
            Pattern("CCCD 12 digits", r"\b\d{12}\b", 0.9),
            Pattern("CMND 9 digits",  r"\b\d{9}\b",  0.7),
        ],
    )
    phone_recognizer = PatternRecognizer(
        supported_entity="VN_PHONE",
        patterns=[Pattern("VN mobile", r"\b0[3-9]\d{8}\b", 0.9)],
    )

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()
    registry.add_recognizer(cccd_recognizer)
    registry.add_recognizer(phone_recognizer)

    analyzer  = AnalyzerEngine(registry=registry)
    anonymizer = AnonymizerEngine()
    return analyzer, anonymizer


def pii_scan(text: str, analyzer=None, anonymizer=None) -> dict:
    """Return exact detected spans and the Presidio-anonymized text."""
    if analyzer is None or anonymizer is None:
        analyzer, anonymizer = setup_presidio()
    detected = analyzer.analyze(text=text, language=PRESIDIO_LANGUAGE)
    if not detected:
        return {"has_pii": False, "entities": [], "anonymized": text}
    entities = [
        {"type": row.entity_type, "text": text[row.start:row.end],
         "score": round(float(row.score), 3), "start": row.start, "end": row.end}
        for row in detected
    ]
    redacted = anonymizer.anonymize(text=text, analyzer_results=detected).text
    return {"has_pii": True, "entities": entities, "anonymized": redacted}


def setup_nemo_rails():
    """Build the configured Colang 1.0 input/output rails."""
    from langchain_openai import ChatOpenAI
    from nemoguardrails.llm.providers import register_llm_provider
    from nemoguardrails import LLMRails, RailsConfig
    # NeMo 0.10 chooses the legacy completions API for unknown OpenAI model
    # names. Gemini's OpenAI-compatible endpoint supports chat completions.
    register_llm_provider("gemini_openai", ChatOpenAI)
    return LLMRails(RailsConfig.from_path(GUARDRAILS_CONFIG_DIR))


def _stopped(result) -> bool:
    """Use activated-rail decisions, never refusal wording as a proxy."""
    log = getattr(result, "log", None)
    for rail in getattr(log, "activated_rails", []) or []:
        if rail.get("stop", False) if isinstance(rail, dict) else getattr(rail, "stop", False):
            return True
    return False


async def check_input_rail(text: str, rails=None) -> dict:
    """Run only NeMo input rails on the supplied user message."""
    if rails is None:
        rails = setup_nemo_rails()
    result = await _generate_with_quota(rails,
        messages=[{"role": "user", "content": text}],
        options={"rails": ["input"], "log": {"activated_rails": True}},
    )
    blocked = _stopped(result)
    response = result.response[0]["content"]
    return {"allowed": not blocked,
            "blocked_reason": "nemo_input" if blocked else None,
            "response": response}


async def check_output_rail(question: str, answer: str, rails=None) -> dict:
    """Check a supplied answer without generating a new one."""
    if rails is None:
        rails = setup_nemo_rails()
    result = await _generate_with_quota(rails,
        messages=[{"role": "user", "content": question},
                  {"role": "assistant", "content": answer}],
        options={"rails": ["output"], "log": {"activated_rails": True}},
    )
    blocked = _stopped(result)
    response = result.response[0]["content"]
    return {"safe": not blocked,
            "flagged_reason": "nemo_output" if blocked else None,
            "final_answer": response if blocked else answer}


def run_adversarial_suite(adversarial_set: list[dict], rails=None,
                           analyzer=None, anonymizer=None) -> list[dict]:
    """Run arbitrary attack/control inputs without looking at expected labels."""
    if analyzer is None or anonymizer is None:
        analyzer, anonymizer = setup_presidio()
    if rails is None:
        rails = setup_nemo_rails()

    async def collect():
        rows = []
        for item in adversarial_set:
            blocked_by = None
            if pii_scan(item["input"], analyzer, anonymizer)["has_pii"]:
                blocked_by = "presidio"
            else:
                decision = await check_input_rail(item["input"], rails)
                if not decision["allowed"]:
                    blocked_by = "nemo_input"
            actual = "blocked" if blocked_by else "allowed"
            rows.append({
                "id": item["id"], "category": item["category"],
                "input": item["input"], "expected": item["expected"],
                "actual": actual, "blocked_by": blocked_by,
                "passed": actual == item["expected"],
            })
        return rows

    return asyncio.run(collect())


def measure_p95_latency(test_inputs: list[str], n_runs: int = 20,
                         rails=None, analyzer=None, anonymizer=None) -> dict:
    """Measure both input layers in sequence, including two real warm-ups."""
    from src.experiment_support import summarize_latency

    if not test_inputs or n_runs < 20:
        raise ValueError("Need nonempty inputs and at least 20 timed samples")
    if analyzer is None or anonymizer is None:
        analyzer, anonymizer = setup_presidio()
    if rails is None:
        rails = setup_nemo_rails()

    async def measure():
        for index in range(2):
            text = test_inputs[index % len(test_inputs)]
            pii_scan(text, analyzer, anonymizer)
            await check_input_rail(text, rails)
        samples = []
        for index in range(n_runs):
            text = test_inputs[index % len(test_inputs)]
            start = time.perf_counter()
            pii_scan(text, analyzer, anonymizer)
            pii_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            await check_input_rail(text, rails)
            nemo_ms = (time.perf_counter() - start) * 1000
            samples.append({"presidio_ms": pii_ms, "nemo_input_ms": nemo_ms,
                            "input_guard_ms": pii_ms + nemo_ms})
        return samples

    return summarize_latency(asyncio.run(measure()), warmup_runs=2)


if __name__ == "__main__":
    from scripts.run_experiments import main
    raise SystemExit(main(["--phase", "c", *sys.argv[1:]]))
