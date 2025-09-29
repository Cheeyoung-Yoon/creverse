from client.azure_openai import AzureOpenAILLM
from typing import Dict




async def analyze_intro(text: str) -> Dict:
    s = await safe_llm(f"서론 평가:\n{text}")
    return {"section": "intro", "summary": s}

async def analyze_body(text: str, intro_summary: str) -> Dict:
    s = await safe_llm(f"본론 평가(서론 요약:{intro_summary}):\n{text}")
    return {"section": "body", "summary": s}

async def analyze_conclusion(text: str, body_summary: str) -> Dict:
    s = await safe_llm(f"결론 평가(본론 요약:{body_summary}):\n{text}")
    return {"section": "conclusion", "summary": s}

async def run_structure_chain(intro: str, body: str, conclusion: str) -> Dict:
    intro_res = await analyze_intro(intro)
    body_res  = await analyze_body(body, intro_res["summary"])
    concl_res = await analyze_conclusion(conclusion, body_res["summary"])
    return {"intro": intro_res, "body": body_res, "conclusion": concl_res}