import pytest
import json
import sys
import os
# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.evaluation.rubric_chain.grammar_eval import GrammarEvaluator
from app.models.rubric import RubricItemResult
from app.client.azure_openai import AzureOpenAILLM


class TestGrammarEvaluator:
    """GrammarEvaluator 클래스 실제 테스트 (Mock 없음)"""

    @pytest.fixture
    def evaluator(self):
        """실제 GrammarEvaluator 인스턴스"""
        return GrammarEvaluator()

    @pytest.fixture
    def sample_text_good(self):
        """문법이 좋은 영문 텍스트"""
        return "The quick brown fox jumps over the lazy dog. This sentence demonstrates perfect grammar and spelling."

    @pytest.fixture
    def sample_text_errors(self):
        """문법 오류가 있는 영문 텍스트"""
        return "Move to a higher ground First, I can save by large waves Secondly, Many people will come to high place Last, l will see what is happening on the ground.For this reason, when tsunami come l will get to high places.l hope you respect my think"

    @pytest.fixture
    def sample_text_moderate(self):
        """중간 수준의 영문 텍스트"""
        return "I think that climate change is very important issue. We should do something about it because it effect our future. Many scientist agree that we need to take action now."

    def test_get_grammar_schema(self, evaluator):
        """JSON 스키마 생성 테스트"""
        schema = evaluator._get_grammar_schema()
        
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "type" in schema
        assert schema["type"] == "object"

    @pytest.mark.asyncio
    async def test_check_grammar_good_text(self, evaluator, sample_text_good):
        """문법이 좋은 텍스트 검사 테스트"""
        result = await evaluator.check_grammar(sample_text_good)

        # 기본 구조 검증
        assert result["rubric_item"] == "grammar"
        assert result["evaluation_type"] == "grammar_check"
        assert "token_usage" in result
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 2
        assert isinstance(result["corrections"], list)
        assert isinstance(result["feedback"], str)
        
        # 토큰 사용량 검증
        assert result["token_usage"]["total_tokens"] > 0
        assert result["token_usage"]["prompt_tokens"] > 0
        assert result["token_usage"]["completion_tokens"] > 0
        
        # 좋은 텍스트는 높은 점수를 받아야 함
        assert result["score"] >= 1

    @pytest.mark.asyncio
    async def test_check_grammar_error_text(self, evaluator, sample_text_errors):
        """문법 오류가 있는 텍스트 검사 테스트"""
        result = await evaluator.check_grammar(sample_text_errors)

        # 기본 구조 검증
        assert result["rubric_item"] == "grammar"
        assert result["evaluation_type"] == "grammar_check"
        assert "token_usage" in result
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 2
        assert isinstance(result["corrections"], list)
        assert isinstance(result["feedback"], str)
        
        # 토큰 사용량 검증
        assert result["token_usage"]["total_tokens"] > 0
        
        # 오류가 있는 텍스트는 수정사항이 있어야 함
        assert len(result["corrections"]) > 0
        
        # 각 correction 항목 검증
        for correction in result["corrections"]:
            assert "original" in correction
            assert "corrected" in correction
            assert "explanation" in correction
            assert isinstance(correction["original"], str)
            assert isinstance(correction["corrected"], str)
            assert isinstance(correction["explanation"], str)

    @pytest.mark.asyncio
    async def test_check_grammar_moderate_text(self, evaluator, sample_text_moderate):
        """중간 수준의 텍스트 검사 테스트"""
        result = await evaluator.check_grammar(sample_text_moderate)

        # 기본 구조 검증
        assert result["rubric_item"] == "grammar"
        assert result["evaluation_type"] == "grammar_check"
        assert "token_usage" in result
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 2
        assert isinstance(result["corrections"], list)
        assert isinstance(result["feedback"], str)
        
        # 피드백이 의미있는 내용인지 확인
        assert len(result["feedback"]) > 10

    @pytest.mark.asyncio
    async def test_check_grammar_empty_text(self, evaluator):
        """빈 텍스트 처리 테스트"""
        empty_text = ""
        result = await evaluator.check_grammar(empty_text)

        # 빈 텍스트에 대한 응답 검증
        assert result["evaluation_type"] == "grammar_check"
        assert "token_usage" in result
        assert isinstance(result["score"], int)

    @pytest.mark.asyncio
    async def test_check_grammar_short_text(self, evaluator):
        """짧은 텍스트 처리 테스트"""
        short_text = "Hello world."
        result = await evaluator.check_grammar(short_text)

        # 기본 구조 검증
        assert result["rubric_item"] == "grammar"
        assert result["evaluation_type"] == "grammar_check"
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 2

    @pytest.mark.asyncio
    async def test_check_grammar_long_text(self, evaluator):
        """긴 텍스트 처리 테스트"""
        long_text = """
        Climate change is one of the most pressing issues of our time. The scientific evidence is overwhelming that human activities, particularly the emission of greenhouse gases, are causing significant changes to our planet's climate system. These changes manifest in various ways including rising global temperatures, melting ice caps, rising sea levels, and more frequent extreme weather events.
        
        The consequences of climate change are far-reaching and affect multiple aspects of human life and the natural world. Agricultural systems are being disrupted, leading to food security concerns. Coastal communities face the threat of sea-level rise and increased flooding. Biodiversity is under threat as species struggle to adapt to rapidly changing conditions.
        
        Addressing climate change requires urgent and coordinated action at all levels of society. Governments must implement policies that reduce greenhouse gas emissions and promote renewable energy. Businesses need to adopt sustainable practices and invest in clean technologies. Individuals can contribute by making environmentally conscious choices in their daily lives.
        """
        
        result = await evaluator.check_grammar(long_text)
        print(result)
        # 기본 구조 검증
        assert result["rubric_item"] == "grammar"
        assert result["evaluation_type"] == "grammar_check"
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 2
        assert isinstance(result["corrections"], list)
        assert isinstance(result["feedback"], str)
        
        # 긴 텍스트는 더 많은 토큰을 사용해야 함
        assert result["token_usage"]["total_tokens"] > 100

    @pytest.mark.asyncio
    async def test_check_grammar_multiple_sentences(self, evaluator):
        """여러 문장으로 구성된 텍스트 테스트"""
        multi_sentence_text = """
        I goes to school every day. My teacher are very nice. 
        We learns many things in class. Mathematics is my favorite subject.
        I wants to become a scientist when I grow up.
        """
        
        result = await evaluator.check_grammar(multi_sentence_text)

        # 기본 구조 검증
        assert result["rubric_item"] == "grammar"
        assert result["evaluation_type"] == "grammar_check"
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 2
        
        # 명백한 문법 오류가 있으므로 수정사항이 있어야 함
        assert len(result["corrections"]) > 0

    @pytest.mark.asyncio
    async def test_check_grammar_punctuation_errors(self, evaluator):
        """구두점 오류가 있는 텍스트 테스트"""
        punctuation_text = "Hello how are you today I am fine thank you What about you"
        
        result = await evaluator.check_grammar(punctuation_text)

        # 기본 구조 검증
        assert result["rubric_item"] == "grammar"
        assert result["evaluation_type"] == "grammar_check"
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 2

    @pytest.mark.asyncio
    async def test_check_grammar_consistency(self, evaluator, sample_text_good):
        """동일한 텍스트에 대한 일관성 테스트"""
        # 같은 텍스트를 두 번 테스트
        result1 = await evaluator.check_grammar(sample_text_good)
        result2 = await evaluator.check_grammar(sample_text_good)

        # 두 결과의 기본 구조가 같아야 함
        assert result1["rubric_item"] == result2["rubric_item"]
        assert result1["evaluation_type"] == result2["evaluation_type"]
        assert isinstance(result1["score"], int)
        assert isinstance(result2["score"], int)

    def test_evaluator_initialization(self):
        """GrammarEvaluator 초기화 테스트"""
        evaluator = GrammarEvaluator()
        
        assert evaluator.client is not None
        assert isinstance(evaluator.client, AzureOpenAILLM)
        assert evaluator.prompt_loader is not None

    def test_evaluator_initialization_with_custom_client(self):
        """커스텀 클라이언트로 초기화 테스트"""
        custom_client = AzureOpenAILLM()
        evaluator = GrammarEvaluator(client=custom_client)
        
        assert evaluator.client == custom_client

    @pytest.mark.asyncio
    async def test_pydantic_validation(self, evaluator, sample_text_good):
        """Pydantic 모델 검증 테스트"""
        result = await evaluator.check_grammar(sample_text_good)
        
        # RubricItemResult 모델로 검증 가능한지 확인
        # 메타데이터 제거 후 검증
        result_for_validation = {
            "rubric_item": result["rubric_item"],
            "score": result["score"],
            "corrections": result["corrections"],
            "feedback": result["feedback"]
        }
        
        # Pydantic 모델로 검증
        validated_result = RubricItemResult(**result_for_validation)
        assert validated_result.rubric_item == "grammar"
        assert isinstance(validated_result.score, int)
        assert isinstance(validated_result.corrections, list)
        assert isinstance(validated_result.feedback, str)

    @pytest.mark.asyncio
    async def test_token_usage_tracking(self, evaluator, sample_text_good):
        """토큰 사용량 추적 테스트"""
        result = await evaluator.check_grammar(sample_text_good)
        
        usage = result["token_usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage  
        assert "total_tokens" in usage
        
        assert isinstance(usage["prompt_tokens"], int)
        assert isinstance(usage["completion_tokens"], int)
        assert isinstance(usage["total_tokens"], int)
        
        assert usage["prompt_tokens"] > 0
        assert usage["completion_tokens"] > 0
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])