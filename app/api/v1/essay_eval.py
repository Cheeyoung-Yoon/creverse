
from fastapi import APIRouter, Depends, HTTPException
from app.client.azure_openai import AzureOpenAILLM
from app.utils.prompt_loader import PromptLoader
from app.services.essay_evaluator import EssayEvaluator
from app.models.request import EssayEvalRequest
# 기본 골조 작성 
router = APIRouter()

def get_llm():
    return AzureOpenAILLM()

def get_loader():
    return PromptLoader()

def get_evaluator(llm=Depends(get_llm), loader=Depends(get_loader)):
    return EssayEvaluator(llm, loader)

@router.post("/essay-eval")
async def essay_eval(req: EssayEvalRequest, evaluator: EssayEvaluator = Depends(get_evaluator)):
    try:
        return await evaluator.evaluate(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
