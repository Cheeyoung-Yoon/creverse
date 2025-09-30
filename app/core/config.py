# app/core/config.py
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings:
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    API_TIMEOUT_S: float = float(os.getenv("API_TIMEOUT_S", "15.0"))

settings = Settings()
