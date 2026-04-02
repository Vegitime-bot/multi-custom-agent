from __future__ import annotations
"""
config.py - 환경설정 관리
환경변수를 읽어 애플리케이션 전체에서 사용하는 설정 객체를 제공한다.
"""
import os
from pathlib import Path

# 프로젝트 루트 (multi-custom-agent/)
PROJECT_ROOT = Path(__file__).parent.parent

# .env 파일 로드 (python-dotenv 사용)
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
except ImportError:
    pass  # python-dotenv 없으면 환경변수만 사용


class Settings:
    # ── 모드 플래그 ──────────────────────────────────────────────
    USE_MOCK_DB: bool = os.getenv("USE_MOCK_DB", "true").lower() == "true"
    USE_MOCK_AUTH: bool = os.getenv("USE_MOCK_AUTH", "true").lower() == "true"

    # ── PostgreSQL ───────────────────────────────────────────────
    PG_HOST: str = os.getenv("PG_HOST", "localhost")
    PG_PORT: int = int(os.getenv("PG_PORT", "5432"))
    PG_DB: str = os.getenv("PG_DB", "chatbot_db")
    PG_USER: str = os.getenv("PG_USER", "postgres")
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", "")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}"
        )

    # ── LLM (OpenAI 호환 사내 엔드포인트) ────────────────────────
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "dummy-key")
    LLM_DEFAULT_MODEL: str = os.getenv("LLM_DEFAULT_MODEL", "GLM4.7")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "120"))
    
    # ── LLM 기본 설정 (모든 챗봇 공통) ───────────────────────────
    LLM_DEFAULT_TEMPERATURE: float = float(os.getenv("LLM_DEFAULT_TEMPERATURE", "0.3"))
    LLM_DEFAULT_MAX_TOKENS: int = int(os.getenv("LLM_DEFAULT_MAX_TOKENS", "1024"))

    # ── Ingestion 서버 ────────────────────────────────────────────
    INGESTION_BASE_URL: str = os.getenv("INGESTION_BASE_URL", "http://localhost:8001")

    # ── SSL ──────────────────────────────────────────────────────
    SSL_VERIFY: bool = os.getenv("SSL_VERIFY", "false").lower() == "true"

    # ── 챗봇 정의 경로 ────────────────────────────────────────────
    CHATBOTS_DIR: Path = PROJECT_ROOT / "chatbots"

    # ── 서버 ─────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


# 싱글턴 설정 인스턴스
settings = Settings()
