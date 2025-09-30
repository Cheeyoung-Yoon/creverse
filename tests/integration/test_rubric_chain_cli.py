import sys
import os
import json
import pytest

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.evaluation.rubric_chain import __main__ as rc_main


def _require_azure():
    if not (os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_DEPLOYMENT")):
        pytest.skip("Azure OpenAI credentials not configured; skipping integration test.")


def _parse_stdout_json(capsys):
    out = capsys.readouterr().out
    assert out.strip(), "No output captured from CLI"
    return json.loads(out)


def test_cli_runs_with_text_and_level(capsys):
    _require_azure()
    text = "This is a sample essay. It has multiple sentences."
    rc = rc_main.main(["--level", "Intermediate", "--text", text])
    assert rc == 0

    payload = _parse_stdout_json(capsys)
    # 최상위 키
    assert set(payload.keys()) == {"level", "grammar", "structure"}
    assert payload["level"] == "Intermediate"

    # Grammar 결과 검증
    g = payload["grammar"]
    assert g["rubric_item"] == "grammar"
    assert g["evaluation_type"] == "grammar_check"
    assert isinstance(g["score"], int)
    assert isinstance(g["corrections"], list)
    assert isinstance(g["feedback"], str)
    assert "token_usage" in g

    # Structure 결과 검증
    s = payload["structure"]
    assert s["evaluation_type"] == "structure_chain"
    for section in ("introduction", "body", "conclusion"):
        sec = s[section]
        assert sec["rubric_item"] == section
        assert isinstance(sec["score"], int)
        assert isinstance(sec["corrections"], list)
        assert isinstance(sec["feedback"], str)
        assert "token_usage" in sec

    # 합산 토큰 사용량 검증 (환경에 따라 값은 변동 가능)
    tot = s["token_usage_total"]
    assert isinstance(tot["prompt_tokens"], int)
    assert isinstance(tot["completion_tokens"], int)
    assert isinstance(tot["total_tokens"], int)


def test_cli_runs_with_file_input(tmp_path, capsys):
    _require_azure()
    p = tmp_path / "essay.txt"
    p.write_text("Intro. Body. Conclusion.", encoding="utf-8")

    rc = rc_main.main(["--level", "Basic", "--file", str(p)])
    assert rc == 0

    payload = _parse_stdout_json(capsys)
    assert payload["level"] == "Basic"
    assert payload["grammar"]["rubric_item"] == "grammar"
    assert payload["structure"]["introduction"]["rubric_item"] == "introduction"
