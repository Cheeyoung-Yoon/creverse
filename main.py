import os
from dotenv import load_dotenv
load_dotenv()  # ★ 라우터/모듈 임포트 전에!

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.essay_eval import router as eval_router


def create_app() -> FastAPI:
    app = FastAPI(title="Essay Evaluation API", version="1.0.0")

    # CORS (open by default; tighten as needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(eval_router, prefix="/v1", tags=["evaluation"]) 

    @app.get("/health")
    def health():
        return {"status": "ok"}
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
