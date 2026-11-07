"""Офлайн-перевірка оцінювача на відтворених (mock) відповідях. НЕ є оцінкою реального LLM."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not (ROOT / "data" / "hub.duckdb").exists(), reason="спочатку python etl/load.py")
def test_replay_pipeline(tmp_path):
    out = tmp_path / "res.jsonl"
    subprocess.run([sys.executable, str(ROOT / "text2sql" / "evaluate.py"), "--replay",
                    str(ROOT / "tests" / "fixtures" / "mock_llm_outputs.json"), "--out", str(out)],
                   check=True, capture_output=True)
    s = json.loads((tmp_path / "t2sql_summary.json").read_text())
    assert s["answerable"] == 12 and s["unsafe_prompts"] == 4
    assert s["safe_rate"] == 1.0                 # небезпечне не дійшло до БД
    assert s["guard_blocked_raw_outputs"] == 2   # DELETE і read_csv
    assert s["accuracy"] == pytest.approx(8 / 12, abs=1e-3)  # 4 навмисні помилки у mock
