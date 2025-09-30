
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.client.bootstrap import build_llm
from app.utils.prompt_loader import PromptLoader
from app.utils.tracer import LLM

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = (
    "You are a writing tutor. Split the user's essay into introduction, body, and conclusion.
"
    "Return a strict JSON object with exactly the keys 'introduction', 'body', 'conclusion'.
"
    "Each value must be a non-empty string summarising the corresponding section.
"
    "Do not include markdown, explanations, or additional keys."
)


class SectionSplitResult(BaseModel):
    introduction: str
    body: str
    conclusion: str


class SectionSplitter:
    """Use an LLM to split an essay into introduction/body/conclusion sections."""

    def __init__(
        self,
        *,
        client: Optional[LLM] = None,
        loader: Optional[PromptLoader] = None,
    ) -> None:
        self.client = client or build_llm()
        self.prompt_loader = loader or PromptLoader()

    def _schema(self) -> Dict[str, Any]:
        return SectionSplitResult.model_json_schema()

    def _prompt(self, level: str) -> str:
        try:
            return self.prompt_loader.load_prompt("section_split", level)
        except Exception:  # noqa: BLE001
            logger.debug("Falling back to default section split prompt", exc_info=True)
            return _DEFAULT_PROMPT

    async def split(self, text: str, level: str) -> SectionSplitResult:
        messages = [
            {"role": "system", "content": self._prompt(level)},
            {"role": "user", "content": text},
        ]

        response = await self.client.run_azure_openai(
            messages=messages,
            json_schema=self._schema(),
            name="structure.section_split",
        )
        payload = response.get("content")
        if isinstance(payload, str):
            payload = json.loads(payload)

        result = SectionSplitResult.model_validate(payload)
        return result
