from __future__ import annotations
"""
main.py - FastAPI 앱 진입점
앱 초기화, 상태 객체 등록, 라우터 등록, 정적 파일 서빙을 수행한다.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.api.admin import router as admin_router
from backend.api.chat import router as chat_router
from backend.api.health import router as health_router
from backend.config import settings
from backend.managers.chatbot_manager import ChatbotManager
from backend.managers.memory_manager import MemoryManager
from backend.managers.session_manager import SessionManager
from backend.retrieval.ingestion_client import IngestionClient
from backend.roles.router import RoleRouter

# ── 정적 파일 경로 ─────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent.parent / "static"

# ── 앱 생성 ───────────────────────────────────────────────────────
app = FastAPI(
    title="Multi Custom Agent Service",
    description="멀티 테넌트 RAG 챗봇 플랫폼",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 앱 시작 시 상태 객체 초기화 ───────────────────────────────────
@app.on_event("startup")
def startup():
    app.state.chatbot_manager = ChatbotManager()
    app.state.session_manager = SessionManager()
    app.state.memory_manager  = MemoryManager()
    app.state.ingestion_client = IngestionClient()
    app.state.role_router     = RoleRouter(app.state.ingestion_client)
    print(f"[Startup] USE_MOCK_DB={settings.USE_MOCK_DB}, USE_MOCK_AUTH={settings.USE_MOCK_AUTH}")
    print(f"[Startup] 챗봇 {len(app.state.chatbot_manager.list_all())}개 로드됨")


# ── 라우터 등록 ───────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(admin_router, prefix="")


# ── 루트: HTML 챗 UI 서빙 ─────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Multi Custom Agent Service</h1><p>static/index.html 없음</p>")


# ── 정적 파일 마운트 ──────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 직접 실행 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
