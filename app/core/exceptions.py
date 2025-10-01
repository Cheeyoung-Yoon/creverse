# app/core/exceptions.py
from fastapi import HTTPException, status
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class EvaluationException(Exception):
    """Base exception for evaluation errors"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class PromptLoadException(EvaluationException):
    """Prompt loading related errors"""
    pass

class LLMConnectionException(EvaluationException):
    """LLM connection/timeout errors"""
    pass

class ValidationException(EvaluationException):
    """Input validation errors"""
    pass

class TokenLimitException(EvaluationException):
    """Token limit exceeded errors"""
    pass

# Exception handlers
async def evaluation_exception_handler(request, exc: EvaluationException):
    logger.error(f"Evaluation error: {exc.message}", extra={"details": exc.details})
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": exc.message,
            "type": exc.__class__.__name__,
            "details": exc.details
        }
    )

async def llm_connection_exception_handler(request, exc: LLMConnectionException):
    logger.error(f"LLM connection error: {exc.message}")
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "External service temporarily unavailable",
            "type": "ServiceUnavailable",
            "retry_after": 30
        }
    )

async def token_limit_exception_handler(request, exc: TokenLimitException):
    logger.warning(f"Token limit exceeded: {exc.message}")
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail={
            "error": "Text too long for processing",
            "type": "TokenLimitExceeded",
            "max_tokens": exc.details.get("max_tokens", "N/A")
        }
    )