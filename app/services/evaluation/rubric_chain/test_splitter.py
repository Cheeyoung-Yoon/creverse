
"""Integration test for section splitting via Azure OpenAI.

This test intentionally hits the real Azure OpenAI endpoint. It is meant for
manual / exploratory verification and will be skipped automatically when the
required credentials are not configured.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from app.client.bootstrap import build_llm
from app.core.config import settings
from app.utils.tracer import LLM


class InlinePromptLoader:
    """Minimal prompt loader that keeps prompts in-memory for testing."""

    def load_prompt(self, rubric_item: str, level: str) -> str:
        if rubric_item != "section_split":
            raise ValueError(f"Unsupported rubric item: {rubric_item}")
        return (
            "You are a writing tutor. Split the user's essay into introduction, body, and conclusion.
"
            "Return a strict JSON object with exactly the keys 'introduction', 'body', 'conclusion'.
"
            "Each value must be a non-empty string summarising the corresponding section.
"
            "Do not include markdown, explanations, or additional keys."
        )


class SplitSections(BaseModel):
    introduction: str
    body: str
    conclusion: str


class SectionSplitter:
    """Lightweight splitter that talks directly to Azure OpenAI."""

    def __init__(
        self,
        *,
        client: LLM | None = None,
        loader: InlinePromptLoader | None = None,
    ) -> None:
        self.client = client or build_llm()
        self.prompt_loader = loader or InlinePromptLoader()

    async def split(self, text: str, level: str) -> SplitSections:
        prompt = self.prompt_loader.load_prompt("section_split", level)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ]
        response = await self.client.run_azure_openai(
            messages=messages,
            json_schema=SplitSections.model_json_schema(),
            name="integration.section_split",
        )
        payload = response.get("content")
        if isinstance(payload, str):
            payload = json.loads(payload)
        return SplitSections.model_validate(payload)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT,
    reason="Azure OpenAI credentials are not configured.",
)
async def test_splitter_returns_sections():
    sample_text = (
        "Climate change is one of the defining challenges of our generation. "
        "In this essay I argue that local communities must take action. "
        "First, I examine the scientific consensus showing rising temperatures. "
        "Then, I describe how community-led recycling programs contribute to lowering emissions. "
        "Finally, I conclude with a call to participate in regional planning meetings so that policies "
        "reflect citizen priorities."
    )

    splitter = SectionSplitter()
    result = await splitter.split(sample_text, level="Basic")

    assert result.introduction.strip(), "introduction should not be empty"
    assert result.body.strip(), "body should not be empty"
    assert result.conclusion.strip(), "conclusion should not be empty"

    # Ensure the splitter is not echoing the entire essay verbatim for every section
    joined_sections = " ".join([result.introduction, result.body, result.conclusion])
    assert len(joined_sections) <= len(sample_text) * 3
