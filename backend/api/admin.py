from __future__ import annotations
"""
api/admin.py - 관리자 API
챗봇 정의 CRUD 및 사용자 조회 엔드포인트를 제공한다.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.auth.mock_auth import get_current_user
from backend.core.models import ChatbotDef
from backend.managers.chatbot_manager import ChatbotManager

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Pydantic 요청 스키마 ───────────────────────────────────────────
class ChatbotCreateRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    role: str = "agent"
    active: bool = True
    retrieval: dict
    llm: dict
    memory: dict
    system_prompt: str = ""
    sub_chatbots: list = []


# ── 의존성: ChatbotManager는 app state에서 주입 ──────────────────
def get_chatbot_manager(request: Request) -> ChatbotManager:
    return request.app.state.chatbot_manager


def get_current_admin(request: Request) -> dict:
    """관리자 권한 확인 (현재는 인증만 수행, 추후 role 체크 추가)"""
    return get_current_user(request)


# ── 챗봇 목록 조회 ───────────────────────────────────────────────
@router.get("/chatbots")
def list_chatbots(
    manager: ChatbotManager = Depends(get_chatbot_manager),
    _user: dict = Depends(get_current_admin),
):
    return [c.to_dict() for c in manager.list_all()]


# ── 챗봇 단건 조회 ───────────────────────────────────────────────
@router.get("/chatbots/{chatbot_id}")
def get_chatbot(
    chatbot_id: str,
    manager: ChatbotManager = Depends(get_chatbot_manager),
    _user: dict = Depends(get_current_admin),
):
    chatbot = manager.get(chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail=f"챗봇을 찾을 수 없습니다: {chatbot_id}")
    return chatbot.to_dict()


# ── 챗봇 등록/수정 ───────────────────────────────────────────────
@router.post("/chatbots", status_code=status.HTTP_201_CREATED)
def create_chatbot(
    body: ChatbotCreateRequest,
    manager: ChatbotManager = Depends(get_chatbot_manager),
    _user: dict = Depends(get_current_admin),
):
    try:
        chatbot = ChatbotDef.from_dict(body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"챗봇 정의 오류: {e}")
    manager.save(chatbot)
    return chatbot.to_dict()


@router.put("/chatbots/{chatbot_id}")
def update_chatbot(
    chatbot_id: str,
    body: ChatbotCreateRequest,
    manager: ChatbotManager = Depends(get_chatbot_manager),
    _user: dict = Depends(get_current_admin),
):
    data = body.model_dump()
    data["id"] = chatbot_id
    try:
        chatbot = ChatbotDef.from_dict(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"챗봇 정의 오류: {e}")
    manager.save(chatbot)
    return chatbot.to_dict()


# ── 챗봇 삭제 ────────────────────────────────────────────────────
@router.delete("/chatbots/{chatbot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chatbot(
    chatbot_id: str,
    manager: ChatbotManager = Depends(get_chatbot_manager),
    _user: dict = Depends(get_current_admin),
):
    if not manager.delete(chatbot_id):
        raise HTTPException(status_code=404, detail=f"챗봇을 찾을 수 없습니다: {chatbot_id}")


# ── 챗봇 재로드 ──────────────────────────────────────────────────
@router.post("/chatbots/reload")
def reload_chatbots(
    manager: ChatbotManager = Depends(get_chatbot_manager),
    _user: dict = Depends(get_current_admin),
):
    manager.reload()
    return {"message": "챗봇 정의를 다시 불러왔습니다.", "count": len(manager.list_all())}
