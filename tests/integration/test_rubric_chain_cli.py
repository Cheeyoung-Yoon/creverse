import sys
import os
import json
import pytest

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import app.services.evaluation.rubric_chain.grammar_eval as ge
import app.services.evaluation.rubric_chain.context_eval as ce
from app.services.evaluation.rubric_chain import __main__ as rc_main


class FakeLLM:
    """Grammar/Structure 공용 Fake LLM.
    system 메시지의 프롬프트 내용에서 rubric_item을 추론하여
    RubricItemResult 형태의 content와 usage를 반환한다.
    """

    def __init__(self):
        self.calls = []

    async def generate_json(self, *, messages, json_schema):
        self.calls.append(messages)
        system = messages[0]["content"]

        # system 프롬프트 내부 JSON 예시에서 rubric_item 추론
        if '"rubric_item": "grammar"' in system:
            item = "grammar"
        elif '"rubric_item": "introduction"' in system:
            item = "introduction"
        elif '"rubric_item": "body"' in system:
            item = "body"
        elif '"rubric_item": "conclusion"' in system:
            item = "conclusion"
        else:
            item = "grammar"  # 보수적 기본값

        content = {
            "rubric_item": item,
            "score": 1,
            "corrections": [],
            "feedback": f"{item} feedback",
        }
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        return {"content": content, "usage": usage}


@pytest.fixture(autouse=True)
def patch_azure_llm(monkeypatch):
    """GrammarEvaluator/StructureEvaluator에서 사용하는 AzureOpenAILLM을 Fake로 교체."""
    monkeypatch.setattr(ge, "AzureOpenAILLM", lambda: FakeLLM())
    monkeypatch.setattr(ce, "AzureOpenAILLM", lambda: FakeLLM())


def _parse_stdout_json(capsys):
    out = capsys.readouterr().out
    assert out.strip(), "No output captured from CLI"
    return json.loads(out)


def test_cli_runs_with_text_and_level(capsys):
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

    # 합산 토큰 사용량 검증 (각 15씩 3회 호출)
    tot = s["token_usage_total"]
    assert tot["prompt_tokens"] == 30
    assert tot["completion_tokens"] == 15
    assert tot["total_tokens"] == 45


def test_cli_runs_with_file_input(tmp_path, capsys):
    p = tmp_path / "essay.txt"
    p.write_text("Intro. Body. Conclusion.", encoding="utf-8")

    rc = rc_main.main(["--level", "Basic", "--file", str(p)])
    assert rc == 0

    payload = _parse_stdout_json(capsys)
    assert payload["level"] == "Basic"
    assert payload["grammar"]["rubric_item"] == "grammar"
    assert payload["structure"]["introduction"]["rubric_item"] == "introduction"
