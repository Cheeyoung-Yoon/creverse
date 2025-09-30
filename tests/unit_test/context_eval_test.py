import sys
import os
import pytest

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator, run_structure_chain


@pytest.mark.asyncio
async def test_structure_chain_basic_flow():
    # 실제 Azure 호출 필요
    if not (os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_DEPLOYMENT")):
        pytest.skip("Azure OpenAI credentials not configured; skipping context eval test.")
    evaluator = StructureEvaluator()

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

    # 실제 호출에서는 내부 메시지 접근이 불가하므로 구조만 검증


@pytest.mark.asyncio
async def test_structure_chain_with_level():
    """레벨 지정 시에도 정상 동작하는지 테스트"""
    if not (os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_DEPLOYMENT")):
        pytest.skip("Azure OpenAI credentials not configured; skipping context eval test.")
    evaluator = StructureEvaluator()
    result = await evaluator.run_structure_chain(intro="I", body="B", conclusion="C", level="Advanced")
    assert result["evaluation_type"] == "structure_chain"
