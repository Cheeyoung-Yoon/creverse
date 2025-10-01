import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.api.v1.essay_eval import router as eval_router
from app.core.exceptions import (
    EvaluationException,
    LLMConnectionException,
    TokenLimitException,
    evaluation_exception_handler,
    llm_connection_exception_handler,
    token_limit_exception_handler
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("🚀 Starting Essay Evaluation API")
    
    # Validate environment variables
    required_env_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY", 
        "AZURE_OPENAI_DEPLOYMENT"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {missing_vars}")
        raise RuntimeError(f"Missing environment variables: {missing_vars}")
    
    # Initialize services
    try:
        from app.client.bootstrap import build_llm
        llm = build_llm()
        logger.info("✅ LLM client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize LLM client: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Essay Evaluation API")

def create_app() -> FastAPI:
    """Create FastAPI application with enhanced configuration"""
    
    app = FastAPI(
        title="Essay Evaluation API",
        version="1.0.0",
        description="AI-powered essay evaluation system with rubric-based scoring",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # Middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # CORS with more restrictive settings for production
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    # Exception handlers
    app.add_exception_handler(EvaluationException, evaluation_exception_handler)
    app.add_exception_handler(LLMConnectionException, llm_connection_exception_handler)  
    app.add_exception_handler(TokenLimitException, token_limit_exception_handler)

    # Global exception handler for unhandled exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred. Please try again later."
            }
        )

    # Routers
    app.include_router(
        eval_router, 
        prefix="/v1", 
        tags=["evaluation"]
    )

    # Health check endpoints
    @app.get("/health", tags=["health"])
    async def health():
        """Simple health check"""
        return {"status": "ok", "version": "1.0.0"}
    
    @app.get("/health/detailed", tags=["health"])
    async def detailed_health():
        """Detailed health check with service status"""
        try:
            from app.client.bootstrap import build_llm
            llm = build_llm()
            
            # Quick ping to verify LLM connectivity
            await llm.run_azure_openai(
                messages=[{"role": "user", "content": "health check"}],
                json_schema={
                    "type": "object",
                    "properties": {"status": {"type": "string"}},
                    "required": ["status"]
                }
            )
            
            return {
                "status": "ok",
                "version": "1.0.0",
                "services": {
                    "llm": "connected",
                    "prompts": "loaded"
                }
            }
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded", 
                    "version": "1.0.0",
                    "error": str(e)
                }
            )
    
    return app

app = create_app()

if __name__ == "__main__":
    # Development server configuration
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug",
        access_log=True
    )