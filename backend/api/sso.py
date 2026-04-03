"""
backend/api/sso.py - OIDC/OAuth2 SSO 인증 (사내 템플릿 구조)

사내 SSO 템플릿에 맞춘 구조:
- GET /         : 로그인 폼 (index.html)
- GET /sso      : SSO 인증 요청
- GET /acs      : SSO 콜백 (Assertion Consumer Service)
- GET /slo      : 로그아웃 (Single Logout)

TODO: 사내 SSO Provider에 맞게 구현 필요
"""
from __future__ import annotations
import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from config import settings

router = APIRouter(tags=["auth"])

# ── 템플릿 설정 ────────────────────────────────────────────────────
# TODO: 템플릿 경로 사내 환경에 맞게 수정
templates = Jinja2Templates(directory="templates")


# ── 1. 로그인 폼 (/)
# 사내 템플릿: return templates.TemplateResponse('index.html', context={...})
@router.get("/", response_class=HTMLResponse)
async def get_login_form(request: Request):
    """
    로그인 폼 페이지
    사내 템플릿: index.html
    """
    # TODO: 사내 템플릿에 맞게 context 수정
    context = {
        "request": request,
        "claim_val": "",  # TODO: 사내 claim 값 설정
        # TODO: 사내 추가 context 변수
    }
    
    return templates.TemplateResponse("index.html", context=context)


# ── 2. SSO 인증 요청 (/sso)
# 사내 템플릿: @app.get('/sso') -> return RedirectResponse(...)
@router.get("/sso")
async def sso(request: Request):
    """
    SSO 인증 요청 시작
    OIDC Provider로 리다이렉트
    """
    # TODO: CSRF 방지용 state 생성 및 세션 저장
    state = secrets.token_urlsafe(32)
    request.session["sso_state"] = state
    
    # TODO: PKCE 생성 (사내 SSO에서 필요 시)
    # code_verifier, code_challenge = generate_pkce()
    # request.session["sso_code_verifier"] = code_verifier
    
    # TODO: 사내 SSO Authorization URL 구성
    # issuer = settings.SSO_ISSUER
    # client_id = settings.SSO_CLIENT_ID
    # redirect_uri = settings.SSO_REDIRECT_URI
    # scopes = settings.SSO_SCOPES
    
    # TODO: 사내 SSO에 맞게 파라미터 구성
    # auth_url = f"{issuer}/oauth2/authorize?..."
    
    # 임시: 실제 구현 시 아래 return 대신 리다이렉트 URL 반환
    # return RedirectResponse(url=auth_url)
    
    # TODO: 사내 구현으로 교체
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="SSO not implemented yet. TODO: 사내 SSO 로직 추가"
    )


# ── 3. SSO 콜백 (/acs)
# 사내 템플릿: @app.get('/acs') -> return templates.TemplateResponse(...)
@router.get("/acs")
async def acs(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """
    SSO 콜백 처리 (Assertion Consumer Service)
    OIDC Provider에서 인증 후 리다이렉트
    """
    # TODO: 사내 SSO 응답 처리
    
    # ── 에러 처리 ─────────────────────────────────────────────────
    if error:
        # TODO: 사내 에러 처리 방식으로 수정
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "claim_val": f"Error: {error} - {error_description}",
            }
        )
    
    if not code:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "claim_val": "Error: Authorization code missing",
            }
        )
    
    # TODO: state 검증 (CSRF 방지)
    # saved_state = request.session.get("sso_state")
    # if not saved_state or saved_state != state:
    #     return templates.TemplateResponse("index.html", {...})
    
    # TODO: code로 token 교환
    # token_data = await exchange_code_for_token(code, code_verifier)
    
    # TODO: 사용자 정보 조회 및 복호화
    # user_info = await get_user_info(access_token)
    
    # TODO: 세션에 사용자 정보 저장
    # request.session["user"] = {
    #     "id": user_info.get("sub"),
    #     "email": user_info.get("email"),
    #     # ...
    # }
    
    # TODO: 사내 템플릿 반환 (로그인 성공)
    # return templates.TemplateResponse("dashboard.html", {...})
    
    # 임시: 실제 구현 필요
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="ACS not implemented yet. TODO: 사내 SSO 콜백 로직 추가"
    )


# ── 4. 로그아웃 (/slo)
# 사내 템플릿: @app.get('/slo') -> return response
@router.get("/slo")
async def slo(request: Request):
    """
    로그아웃 (Single Logout)
    세션 삭제 및 OIDC 로그아웃 (선택)
    """
    # TODO: 세션에서 사용자 정보 가져오기
    # user = request.session.get("user")
    
    # TODO: 세션 삭제
    request.session.clear()
    
    # TODO: 사내 SSO RP-Initiated Logout (지원 시)
    # if settings.SSO_LOGOUT_URL and user:
    #     params = {
    #         "id_token_hint": user.get("id_token"),
    #         "post_logout_redirect_uri": "http://localhost:8080/",
    #     }
    #     logout_url = f"{settings.SSO_LOGOUT_URL}?{urlencode(params)}"
    #     return RedirectResponse(url=logout_url)
    
    # TODO: 사내 로그아웃 후 리다이렉트
    # return RedirectResponse(url="/")
    # 또는 템플릿 반환
    
    # 임시: 실제 구현 필요
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="SLO not implemented yet. TODO: 사내 로그아웃 로직 추가"
    )


# ── 유틸리티 함수 (TODO: 사내 구현에 맞게 수정) ────────────────────

def generate_pkce() -> tuple[str, str]:
    """
    PKCE 코드 생성
    TODO: 사내 SSO에서 PKCE 필수 여부 확인
    """
    import base64
    import hashlib
    
    code_verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode('utf-8').rstrip('=')
    
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge


# TODO: 토큰 교환 함수
# async def exchange_code_for_token(code: str, code_verifier: str) -> dict:
#     ...

# TODO: 사용자 정보 조회 함수
# async def get_user_info(access_token: str) -> dict:
#     ...
