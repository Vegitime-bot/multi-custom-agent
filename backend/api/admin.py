"""
backend/api/admin.py - Admin 관리 API
챗봇 관리자 페이지용 REST API
"""
import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.responses import FileResponse, JSONResponse

from backend.managers.chatbot_manager import ChatbotManager
from backend.config import settings

router = APIRouter(tags=["admin"])

STATIC_DIR = Path(__file__).parent.parent.parent / "static" / "admin"


def get_chatbot_manager(request: Request) -> ChatbotManager:
    return request.app.state.chatbot_manager


# ── 관리자 권한 체크 ────────────────────────────────────────────
def require_admin(request: Request):
    """관리자 권한 체크 의존성"""
    # Mock Auth 모드에서는 항상 허용
    if settings.USE_MOCK_AUTH:
        return True
    
    # SSO 세션에서 사용자 ID 확인
    sso_data = request.session.get('sso')
    if not sso_data:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # SSO 데이터에서 knox_id 추출
    knox_id = None
    if isinstance(sso_data, dict):
        knox_id = sso_data.get('knox_id') or sso_data.get('email') or sso_data.get('sub')
    
    if not knox_id:
        raise HTTPException(status_code=401, detail="사용자 정보를 확인할 수 없습니다")
    
    # 관리자 ID 목록에 있는지 확인
    if knox_id not in settings.ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    return True


# ── 현재 사용자 정보 조회 ───────────────────────────────────────
@router.get("/main/api/me")
async def get_current_user_info(request: Request) -> dict:
    """현재 로그인한 사용자 정보 반환"""
    # Mock Auth
    if settings.USE_MOCK_AUTH:
        return {
            "knox_id": "user-001",
            "name": "Admin User",
            "role": "system_admin",
            "is_admin": True
        }
    
    # SSO
    sso_data = request.session.get('sso')
    if not sso_data:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    knox_id = None
    name = "Unknown"
    
    if isinstance(sso_data, dict):
        knox_id = sso_data.get('knox_id') or sso_data.get('email') or sso_data.get('sub')
        name = sso_data.get('name') or sso_data.get('display_name') or sso_data.get('preferred_username') or knox_id
    
    if not knox_id:
        raise HTTPException(status_code=401, detail="사용자 정보를 확인할 수 없습니다")
    
    is_admin = knox_id in settings.ADMIN_USER_IDS
    
    return {
        "knox_id": knox_id,
        "name": name,
        "is_admin": is_admin
    }


# ── 관리자 페이지 HTML ────────────────────────────────────────────
@router.get("/main")
async def admin_page():
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/main/")
async def admin_page_slash():
    return FileResponse(STATIC_DIR / "index.html")


# ── 챗봇 목록 ────────────────────────────────────────────────────
@router.get("/main/api/chatbots")
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
            "sub_chatbots": [{"id": s.id, "level": s.level, "default_role": s.default_role.value} for s in cb.sub_chatbots] if cb.sub_chatbots else [],
            "parent_id": cb.parent_id,
            "level": cb.level,
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
        
        if cb.policy:
            info["policy"] = cb.policy
        
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
@router.post("/main/api/chatbots")
async def create_chatbot(
    request: dict,
    req: Request,
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
    _: bool = Depends(require_admin),
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
        "policy": request.get("policy", {
            "temperature": 0.3,
            "max_tokens": 1024,
            "stream": True,
            "supported_modes": ["tool", "agent"],
            "default_mode": "agent",
            "max_messages": 20,
        }),
        "sub_chatbots": [],
    }

    # 3-tier hierarchy support: parent_id and level
    if request.get("parent_id") is not None:
        chatbot_json["parent_id"] = request["parent_id"]
    if "level" in request:
        chatbot_json["level"] = request["level"]

    # Validate max depth
    if request.get("level", 0) > 5:
        raise HTTPException(400, "Maximum hierarchy depth exceeded (max level: 5)")

    # sub_chatbots 처리 (객체 리스트 형태 지원)
    if "sub_chatbots" in request:
        sub_chatbots = []
        for sub in request["sub_chatbots"]:
            if isinstance(sub, dict):
                sub_chatbots.append({
                    "id": sub.get("id"),
                    "level": sub.get("level", 1),
                    "default_role": sub.get("default_role", "agent")
                })
            elif isinstance(sub, str):
                sub_chatbots.append(sub)
        chatbot_json["sub_chatbots"] = sub_chatbots

    # 하위 Agent → 상위 Agent JSON에 참조 추가 (type=child일 때)
    parent_id = request.get("parent") or request.get("parent_id")
    if (request.get("type") == "child" or request.get("parent_id")) and parent_id:
        parent_file = chatbots_dir / f"{parent_id}.json"
        if parent_file.exists():
            parent_data = json.loads(parent_file.read_text(encoding="utf-8"))
            if "sub_chatbots" not in parent_data:
                parent_data["sub_chatbots"] = []
            existing = [s["id"] if isinstance(s, dict) else s for s in parent_data["sub_chatbots"]]
            if request["id"] not in existing:
                level = request.get("level", 1)
                parent_data["sub_chatbots"].append(
                    {"id": request["id"], "level": level, "default_role": "agent"}
                )
                parent_file.write_text(
                    json.dumps(parent_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )

    file_path.write_text(json.dumps(chatbot_json, ensure_ascii=False, indent=2), encoding="utf-8")
    chatbot_mgr.reload()

    return {"status": "success", "id": request["id"]}


# ── 챗봇 수정 ────────────────────────────────────────────────────
@router.put("/main/api/chatbots/{chatbot_id}")
async def update_chatbot(
    chatbot_id: str,
    request: dict,
    req: Request,
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
    _: bool = Depends(require_admin),
) -> dict:
    """챗봇 정의를 수정한다."""
    chatbots_dir = chatbot_mgr._dir
    file_path = chatbots_dir / f"{chatbot_id}.json"
    
    if not file_path.exists():
        raise HTTPException(404, f"챗봇 '{chatbot_id}'를 찾을 수 없습니다")
    
    # 기존 데이터 로드
    existing_data = json.loads(file_path.read_text(encoding="utf-8"))
    
    # 새 데이터로 업데이트 (필드별 병합)
    updated_data = {
        "id": request.get("id", chatbot_id),
        "name": request.get("name", existing_data.get("name", "")),
        "description": request.get("description", existing_data.get("description", "")),
        "active": request.get("active", existing_data.get("active", True)),
        "capabilities": existing_data.get("capabilities", {}),
        "policy": existing_data.get("policy", {}),
        "sub_chatbots": [],
    }
    
    # capabilities 업데이트
    if "capabilities" in request:
        updated_data["capabilities"].update(request["capabilities"])
    
    # policy 업데이트
    if "policy" in request:
        updated_data["policy"].update(request["policy"])
    
    # sub_chatbots 처리 (객체 리스트 형태 지원)
    if "sub_chatbots" in request:
        sub_chatbots = []
        for sub in request["sub_chatbots"]:
            if isinstance(sub, dict):
                sub_chatbots.append({
                    "id": sub.get("id"),
                    "level": sub.get("level", 1),
                    "default_role": sub.get("default_role", "agent")
                })
            elif isinstance(sub, str):
                sub_chatbots.append(sub)
        updated_data["sub_chatbots"] = sub_chatbots
    else:
        updated_data["sub_chatbots"] = existing_data.get("sub_chatbots", [])
    
    # 3-tier hierarchy 필드
    if "parent_id" in request:
        updated_data["parent_id"] = request["parent_id"]
    elif "parent_id" in existing_data:
        updated_data["parent_id"] = existing_data["parent_id"]
    
    if "level" in request:
        updated_data["level"] = request["level"]
    elif "level" in existing_data:
        updated_data["level"] = existing_data["level"]
    
    # 파일 저장
    file_path.write_text(json.dumps(updated_data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # 메모리 상태 갱신
    chatbot_mgr.reload()
    
    return {"status": "success", "id": chatbot_id}


# ── 챗봘 삭제 ────────────────────────────────────────────────────
@router.delete("/main/api/chatbots/{chatbot_id}")
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
@router.get("/main/api/stats")
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


# ── DB 목록 ─────────────────────────────────────────────────────────
@router.get("/main/api/databases")
async def list_databases(
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
) -> List[str]:
    """
    모든 챗봇에서 사용 중인 DB ID 목록 반환
    """
    all_defs = chatbot_mgr.list_all()
    db_ids = set()
    
    for chatbot in all_defs:
        if chatbot.retrieval and chatbot.retrieval.db_ids:
            db_ids.update(chatbot.retrieval.db_ids)
    
    return sorted(list(db_ids))
