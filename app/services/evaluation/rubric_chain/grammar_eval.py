import json
import logging
from typing import Any, Dict, Optional

from app.client.bootstrap import build_llm
from app.models.rubric import RubricItemResult
from app.utils.prompt_loader import PromptLoader
from app.utils.tracer import LLM

logger = logging.getLogger(__name__)


class GrammarEvaluator:
    """문법 검수를 위한 평가자 클래스"""

    def __init__(self, client: Optional[LLM] = None, loader: Optional[PromptLoader] = None) -> None:
        self.client = client or build_llm()
        # Use provided PromptLoader if given; otherwise create a new one.
        self.prompt_loader = loader or PromptLoader()

    def _get_grammar_schema(self) -> Dict[str, Any]:
        """문법 검수 결과를 위한 JSON 스키마 (Pydantic에서 자동 생성)"""
        return RubricItemResult.model_json_schema()

    async def check_grammar(self, text: str, level: str = "Basic") -> Dict[str, Any]:
        """
        텍스트의 문법을 검사합니다.
        Returns: GrammarRubricResult + 메타데이터(token_usage, evaluation_type)
        """
        try:
            # 프롬프트 구성
            system_message = self.prompt_loader.load_prompt("grammar", level)
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": text},
            ]

            # Azure OpenAI 호출
            response = await self.client.run_azure_openai(
                messages=messages,
                json_schema=self._get_grammar_schema(),
                name="grammar_check",
            )

            content = response["content"]
            logger.info(f"Grammar LLM response content: {content}")
            
            # 모델이 문자열 JSON을 줄 수도 있음
            if isinstance(content, str):
                content = json.loads(content)

            # 빈 content 체크
            if not content or content == {}:
                logger.warning("Empty content received from LLM for grammar evaluation")
                return {
                    "rubric_item": "grammar",
                    "score": 0,
                    "corrections": [],
                    "feedback": "Grammar evaluation failed - empty response from AI model",
                    "token_usage": response.get("usage", {}),
                    "evaluation_type": "grammar_check"
                }

            # Pydantic 검증/파싱
            parsed = RubricItemResult(**content)
            result = parsed.model_dump()

            # 메타데이터 부가
            result["token_usage"] = response.get("usage", {})
            result["evaluation_type"] = "grammar_check"
            return result

        except Exception as exc:  # noqa: BLE001
            logger.exception("Grammar evaluation failed")
            return {
                "rubric_item": "grammar",
                "score": 1,  # Give a neutral score instead of 0
                "corrections": [],
                "feedback": "문법 검사 중 기술적 문제가 발생했습니다. 다시 시도해 주세요.",
                "error": str(exc),
                "evaluation_type": "grammar_check",
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
