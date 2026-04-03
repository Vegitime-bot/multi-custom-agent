"""
backend/api/sso.py - OIDC/OAuth2 SSO 인증
OpenID Connect Authorization Code Flow 구현

TODO: 사내 SSO Provider에 맞게 수정 필요
"""
from __future__ import annotations
import secrets
import hashlib
import base64
from urllib.parse import urlencode, parse_qs, urlparse
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
import httpx

from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# ── SSO 설정 ─────────────────────────────────────────────────────
# TODO: 아래 설정값을 .env 파일로 이동하여 관리
SSO_CONFIG = {
    # OIDC Discovery URL (사내 SSO 서버의 well-known endpoint)
    "issuer": getattr(settings, "SSO_ISSUER", "https://sso.company.com"),
    
    # OAuth2 클라이언트 설정
    "client_id": getattr(settings, "SSO_CLIENT_ID", "your-client-id"),
    "client_secret": getattr(settings, "SSO_CLIENT_SECRET", "your-client-secret"),
    
    # 콜백 URL (반드시 SSO 서버에 등록된 URI와 일치해야 함)
    "redirect_uri": getattr(settings, "SSO_REDIRECT_URI", "http://localhost:8080/auth/acs"),
    
    # OAuth2 Endpoints (Discovery로 자동 설정 가능)
    "authorization_endpoint": getattr(settings, "SSO_AUTH_URL", "https://sso.company.com/oauth2/authorize"),
    "token_endpoint": getattr(settings, "SSO_TOKEN_URL", "https://sso.company.com/oauth2/token"),
    "userinfo_endpoint": getattr(settings, "SSO_USERINFO_URL", "https://sso.company.com/oauth2/userinfo"),
    "end_session_endpoint": getattr(settings, "SSO_LOGOUT_URL", None),  # Optional
    
    # 요청 Scope
    "scopes": getattr(settings, "SSO_SCOPES", "openid email profile"),
}


# ── PKCE 생성 ──────────────────────────────────────────────────────
def generate_pkce() -> tuple[str, str]:
    """
    PKCE 코드 생성 (Code Challenge, Verifier)
    TODO: 사내 SSO에서 PKCE 필수 여부 확인
    """
    code_verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode('utf-8').rstrip('=')
    
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge


# ── SSO 로그인 시작 (/sso) ─────────────────────────────────────────
@router.get("/sso")
async def sso_login(request: Request):
    """
    SSO 로그인 시작
    OIDC Provider로 리다이렉트
    """
    # TODO: 사용자가 이미 로그인했는지 확인 (선택사항)
    # if request.session.get("user"):
    #     return RedirectResponse(url="/")
    
    # CSRF 방지용 state 생성
    state = secrets.token_urlsafe(32)
    
    # PKCE 생성 (보안 강화)
    code_verifier, code_challenge = generate_pkce()
    
    # 세션에 state와 code_verifier 저장 (콜백에서 검증)
    # TODO: Redis/DB 세션으로 변경 권장 (현재는 메모리)
    request.session["sso_state"] = state
    request.session["sso_code_verifier"] = code_verifier
    
    # Authorization URL 구성
    params = {
        "client_id": SSO_CONFIG["client_id"],
        "response_type": "code",
        "scope": SSO_CONFIG["scopes"],
        "redirect_uri": SSO_CONFIG["redirect_uri"],
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",  # PKCE
    }
    
    # TODO: 사내 SSO에 맞게 추가 파라미터 필요 시 수정
    # 예: prompt=login (항상 로그인 화면 표시)
    # 예: login_hint=user@company.com (사용자 미리 채워넣기)
    
    auth_url = f"{SSO_CONFIG['authorization_endpoint']}?{urlencode(params)}"
    
    return RedirectResponse(url=auth_url)


# ── SSO 콜백 (/acs) ──────────────────────────────────────────────
@router.get("/acs")
async def sso_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """
    SSO 콜백 처리 (Assertion Consumer Service)
    OIDC Provider에서 리다이렉트되어 code를 받아 처리
    """
    # ── 에러 처리 ─────────────────────────────────────────────────
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSO Error: {error} - {error_description}"
        )
    
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code is missing"
        )
    
    # ── state 검증 (CSRF 방지) ──────────────────────────────────
    saved_state = request.session.get("sso_state")
    if not saved_state or saved_state != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )
    del request.session["sso_state"]
    
    # ── code로 token 교환 ───────────────────────────────────────
    code_verifier = request.session.get("sso_code_verifier")
    if not code_verifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PKCE verification failed"
        )
    del request.session["sso_code_verifier"]
    
    # Token 요청
    token_data = await exchange_code_for_token(code, code_verifier)
    
    if "error" in token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token exchange failed: {token_data.get('error_description', token_data['error'])}"
        )
    
    # ── 사용자 정보 조회 ────────────────────────────────────────
    access_token = token_data.get("access_token")
    id_token = token_data.get("id_token")  # JWT
    
    # UserInfo Endpoint 호출 또는 ID Token 파싱
    user_info = await get_user_info(access_token, id_token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to retrieve user information"
        )
    
    # ── 세션 생성 ─────────────────────────────────────────────────
    # TODO: 사용자 정보 매핑 사내 규칙에 맞게 수정
    # 예: employee_id, department, role 등 추가 매핑
    request.session["user"] = {
        "id": user_info.get("sub") or user_info.get("id"),  # OIDC: sub, OAuth2: id
        "email": user_info.get("email"),
        "name": user_info.get("name") or user_info.get("display_name"),
        "access_token": access_token,  # API 호출용 (선택)
    }
    
    # TODO: PostgreSQL에 사용자 정보 저장/업데이트 (선택)
    # await save_user_to_db(user_info)
    
    # 로그인 성공 후 리다이쉿
    return RedirectResponse(url="/")


# ── 토큰 교환 ────────────────────────────────────────────────────
async def exchange_code_for_token(code: str, code_verifier: str) -> Dict[str, Any]:
    """
    Authorization Code를 Access Token으로 교환
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SSO_CONFIG["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": SSO_CONFIG["client_id"],
                "client_secret": SSO_CONFIG["client_secret"],
                "code": code,
                "redirect_uri": SSO_CONFIG["redirect_uri"],
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        # TODO: 사내 SSO에서 인증 방식이 다르면 수정 (예: Basic Auth)
        return response.json()


# ── 사용자 정보 조회 ───────────────────────────────────────────────
async def get_user_info(access_token: str, id_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    UserInfo Endpoint 호출 또는 ID Token 파싱
    TODO: 사내 SSO 방식에 맞게 선택
    """
    # 방법 1: UserInfo Endpoint 호출 (표준 OIDC)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            SSO_CONFIG["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 200:
            return response.json()
    
    # 방법 2: ID Token 직접 파싱 (JWT)
    # TODO: JWT 서명 검증 필요 (사내 SSO의 JWKS endpoint 사용)
    if id_token:
        try:
            # JWT payload 디코딩 (검증 없이)
            # 실제 운영에서는 PyJWT + 검증 필수
            payload = id_token.split(".")[1]
            padding = 4 - len(payload) % 4
            payload += "=" * padding
            return json.loads(base64.b64decode(payload))
        except Exception:
            pass
    
    return None


# ── 로그아웃 ─────────────────────────────────────────────────────
@router.get("/logout")
async def logout(request: Request):
    """
    로그아웃
    세션 삭제 및 OIDC 로그아웃 (선택)
    """
    user = request.session.get("user")
    
    # 세션 삭제
    request.session.clear()
    
    # OIDC RP-Initiated Logout (지원 시)
    # TODO: 사내 SSO에서 logout endpoint 지원 여부 확인
    if SSO_CONFIG.get("end_session_endpoint") and user:
        params = {
            "id_token_hint": user.get("id_token"),  # 있을 경우
            "post_logout_redirect_uri": "http://localhost:8080/",
        }
        logout_url = f"{SSO_CONFIG['end_session_endpoint']}?{urlencode(params)}"
        return RedirectResponse(url=logout_url)
    
    return RedirectResponse(url="/")


# ── 현재 사용자 정보 ─────────────────────────────────────────────
@router.get("/me")
async def get_current_user(request: Request):
    """
    현재 로그인한 사용자 정보 반환
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user


# ── OIDC Discovery (자동 설정) ───────────────────────────────────
async def discover_oidc_config(issuer: str) -> Dict[str, str]:
    """
    OIDC Discovery URL에서 설정 자동 로드
    사용 예: await discover_oidc_config("https://sso.company.com")
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{issuer}/.well-known/openid-configuration")
        if response.status_code == 200:
            config = response.json()
            return {
                "authorization_endpoint": config.get("authorization_endpoint"),
                "token_endpoint": config.get("token_endpoint"),
                "userinfo_endpoint": config.get("userinfo_endpoint"),
                "end_session_endpoint": config.get("end_session_endpoint"),
            }
    return {}


# TODO: 앱 시작 시 Discovery로 설정 로드 (선택)
# @router.on_event("startup")
# async def load_oidc_config():
#     global SSO_CONFIG
#     discovered = await discover_oidc_config(SSO_CONFIG["issuer"])
#     SSO_CONFIG.update(discovered)
