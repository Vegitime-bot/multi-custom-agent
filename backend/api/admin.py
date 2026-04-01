"""
backend/api/admin.py - Admin 관리 API
챗봇 관리자 페이지용 REST API
"""
import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.responses import FileResponse

from backend.managers.chatbot_manager import ChatbotManager

router = APIRouter(tags=["admin"])

STATIC_DIR = Path(__file__).parent.parent.parent / "static" / "admin"


def get_chatbot_manager(request: Request) -> ChatbotManager:
    return request.app.state.chatbot_manager


# ── 관리자 페이지 HTML ────────────────────────────────────────────
@router.get("/admin")
async def admin_page():
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/admin/")
async def admin_page_slash():
    return FileResponse(STATIC_DIR / "index.html")


# ── 챗봇 목록 ────────────────────────────────────────────────────
@router.get("/admin/api/chatbots")
async def list_chatbots(
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
) -> List[dict]:
    all_defs = chatbot_mgr.list_all()

    result = []
    for cb in all_defs:
        info = {
            "id": cb.id,
            "name": cb.name,
            "description": cb.description,
            "active": cb.active,
            "db_ids": cb.retrieval.db_ids,
            "sub_chatbots": [s.id for s in cb.sub_chatbots] if cb.sub_chatbots else [],
        }

        # 타입 결정
        if cb.sub_chatbots and len(cb.sub_chatbots) > 0:
            info["type"] = "parent"
        else:
            parent_id = _find_parent(cb.id, all_defs)
            if parent_id:
                info["type"] = "child"
                info["parent"] = parent_id
            else:
                info["type"] = "standalone"

        result.append(info)

    return result


from typing import Optional

def _find_parent(chatbot_id: str, all_defs) -> Optional[str]:
    for other in all_defs:
        if other.sub_chatbots:
            for sub in other.sub_chatbots:
                if sub.id == chatbot_id:
                    return other.id
    return None


# ── 챗봇 생성 ────────────────────────────────────────────────────
@router.post("/admin/api/chatbots")
async def create_chatbot(
    request: dict,
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
) -> dict:
    chatbots_dir = chatbot_mgr._dir
    file_path = chatbots_dir / f"{request['id']}.json"

    if file_path.exists():
        raise HTTPException(400, f"챗봇 ID '{request['id']}'가 이미 존재합니다")

    chatbot_json = {
        "id": request["id"],
        "name": request["name"],
        "description": request.get("description", ""),
        "active": request.get("active", True),
        "capabilities": {
            "db_ids": request.get("db_ids", []),
            "model": request.get("model", "kimi-k2.5:cloud"),
            "system_prompt": request.get("system_prompt", "당신은 도움이 되는 어시스턴트입니다."),
        },
        "policy": {
            "temperature": 0.3,
            "max_tokens": 1024,
            "stream": True,
            "supported_modes": ["tool", "agent"],
            "default_mode": "agent",
            "max_messages": 20,
        },
        "sub_chatbots": [],
    }

    # 하위 Agent → 상위 Agent JSON에 참조 추가
    if request.get("type") == "child" and request.get("parent"):
        parent_file = chatbots_dir / f"{request['parent']}.json"
        if parent_file.exists():
            parent_data = json.loads(parent_file.read_text(encoding="utf-8"))
            if "sub_chatbots" not in parent_data:
                parent_data["sub_chatbots"] = []
            existing = [s["id"] for s in parent_data["sub_chatbots"] if isinstance(s, dict)]
            if request["id"] not in existing:
                parent_data["sub_chatbots"].append(
                    {"id": request["id"], "level": 1, "default_role": "agent"}
                )
                parent_file.write_text(
                    json.dumps(parent_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )

    file_path.write_text(json.dumps(chatbot_json, ensure_ascii=False, indent=2), encoding="utf-8")
    chatbot_mgr.reload()

    return {"status": "success", "id": request["id"]}


# ── 챗봘 삭제 ────────────────────────────────────────────────────
@router.delete("/admin/api/chatbots/{chatbot_id}")
async def delete_chatbot(
    chatbot_id: str,
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
) -> dict:
    chatbots_dir = chatbot_mgr._dir

    # 다른 챗봘의 sub_chatbots에서 참조 제거
    for other_file in chatbots_dir.glob("*.json"):
        data = json.loads(other_file.read_text(encoding="utf-8"))
        if "sub_chatbots" in data:
            before = len(data["sub_chatbots"])
            data["sub_chatbots"] = [
                s for s in data["sub_chatbots"]
                if (isinstance(s, dict) and s.get("id") != chatbot_id)
                or (isinstance(s, str) and s != chatbot_id)
            ]
            if len(data["sub_chatbots"]) != before:
                other_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )

    if not chatbot_mgr.delete(chatbot_id):
        raise HTTPException(404, f"챗봇 '{chatbot_id}'를 찾을 수 없습니다")

    # 메모리 상태 완전 갱신 (다른 챗봘들의 sub_chatbots 참조 업데이트)
    chatbot_mgr.reload()

    return {"status": "success", "message": "삭제되었습니다"}


# ── 통계 ──────────────────────────────────────────────────────────
@router.get("/admin/api/stats")
async def get_stats(
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
) -> dict:
    all_defs = chatbot_mgr.list_all()
    parents = sum(1 for c in all_defs if c.sub_chatbots and len(c.sub_chatbots) > 0)
    return {
        "total": len(all_defs),
        "parents": parents,
        "active": sum(1 for c in all_defs if c.active),
    }
