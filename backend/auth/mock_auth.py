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
    - USE_MOCK_AUTH=false: Authorization 헤더의 knox_id 기반 DB 조회 (SSO TBD)
    """
    if settings.USE_MOCK_AUTH:
        return {"knox_id": "jyd1234", "name": "장영동", "team": "AI팀", "eng_name": "Youngdong Jang"}

    # ── 실제 SSO 연동 (TBD) ─────────────────────────────────────
    # 사내 OAuth SSO 방식 확인 후 구현 예정
    # 현재는 Authorization 헤더에서 knox_id를 직접 읽는 임시 방식 사용
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
