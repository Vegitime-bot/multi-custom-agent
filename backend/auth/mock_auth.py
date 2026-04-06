from __future__ import annotations
"""
auth/mock_auth.py - Mock Auth (SSO bypass)
USE_MOCK_AUTH=true 일 때 고정 사용자를 반환한다.
USE_MOCK_AUTH=false 일 때는 실제 OAuth SSO 검증 로직을 연결해야 한다 (TBD).
"""
from fastapi import Request, HTTPException, status

from backend.config import settings
from backend.users.repository import get_user_repository


def get_current_user(request: Request) -> dict:
    """
    현재 요청의 사용자를 반환한다.
    - USE_MOCK_AUTH=true: 고정 사용자(jyd1234) 반환
    - USE_MOCK_AUTH=false: 
        1. 세션에 sso 정보가 있으면 세션에서 사용자 정보 읽기
        2. 없으면 X-Knox-Id 헤더 기반 DB 조회
    """
    if settings.USE_MOCK_AUTH:
        return {"knox_id": "jyd1234", "name": "장영동", "team": "AI팀", "eng_name": "Youngdong Jang"}

    # ── 세션 기반 SSO 인증 (사내 SSO) ─────────────────────────────
    # SSO 인증 후 세션에 'sso'와 'knox_id' 저장됨
    try:
        if hasattr(request, 'session') and request.session.get('sso'):
            knox_id = request.session.get('knox_id')
            if knox_id:
                repo = get_user_repository(use_mock=settings.USE_MOCK_DB)
                user = repo.get_user_by_knox_id(knox_id)
                if user:
                    return user
    except Exception:
        pass  # 세션 미들웨어 없으면 다음으로 진행

    # ── 헤더 기반 인증 (fallback) ─────────────────────────────────
    knox_id = request.headers.get("X-Knox-Id")
    if not knox_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 없습니다.",
        )

    repo = get_user_repository(use_mock=settings.USE_MOCK_DB)
    user = repo.get_user_by_knox_id(knox_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"사용자를 찾을 수 없습니다: {knox_id}",
        )
    return user
