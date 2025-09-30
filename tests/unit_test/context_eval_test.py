import sys
import os
import pytest

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator, run_structure_chain


class FakeLLMForContext:
    """Context evaluation용 테스트 LLM.
    AzureOpenAILLM.generate_json과 동일한 시그니처를 제공하고,
    content/usage 구조를 반환한다.
    각 호출의 messages를 기록해 체인 컨텍스트 전달을 검증한다.
    """

    def __init__(self):
        self.calls = []

    async def generate_json(self, *, messages, json_schema):
        # 호출 기록 저장
        self.calls.append({"messages": messages})

        system = messages[0]["content"]
        # system 프롬프트의 JSON 예시에서 rubric_item 추론
        if '"rubric_item": "introduction"' in system:
            item = "introduction"
        elif '"rubric_item": "body"' in system:
            item = "body"
        else:
            item = "conclusion"

        content = {
            "rubric_item": item,
            "score": 1,
            "corrections": [],
            "feedback": f"{item} feedback",
        }
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        return {"content": content, "usage": usage}


@pytest.mark.asyncio
async def test_structure_chain_basic_flow():
    client = FakeLLMForContext()
    evaluator = StructureEvaluator(client=client)

    intro_text = "Intro text"
    body_text = "Body text"
    conclusion_text = "Conclusion text"

    result = await evaluator.run_structure_chain(
        intro=intro_text, body=body_text, conclusion=conclusion_text, level="Basic"
    )

    # 최상위 키 검증
    assert set(result.keys()) == {"introduction", "body", "conclusion", "token_usage_total", "evaluation_type"}
    assert result["evaluation_type"] == "structure_chain"

    # 각 섹션 결과 구조 검증
    for section in ("introduction", "body", "conclusion"):
        sec = result[section]
        assert sec["rubric_item"] == section
        assert isinstance(sec["score"], int)
        assert isinstance(sec["corrections"], list)
        assert isinstance(sec["feedback"], str)
        assert sec["evaluation_type"] == "structure_chain"
        assert "token_usage" in sec

    # 토큰 합산 검증 (각 호출 10/5/15, 총 3회)
    total = result["token_usage_total"]
    assert total["prompt_tokens"] == 30
    assert total["completion_tokens"] == 15
    assert total["total_tokens"] == 45

    # 체인 컨텍스트 전달 검증: 두 번째/세 번째 호출의 user 메시지에 이전 섹션 피드백 포함
    assert len(client.calls) == 3
    body_call_user = client.calls[1]["messages"][1]["content"]
    concl_call_user = client.calls[2]["messages"][1]["content"]

    assert "Previous section summary" in body_call_user
    assert "introduction feedback" in body_call_user

    assert "Previous section summary" in concl_call_user
    assert "body feedback" in concl_call_user


@pytest.mark.asyncio
async def test_structure_chain_with_level():
    """레벨 지정 시에도 정상 동작하는지 테스트"""
    client = FakeLLMForContext()
    # 래퍼는 내부에서 StructureEvaluator를 생성하므로 monkeypatch로 주입이 어렵다.
    # 대신 evaluator 직접 사용 테스트가 이미 충분하므로,
    # 여기서는 단순히 호출 결과 형태만 점검하기 위해 evaluator를 직접 사용.
    evaluator = StructureEvaluator(client=client)
    result = await evaluator.run_structure_chain(intro="I", body="B", conclusion="C", level="Advanced")
    assert result["evaluation_type"] == "structure_chain"
