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
        same_site="lax",  # SSO 리다이렉트용 lax 설정
        https_only=False,  # 개발 환경용 (프로덕션에서는 True)
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
            # 🔍 디버깅: GET / 요청 확인
            print(f"[GET / DEBUG] 요청 받음 - query: {dict(request.query_params)}")
            print(f"[GET / DEBUG] cookies: {request.cookies.get('session', '없음')[:20] if 'session' in request.cookies else '없음'}")
            
            if not settings.USE_MOCK_AUTH:
                try:
                    has_session = hasattr(request, 'session')
                    sso_value = request.session.get('sso') if has_session else 'N/A'
                    knox_id = request.session.get('knox_id') if has_session else 'N/A'
                    print(f"[GET / DEBUG] session 존재: {has_session}")
                    print(f"[GET / DEBUG] session['sso']: {sso_value}")
                    print(f"[GET / DEBUG] session['knox_id']: {knox_id}")
                    
                    if sso_value:
                        print(f"[GET / DEBUG] ✅ SSO 인증됨 - HTML 반환")
                        html_file = STATIC_DIR / "index.html"
                        if html_file.exists():
                            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
                    else:
                        print(f"[GET / DEBUG] ❌ SSO 미인증 - /sso로 리다이렉트")
                    return RedirectResponse(url="/sso")
                except Exception as e:
                    print(f"[GET / DEBUG] 예외 발생: {e}")
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
            error: str = Form(default=None),
        ):
            """
            SSO POST 콜백 처리 (IdP에서 form_post로 호출)
            """
            print(f"\n{'='*60}")
            print(f"[SSO POST /] ⭐ IdP로부터 POST 콜백 받음!")
            print(f"[SSO POST /] id_token: {'✅ 있음' if id_token else '❌ 없음'}")
            print(f"[SSO POST /] code: {'✅ 있음' if code else '❌ 없음'}")
            print(f"[SSO POST /] state: {state}")
            print(f"[SSO POST /] error: {error}")
            
            # 세션 쿠키 확인
            session_cookie = request.cookies.get('session')
            print(f"[SSO POST /] session 쿠키: {'✅ 있음' if session_cookie else '❌ 없음'}")

            if error:
                print(f"[SSO ERROR] IdP 에러: {error}")
                return RedirectResponse(url=f"/?error={error}")

            if id_token:
                try:
                    parts = id_token.split('.')
                    print(f"[SSO] JWT parts 수: {len(parts)}")

                    if len(parts) >= 2:
                        payload_b64 = parts[1]
                        payload_b64 += '=' * (4 - len(payload_b64) % 4)
                        payload_json = base64.urlsafe_b64decode(payload_b64)
                        payload = json.loads(payload_json)

                        print(f"[SSO] JWT payload: {json.dumps(payload, indent=2, ensure_ascii=False)[:500]}")

                        # knox_id 추출
                        knox_id = (
                            payload.get('sub') or
                            payload.get('knox_id') or
                            payload.get('username') or
                            payload.get('email') or
                            payload.get('preferred_username') or
                            payload.get('user_id') or
                            payload.get('upn') or
                            payload.get('name')
                        )

                        print(f"[SSO] 추출된 knox_id: {knox_id}")

                        if knox_id:
                            # 세션에 저장
                            request.session['sso'] = True
                            request.session['knox_id'] = knox_id
                            request.session['user_info'] = {
                                'name': payload.get('name', ''),
                                'email': payload.get('email', ''),
                            }
                            print(f"[SSO] ✅ 세션 저장 완료")

                            chatbot = request.query_params.get('chatbot')
                            redirect_url = f"/?chatbot={chatbot}" if chatbot else "/"
                            print(f"[SSO] 리다이렉트: {redirect_url}")
                            return RedirectResponse(url=redirect_url, status_code=302)

                except Exception as e:
                    print(f"[SSO ERROR] 토큰 파싱 실패: {e}")
                    return RedirectResponse(url="/?error=sso_token_error", status_code=302)

            # code만 있는 경우  
            if code:
                print(f"[SSO] code 수신: {code[:20]}...")
                request.session['sso'] = True
                request.session['knox_id'] = 'code_only_user'
                return RedirectResponse(url="/", status_code=302)

            print(f"[SSO ERROR] 토큰 없음")
            return RedirectResponse(url="/?error=sso_no_token", status_code=302)
        
        # SSO /acs 콜백 처리 (IdP form_post용 - sso.py보다 우선)
        @app.post("/acs")
        async def acs_sso_callback(
            request: Request,
            id_token: str = Form(default=None),
            code: str = Form(default=None),
            state: str = Form(default=None),
            error: str = Form(default=None),
        ):
            """
            SSO /acs POST 콜백 처리 (IdP에서 form_post로 호출)
            """
            print(f"\n{'='*60}")
            print(f"[SSO POST /acs] ⭐ IdP로부터 POST 콜백 받음!")
            print(f"[SSO POST /acs] id_token: {'✅ 있음' if id_token else '❌ 없음'}")
            print(f"[SSO POST /acs] code: {'✅ 있음' if code else '❌ 없음'}")
            print(f"[SSO POST /acs] state: {state}")
            print(f"[SSO POST /acs] error: {error}")
            
            if error:
                print(f"[SSO ERROR] IdP 에러: {error}")
                return RedirectResponse(url=f"/?error={error}")

            if id_token:
                print(f"[SSO] id_token 길이: {len(id_token)}")
                print(f"[SSO] id_token 앞 100자: {id_token[:100]}...")
                
                try:
                    parts = id_token.split('.')
                    print(f"[SSO] JWT parts 수: {len(parts)}")

                    if len(parts) >= 2:
                        # JWT Payload 디코딩
                        payload_b64 = parts[1]
                        payload_b64 += '=' * (4 - len(payload_b64) % 4)
                        payload_json = base64.urlsafe_b64decode(payload_b64)
                        payload = json.loads(payload_json)

                        print(f"[SSO] JWT payload: {json.dumps(payload, indent=2, ensure_ascii=False)[:500]}")

                        # knox_id 추출 (다양한 필드명 시도)
                        knox_id = (
                            payload.get('sub') or
                            payload.get('knox_id') or
                            payload.get('username') or
                            payload.get('email') or
                            payload.get('preferred_username') or
                            payload.get('user_id') or
                            payload.get('upn') or
                            payload.get('name') or
                            payload.get('oid') or  # Azure AD용
                            payload.get('upn')
                        )

                        print(f"[SSO] 추출된 knox_id: {knox_id}")

                        if knox_id:
                            request.session['sso'] = True
                            request.session['knox_id'] = knox_id
                            request.session['user_info'] = {
                                'name': payload.get('name', ''),
                                'email': payload.get('email', ''),
                            }
                            print(f"[SSO] ✅ 세션 저장 완료: knox_id={knox_id}")

                            # state에 chatbot 정보가 있을 수 있음
                            redirect_url = f"/?chatbot={state}" if state else "/"
                            print(f"[SSO] 리다이렉트: {redirect_url}")
                            return RedirectResponse(url=redirect_url, status_code=302)
                        else:
                            print(f"[SSO WARNING] knox_id 없음. payload 키: {list(payload.keys())}")
                            # 사용자 ID 없어도 인증된 것으로 처리
                            request.session['sso'] = True
                            request.session['knox_id'] = 'unknown'
                            return RedirectResponse(url="/", status_code=302)

                except Exception as e:
                    print(f"[SSO ERROR] 토큰 파싱 실패: {e}")
                    import traceback
                    traceback.print_exc()
                    # 파싱 실패해도 인증된 것으로 처리 (임시)
                    request.session['sso'] = True
                    request.session['knox_id'] = 'parse_failed'
                    return RedirectResponse(url="/", status_code=302)

            # code만 있는 경우
            if code:
                print(f"[SSO] code 수신: {code[:20]}...")
                request.session['sso'] = True
                request.session['knox_id'] = 'code_only_user'
                return RedirectResponse(url="/", status_code=302)

            print(f"[SSO ERROR] 토큰 없음")
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
