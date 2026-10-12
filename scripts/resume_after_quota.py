"""One-shot local continuation after Gemini's daily free-tier reset.

This helper never stores API keys in the repository or command line. It keeps
real experiment results separate from offline tests and stops before the lab
deadline if an external provider remains unavailable.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
WATCH = (
    "config.py", "src/m4_eval.py", "src/llm.py", "src/phase_c_guard.py",
    "guardrails/config.yml", "guardrails/rails.co", "scripts/setup_answers.py",
    "artifacts/answers_50q.json", "artifacts/judge_results.json",
)
COMMIT_FILES = (
    "doc/ENVIRONMENT.md", "doc/TEAM.md", "doc/STATUS.md",
    "src/m4_eval.py", "src/llm.py", "src/phase_c_guard.py",
    "scripts/render_blueprint.py", "scripts/render_failure_report.py",
    "scripts/resume_after_quota.py", "artifacts/ragas_50q.json",
    "artifacts/guard_results.json", "doc/reports/failure_clusters.md",
    "doc/reports/blueprint.md",
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log(message: str) -> None:
    stamp = now().isoformat(timespec="seconds")
    print(f"[{stamp}] {message}", flush=True)


def run(command: list[str], env: dict[str, str], *, timeout: int = 7200) -> int:
    log("START " + " ".join(command[:4]))
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, check=False,
                                stdout=sys.stdout, stderr=sys.stderr, timeout=timeout)
        log(f"EXIT {result.returncode}")
        return result.returncode
    except subprocess.TimeoutExpired:
        log("TIMEOUT")
        return 124


def wait_until(target: datetime) -> None:
    while now() < target:
        time.sleep(min(60, max(1, (target - now()).total_seconds())))


def check_workspace(expected_head: str, expected_files: dict[str, str]) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != expected_head:
        raise RuntimeError("Repo HEAD changed while waiting; stop to preserve newer work.")
    changed = [name for name, before in expected_files.items()
               if not (ROOT / name).exists() or digest(ROOT / name) != before]
    if changed:
        raise RuntimeError("Tracked input changed while waiting: " + ", ".join(changed))


def secret_scan() -> None:
    names = [item.decode("utf-8") for item in subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).split(b"\0") if item]
    patterns = (re.compile(rb"AIza[0-9A-Za-z_-]{25,}"),
                re.compile(rb"(?:sk-|ghp_|github_pat_)[0-9A-Za-z_-]{20,}"))
    affected = [name for name in names if any(pattern.search((ROOT / name).read_bytes())
                                           for pattern in patterns)]
    if affected:
        raise RuntimeError("Credential-like text in staged files: " + ", ".join(affected))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--venv-python", type=Path, required=True)
    parser.add_argument("--resume-at", required=True)
    parser.add_argument("--deadline", required=True)
    args = parser.parse_args()
    resume_at = datetime.fromisoformat(args.resume_at)
    deadline = datetime.fromisoformat(args.deadline)
    if resume_at.tzinfo is None or deadline.tzinfo is None:
        raise ValueError("UTC offsets are required for resume and deadline.")
    expected_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                            text=True).strip()
    expected_files = {name: digest(ROOT / name) for name in WATCH}
    log(f"Waiting for quota reset until {resume_at.isoformat()} (deadline {deadline.isoformat()})")
    wait_until(resume_at)
    check_workspace(expected_head, expected_files)
    key = dotenv_values(args.key_file).get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Gemini key missing from configured local file.")
    env = dict(os.environ)
    env.update({
        "GEMINI_API_KEY": key, "OPENAI_API_KEY": key,
        "OPENAI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "OPENAI_API_BASE": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "LLM_PROVIDER": "gemini", "LLM_MODEL": "gemini-3.5-flash-lite",
        "GENERATION_MODEL": "gemini-3.5-flash-lite",
        "JUDGE_MODEL": "gemini-3.5-flash-lite",
        "EVAL_MODEL": "gemini-3.5-flash-lite",
        "ENABLE_LLM_EVAL": "1", "GEMINI_MIN_INTERVAL_SECONDS": "5",
        "GEMINI_GUARD_MIN_INTERVAL_SECONDS": "5", "DAY24_GUARD_CHECKPOINT": "1",
        "TORCH_NUM_THREADS": "2", "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    })
    while now() < deadline and not (ROOT / "artifacts/ragas_50q.json").exists():
        code = run([str(args.venv_python), "scripts/run_experiments.py", "--phase", "a", "--live"], env)
        if code == 0:
            if run([sys.executable, "scripts/render_failure_report.py"], env, timeout=60) == 0:
                break
            return 4
        log("Phase A incomplete; cached measurements retained. Retry after 10 minutes.")
        wait_until(min(deadline, now() + timedelta(minutes=10)))

    if not (ROOT / "artifacts/ragas_50q.json").exists():
        log("STOP: Phase A did not complete before deadline.")
        return 2

    docker = ["docker", "run", "--rm", "-e", "OPENAI_API_KEY", "-e", "OPENAI_BASE_URL",
              "-e", "OPENAI_API_BASE", "-e", "GEMINI_GUARD_MIN_INTERVAL_SECONDS",
              "-e", "DAY24_GUARD_CHECKPOINT", "-v", f"{ROOT}:/app", "-v",
              "lab24-hf-cache:/root/.cache/huggingface", "-w", "/app", "lab24-guard",
              "python", "scripts/run_experiments.py", "--phase", "c", "--live",
              "--latency-samples", "20"]
    while now() < deadline and not (ROOT / "artifacts/guard_results.json").exists():
        code = run(docker, env)
        if code == 0:
            break
        log("Phase C incomplete; checkpoint retained. Retry after 10 minutes.")
        wait_until(min(deadline, now() + timedelta(minutes=10)))
    if not (ROOT / "artifacts/guard_results.json").exists():
        log("STOP: Phase C did not complete before deadline.")
        return 3

    if run([sys.executable, "scripts/render_blueprint.py"], env, timeout=60):
        return 4
    if run([sys.executable, "scripts/check_lab.py", "--with-tests"], env, timeout=300):
        log("STOP: checker failed; artifacts retained for review.")
        return 5
    if run(["git", "add", "--", *COMMIT_FILES], env, timeout=60):
        return 6
    if run(["git", "diff", "--cached", "--check"], env, timeout=60):
        return 6
    secret_scan()
    if run(["git", "commit", "-m", "feat: add live RAGAS and guardrail evidence"], env, timeout=60):
        return 7
    evidence_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                            text=True).strip()
    if run(["git", "push", "origin", "main"], env, timeout=120):
        return 8

    team_path = ROOT / "doc/TEAM.md"
    team = team_path.read_text(encoding="utf-8")
    team = re.sub(r"Commit dùng để chấm là HEAD[^\n]+", "Commit chứa đủ kết quả để chấm: `" +
                  evidence_head + "`. Bản ghi TEAM/STATUS bổ sung nằm ở commit kế tiếp.", team)
    team_path.write_text(team, encoding="utf-8")
    status_path = ROOT / "doc/STATUS.md"
    status = status_path.read_text(encoding="utf-8")
    for item in (3, 5, 6):
        status = status.replace(f"{item}. [ ]", f"{item}. [x]")
    status_path.write_text(status, encoding="utf-8")
    if run(["git", "add", "--", "doc/TEAM.md", "doc/STATUS.md"], env, timeout=60):
        return 9
    if run(["git", "commit", "-m", "docs: record final evaluation commit"], env, timeout=60):
        return 9
    if run(["git", "push", "origin", "main"], env, timeout=120):
        return 10
    log("DONE: checker passed and both commits pushed to the submitted fork.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Do not print provider exceptions that might include request details.
        log("STOP: " + type(error).__name__ + ": " + str(error)[:240])
        raise SystemExit(1)
