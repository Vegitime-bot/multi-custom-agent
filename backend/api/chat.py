from __future__ import annotations
"""
api/chat.py - 채팅 API + SSE 스트리밍
요청 실행 라이프사이클:
1. 챗봇 정의 조회
2. 사용자 인증 + 권한 검사
3. 세션 확인/생성
4. Factory → ExecutionContext 생성
5. Role Router → 핸들러 선택
6. 검색 + LLM 스트리밍
7. 메모리 저장
"""
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.auth.mock_auth import get_current_user
from backend.config import settings
from backend.core.factory import create_execution_context
from backend.core.models import Message
from backend.managers.chatbot_manager import ChatbotManager
from backend.managers.memory_manager import MemoryManager
from backend.managers.session_manager import SessionManager
from backend.roles.router import RoleRouter

router = APIRouter(prefix="/api", tags=["chat"])


# ── 요청 스키마 ────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    chatbot_id: str
    message: str
    session_id: str | None = None
    role_override: dict[str, str] | None = None
    active_level: int = 1


class SessionCreateRequest(BaseModel):
    chatbot_id: str
    session_id: str | None = None
    role_override: dict[str, str] | None = None
    active_level: int = 1


# ── 의존성 ─────────────────────────────────────────────────────────
def get_chatbot_manager(request: Request) -> ChatbotManager:
    return request.app.state.chatbot_manager

def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager

def get_memory_manager(request: Request) -> MemoryManager:
    return request.app.state.memory_manager

def get_role_router(request: Request) -> RoleRouter:
    return request.app.state.role_router


# ── 사용자 DB 스코프 (임시: 모든 DB 허용, 운영 시 PostgreSQL 기반으로 교체) ──
def get_user_db_scope(user: dict) -> set[str]:
    """
    사용자에게 허용된 db_ids를 반환한다.
    현재는 Mock으로 모든 DB 허용.
    운영 환경에서는 PostgreSQL users_db_scope 테이블에서 조회한다.
    """
    if settings.USE_MOCK_AUTH:
        # Mock: 모든 DB에 접근 허용
        return {"db_001", "db_002", "db_003", "db_004", "db_005"}
    # TODO: PostgreSQL에서 사용자별 db_scope 조회
    return set()


# ── SSE 헬퍼 ──────────────────────────────────────────────────────
def sse_event(data: str, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_done() -> str:
    return "event: done\ndata: {}\n\n"


def sse_error(message: str) -> str:
    return f"event: error\ndata: {json.dumps({'error': message}, ensure_ascii=False)}\n\n"


# ── 챗봇 목록 (활성) ──────────────────────────────────────────────
@router.get("/chatbots")
def list_active_chatbots(
    manager: ChatbotManager = Depends(get_chatbot_manager),
    _user: dict = Depends(lambda req: get_current_user(req)),
    request: Request = None,
):
    return [
        {"id": c.id, "name": c.name, "description": c.description, "role": c.role.value}
        for c in manager.list_active()
    ]


# ── 세션 생성 ─────────────────────────────────────────────────────
@router.post("/sessions")
def create_session(
    body: SessionCreateRequest,
    request: Request,
    session_mgr: SessionManager = Depends(get_session_manager),
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
):
    user = get_current_user(request)
    chatbot = chatbot_mgr.get_active(body.chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail=f"활성 챗봇을 찾을 수 없습니다: {body.chatbot_id}")

    session = session_mgr.create_session(
        chatbot_id=body.chatbot_id,
        user_knox_id=user["knox_id"],
        session_id=body.session_id,
        role_override=body.role_override,
        active_level=body.active_level,
    )
    return session.to_dict()


# ── 채팅 (SSE 스트리밍) ───────────────────────────────────────────
@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
    session_mgr: SessionManager = Depends(get_session_manager),
    memory_mgr: MemoryManager = Depends(get_memory_manager),
    role_router: RoleRouter = Depends(get_role_router),
):
    user = get_current_user(request)

    # 1. 챗봇 정의 조회
    chatbot_def = chatbot_mgr.get_active(body.chatbot_id)
    if not chatbot_def:
        raise HTTPException(status_code=404, detail=f"활성 챗봇을 찾을 수 없습니다: {body.chatbot_id}")

    # 2. 세션 확인/생성
    session = session_mgr.get_or_create(
        chatbot_id=body.chatbot_id,
        user_knox_id=user["knox_id"],
        session_id=body.session_id,
    )
    if body.role_override:
        from backend.core.models import ExecutionRole
        for bot_id, role_str in body.role_override.items():
            session.role_override[bot_id] = ExecutionRole(role_str)

    # 3. 사용자 DB 스코프
    user_db_scope = get_user_db_scope(user)

    # 4. ExecutionContext 생성 (Factory)
    context = create_execution_context(
        chatbot_def=chatbot_def,
        session=session,
        user_db_scope=user_db_scope,
        memory_manager=memory_mgr,
    )

    # 5. 역할에 맞는 핸들러 선택
    handler = role_router.resolve(context.effective_role)

    # 6. SSE 스트리밍 응답 생성
    async def event_generator() -> AsyncGenerator[str, None]:
        full_response = []
        try:
            for chunk in handler.stream(context, body.message):
                full_response.append(chunk)
                yield sse_event(chunk)
        except Exception as e:
            yield sse_error(str(e))
            return

        # 7. 메모리 저장 (스트리밍 완료 후)
        if chatbot_def.memory.enabled:
            memory_mgr.append_pair(
                chatbot_id=chatbot_def.id,
                session_id=session.session_id,
                user_content=body.message,
                assistant_content="".join(full_response),
                max_messages=chatbot_def.memory.max_messages,
            )

        yield sse_event(session.session_id, event="session_id")
        yield sse_done()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── 대화 기록 조회 ────────────────────────────────────────────────
@router.get("/sessions/{session_id}/history")
def get_history(
    session_id: str,
    chatbot_id: str,
    request: Request,
    memory_mgr: MemoryManager = Depends(get_memory_manager),
):
    get_current_user(request)
    history = memory_mgr.get_history(chatbot_id=chatbot_id, session_id=session_id)
    return [m.to_dict() for m in history]


# ── 세션 종료 ─────────────────────────────────────────────────────
@router.delete("/sessions/{session_id}")
def close_session(
    session_id: str,
    request: Request,
    session_mgr: SessionManager = Depends(get_session_manager),
    memory_mgr: MemoryManager = Depends(get_memory_manager),
):
    get_current_user(request)
    memory_mgr.clear_all_for_session(session_id)
    session_mgr.close_session(session_id)
    return {"message": f"세션 {session_id} 종료 완료"}
