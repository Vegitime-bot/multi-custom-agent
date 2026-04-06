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
    """
    # 🔍 디버깅: 요청 정보 로깅
    print(f"[AUTH DEBUG] get_current_user 호출됨")
    print(f"[AUTH DEBUG] USE_MOCK_AUTH: {settings.USE_MOCK_AUTH}")
    
    if settings.USE_MOCK_AUTH:
        print(f"[AUTH DEBUG] Mock 모드 - jyd1234 반환")
        return {"knox_id": "jyd1234", "name": "장영동", "team": "AI팀", "eng_name": "Youngdong Jang"}

    # ── 세션 기반 SSO 인증 ─────────────────────────────────────
    try:
        has_session = hasattr(request, 'session')
        print(f"[AUTH DEBUG] session 있음: {has_session}")
        
        if has_session:
            session_sso = request.session.get('sso')
            session_knox = request.session.get('knox_id')
            print(f"[AUTH DEBUG] session['sso']: {session_sso}")
            print(f"[AUTH DEBUG] session['knox_id']: {session_knox}")
            
            if session_sso and session_knox:
                print(f"[AUTH DEBUG] 세션 인증 성공 - knox_id: {session_knox}")
                repo = get_user_repository(use_mock=settings.USE_MOCK_DB)
                user = repo.get_user_by_knox_id(session_knox)
                if user:
                    print(f"[AUTH DEBUG] DB에서 사용자 찾음: {user.get('name', 'unknown')}")
                    return user
                else:
                    print(f"[AUTH DEBUG] DB에 사용자 없음, 임시 생성")
                    # DB에 없으면 세션 기반 임시 사용자 반환
                    return {
                        "knox_id": session_knox,
                        "name": request.session.get('user_info', {}).get('name', 'Unknown'),
                        "team": "AI팀",
                    }
    except Exception as e:
        print(f"[AUTH DEBUG] 세션 확인 중 오류: {e}")

    # ── 헤더 기반 인증 ───────────────────────────────────────────
    knox_id = request.headers.get("X-Knox-Id")
    print(f"[AUTH DEBUG] X-Knox-Id 헤더: {knox_id}")
    
    if not knox_id:
        print(f"[AUTH DEBUG] ❌ 인증 실패 - 세션도 헤더도 없음")
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
