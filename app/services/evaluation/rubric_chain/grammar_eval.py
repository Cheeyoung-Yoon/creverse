from typing import Dict, Any, Optional
import json
from app.client.azure_openai import AzureOpenAILLM
from app.utils.prompt_loader import PromptLoader
from app.models.rubric import RubricItemResult


class GrammarEvaluator:
    """문법 검수를 위한 평가자 클래스"""
    
    def __init__(self, client: Optional[AzureOpenAILLM] = None):
        self.client = client or AzureOpenAILLM()
        self.prompt_loader = PromptLoader()
    
    def _get_grammar_schema(self) -> Dict[str, Any]:
        """문법 검수 결과를 위한 JSON 스키마 (Pydantic에서 자동 생성)"""
        return RubricItemResult.model_json_schema()
    
    async def check_grammar(self, text: str, level: str = "Basic", trace_id: str | None = None) -> Dict[str, Any]:
        """
        텍스트의 문법을 검사합니다.
        Returns: GrammarRubricResult + 메타데이터(token_usage, evaluation_type)
        """
        try:
            # 프롬프트 구성
            system_message = self.prompt_loader.load_prompt(
                "grammar", level
            )
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": text},
            ]
            
            # Azure OpenAI 호출
            response = await self.client.generate_json(
                messages=messages,
                json_schema=self._get_grammar_schema(),
                trace_id=trace_id,
                name="grammar_check",
            )
            
            content = response["content"]
            # 모델이 문자열 JSON을 줄 수도 있음
            if isinstance(content, str):
                content = json.loads(content)
            
            # Pydantic 검증/파싱
            parsed = RubricItemResult(**content)
            result = parsed.model_dump()
            
            # 메타데이터 부가
            result["token_usage"] = response.get("usage", {})
            result["evaluation_type"] = "grammar_check"
            return result

        except Exception as e:
            return {
                "rubric_item": "grammar",
                "score": 0,
                "corrections": [],
                "feedback": f"문법 검사 중 오류 발생: {str(e)}",
                "error": str(e),
                "evaluation_type": "grammar_check",
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
