from __future__ import annotations
"""
managers/session_manager.py - 세션 관리
세션 생성/조회/종료와 세션별 역할 오버라이드를 관리한다.
현재 인메모리 구현 (향후 Redis/DB로 교체 가능).
"""
import uuid
from backend.core.models import ChatSession, ExecutionRole


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}

    def create_session(
        self,
        chatbot_id: str,
        user_knox_id: str,
        session_id: str | None = None,
        role_override: dict[str, str] | None = None,
        active_level: int = 1,
    ) -> ChatSession:
        sid = session_id or str(uuid.uuid4())
        overrides: dict[str, ExecutionRole] = {}
        if role_override:
            for bot_id, role_str in role_override.items():
                overrides[bot_id] = ExecutionRole(role_str)

        session = ChatSession(
            session_id=sid,
            chatbot_id=chatbot_id,
            user_knox_id=user_knox_id,
            role_override=overrides,
            active_level=active_level,
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def get_or_create(
        self,
        chatbot_id: str,
        user_knox_id: str,
        session_id: str | None = None,
    ) -> ChatSession:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.create_session(
            chatbot_id=chatbot_id,
            user_knox_id=user_knox_id,
            session_id=session_id,
        )

    def close_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self, user_knox_id: str | None = None) -> list[dict]:
        sessions = self._sessions.values()
        if user_knox_id:
            sessions = [s for s in sessions if s.user_knox_id == user_knox_id]
        return [s.to_dict() for s in sessions]
