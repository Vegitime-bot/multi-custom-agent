"""
app.py - 메인 애플리케이션 진입점
사내 SSO 템플릿 구조에 맞춘 FastAPI 앱
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import base64
import json

from config import settings
from backend.api.admin import router as admin_router
from backend.api.chat import router as chat_router
from backend.api.health import router as health_router
from backend.api.permissions import router as permissions_router
from backend.api.conversations import router as conversations_router
from backend.managers.chatbot_manager import ChatbotManager
from backend.managers.memory_manager import MemoryManager
from backend.managers.session_manager import SessionManager
from backend.retrieval.ingestion_client import IngestionClient
from backend.roles.router import RoleRouter

# ── 정적 파일 경로 ─────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"

# ── Lifespan 이벤트 핸들러 ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 lifespan 이벤트"""
    # Startup
    app.state.chatbot_manager = ChatbotManager()
    app.state.session_manager = SessionManager()
    app.state.memory_manager = MemoryManager()
    app.state.ingestion_client = IngestionClient()
    app.state.role_router = RoleRouter(app.state.ingestion_client)
    
    # PostgreSQL 테이블 초기화
    if not settings.USE_MOCK_DB:
        try:
            from backend.database.session import init_tables
            init_tables()
            print("[Startup] PostgreSQL 테이블 초기화 완료")
        except Exception as e:
            print(f"[Startup] PostgreSQL 초기화 오류: {e}")
    
    print(f"[Startup] USE_MOCK_DB={settings.USE_MOCK_DB}, USE_MOCK_AUTH={settings.USE_MOCK_AUTH}")
    print(f"[Startup] 챗봇 {len(app.state.chatbot_manager.list_all())}개 로드됨")
    
    yield
    
    # Shutdown
    print("[Shutdown] 서버 종료 중...")


# ── FastAPI 앱 생성 ────────────────────────────────────────────────
def create_app() -> FastAPI:
    """
    FastAPI 애플리케이션 팩토리
    """
    app = FastAPI(
        title="Multi Custom Agent Service",
        description="멀티 테넌트 RAG 챗봇 플랫폼",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── Session 미들웨어 (SSO 인증용) ─────────────────────────────
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY or "your-secret-key-change-in-production",
        session_cookie="session",
        max_age=3600,  # 1시간
    )
    
    # ── CORS 미들웨어 ──────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── SSO 인증 (Mock Auth 아닐 때만) ────────────────────────────
    if not settings.USE_MOCK_AUTH:
        try:
            from backend.api.sso import router as sso_router
            app.include_router(sso_router, prefix="")  # 루트에 등록
            print("[Startup] SSO 인증 라우터 등록됨 (/, /sso, /acs, /slo)")
        except Exception as e:
            print(f"[Startup] SSO 라우터 로드 실패: {e}")
            
        # SSO 인증 상태 체크 후 챗봇 UI 제공
        @app.get("/", response_class=HTMLResponse)
        async def root_with_sso_check(request: Request):
            """
            루트 경로: SSO 인증 상태에 따라 챗봇 UI 또는 SSO 로그인으로 분기
            """
            if not settings.USE_MOCK_AUTH:
                try:
                    if 'sso' in request.session:
                        html_file = STATIC_DIR / "index.html"
                        if html_file.exists():
                            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
                    return RedirectResponse(url="/sso")
                except Exception:
                    return RedirectResponse(url="/sso")
            else:
                html_file = STATIC_DIR / "index.html"
                if html_file.exists():
                    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
                return HTMLResponse(content="<h1>Multi Custom Agent Service</h1><p>static/index.html 없음</p>")
        
        # SSO POST 콜백 처리 (사내 SSO용)
        @app.post("/")
        async def root_sso_callback(
                request: Request,
                id_token: str = Form(default=None),
                code: str = Form(default=None),
                state: str = Form(default=None),
        ):
            """
            SSO POST 콜백 처리 (IdP에서 form_post로 호출)
            id_token: JWT 토큰
            """
            if id_token:
                try:
                    # JWT payload 추출 (header.payload.signature에서 payload)
                    parts = id_token.split('.')
                    if len(parts) >= 2:
                        payload_b64 = parts[1]
                        # base64 패딩 보정
                        payload_b64 += '=' * (4 - len(payload_b64) % 4)
                        payload_json = base64.urlsafe_b64decode(payload_b64)
                        payload = json.loads(payload_json)

                        # knox_id 추출 (IdP 필드명 확인 필요)
                        knox_id = payload.get('sub') or payload.get('knox_id') or payload.get('username')

                        # 세션에 저장
                        request.session['sso'] = True
                        request.session['knox_id'] = knox_id
                        request.session['user_info'] = {
                            'name': payload.get('name', ''),
                            'email': payload.get('email', ''),
                        }
                        print(f"[SSO] 인증 성공 - knox_id: {knox_id}")

                        # 원래 요청한 chatbot 파라미터 유지
                        chatbot = request.query_params.get('chatbot')
                        if chatbot:
                            return RedirectResponse(url=f"/?chatbot={chatbot}", status_code=302)
                        return RedirectResponse(url="/", status_code=302)

                except Exception as e:
                    print(f"[SSO] 토큰 파싱 실패: {e}")
                    return RedirectResponse(url="/?error=sso_token_error", status_code=302)

            # 토큰 없이 code만 있는 경우
            if code:
                # TODO: code로 id_token 교환 (백엔드 채널)
                print(f"[SSO] code 수신: {code[:20]}...")
                request.session['sso'] = True
                return RedirectResponse(url="/", status_code=302)

            # 토큰도 코드도 없음
            return RedirectResponse(url="/?error=sso_no_token", status_code=302)
    else:
        # Mock Auth: 챗봇 UI를 루트에 표시
        @app.get("/", response_class=HTMLResponse)
        def index():
            html_file = STATIC_DIR / "index.html"
            if html_file.exists():
                return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>Multi Custom Agent Service</h1><p>static/index.html 없음</p>")

    # ── 라우터 등록 ───────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(admin_router, prefix="")
    app.include_router(permissions_router)
    app.include_router(conversations_router)

    # ── 정적 파일 마운트 ───────────────────────────────────────────
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


# ── 전역 앱 인스턴스 ─────────────────────────────────────────────
app = create_app()


# ── 직접 실행 (python app.py) ──────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    
    print(f"[Server] Starting on {settings.HOST}:{settings.PORT}")
    print(f"[Server] DEBUG={settings.DEBUG}")
    
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
