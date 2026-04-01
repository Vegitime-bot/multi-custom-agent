"""
backend/api/permissions.py - 권한 관리 API
사용자-챗봘 권한 CRUD API
"""
from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel

from backend.auth.mock_auth import get_current_user
from backend.config import settings
from backend.permissions.repository import (
    get_permission_repository,
    PermissionRepository,
    MockPermissionRepository,
)
from backend.managers.chatbot_manager import ChatbotManager
from backend.api.deps import get_chatbot_manager

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


# ── 요청/응답 스키마 ───────────────────────────────────────────────
class PermissionCreate(BaseModel):
    knox_id: str
    chatbot_id: str
    can_access: bool = True


class PermissionUpdate(BaseModel):
    can_access: bool


class PermissionResponse(BaseModel):
    id: int
    knox_id: str
    chatbot_id: str
    can_access: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class UserPermissionsResponse(BaseModel):
    knox_id: str
    permissions: List[PermissionResponse]
    total: int
    accessible_count: int


class ChatbotUsersResponse(BaseModel):
    chatbot_id: str
    users: List[dict]
    total: int


# ── 의존성 주입 ───────────────────────────────────────────────────
def get_perm_repo() -> PermissionRepository:
    """설정에 따라 Mock 또는 PG Repository 반환"""
    return get_permission_repository(use_mock=settings.USE_MOCK_DB)


# ── API 엔드포인트 ────────────────────────────────────────────────
@router.get("/users/{knox_id}", response_model=UserPermissionsResponse)
async def get_user_permissions(
    knox_id: str,
    repo: PermissionRepository = Depends(get_perm_repo),
    current_user: dict = Depends(get_current_user),
):
    """
    특정 사용자의 모든 챗봘 권한 조회
    - 자신의 권한만 조회 가능 (관리자 제외)
    """
    # TODO: 관리자 권한 체크 추가
    # if current_user["knox_id"] != knox_id and not is_admin(current_user):
    #     raise HTTPException(403, "권한이 없습니다")

    perms = repo.get_user_permissions(knox_id)
    accessible = [p for p in perms if p["can_access"]]

    return UserPermissionsResponse(
        knox_id=knox_id,
        permissions=[PermissionResponse(**p) for p in perms],
        total=len(perms),
        accessible_count=len(accessible),
    )


@router.get("/check/{chatbot_id}")
async def check_permission(
    chatbot_id: str,
    repo: PermissionRepository = Depends(get_perm_repo),
    current_user: dict = Depends(get_current_user),
):
    """현재 사용자의 특정 챗봘 접근 권한 확인"""
    has_access = repo.check_access(current_user["knox_id"], chatbot_id)

    return {
        "knox_id": current_user["knox_id"],
        "chatbot_id": chatbot_id,
        "has_access": has_access,
    }


@router.post("/", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def grant_permission(
    data: PermissionCreate,
    repo: PermissionRepository = Depends(get_perm_repo),
    current_user: dict = Depends(get_current_user),
):
    """권한 부여 (새로 생성 또는 수정)"""
    # TODO: 관리자 권한 체크

    success = repo.grant_access(data.knox_id, data.chatbot_id, data.can_access)
    if not success:
        raise HTTPException(500, "권한 설정에 실패했습니다")

    # 생성된 권한 반환
    perms = repo.get_user_permissions(data.knox_id)
    for p in perms:
        if p["chatbot_id"] == data.chatbot_id:
            return PermissionResponse(**p)

    raise HTTPException(500, "권한 생성 후 조회 실패")


@router.put("/{knox_id}/{chatbot_id}", response_model=PermissionResponse)
async def update_permission(
    knox_id: str,
    chatbot_id: str,
    data: PermissionUpdate,
    repo: PermissionRepository = Depends(get_perm_repo),
    current_user: dict = Depends(get_current_user),
):
    """권한 수정 (can_access 값 변경)"""
    # TODO: 관리자 권한 체크

    success = repo.grant_access(knox_id, chatbot_id, data.can_access)
    if not success:
        raise HTTPException(500, "권한 수정에 실패했습니다")

    perms = repo.get_user_permissions(knox_id)
    for p in perms:
        if p["chatbot_id"] == chatbot_id:
            return PermissionResponse(**p)

    raise HTTPException(404, "권한을 찾을 수 없습니다")


@router.delete("/{knox_id}/{chatbot_id}")
async def revoke_permission(
    knox_id: str,
    chatbot_id: str,
    repo: PermissionRepository = Depends(get_perm_repo),
    current_user: dict = Depends(get_current_user),
):
    """권한 완전 삭제"""
    # TODO: 관리자 권한 체크

    success = repo.revoke_access(knox_id, chatbot_id)
    if not success:
        raise HTTPException(404, "권한을 찾을 수 없습니다")

    return {"status": "success", "message": "권한이 삭제되었습니다"}


@router.get("/chatbots/{chatbot_id}/users", response_model=ChatbotUsersResponse)
async def get_chatbot_users(
    chatbot_id: str,
    repo: PermissionRepository = Depends(get_perm_repo),
    current_user: dict = Depends(get_current_user),
):
    """특정 챗봘에 접근 가능한 사용자 목록"""
    users = repo.get_chatbot_users(chatbot_id)

    return ChatbotUsersResponse(
        chatbot_id=chatbot_id,
        users=users,
        total=len(users),
    )


@router.get("/")
async def list_all_permissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    repo: PermissionRepository = Depends(get_perm_repo),
    current_user: dict = Depends(get_current_user),
):
    """전체 권한 목록 (관리자용)"""
    # TODO: 관리자 권한 체크

    perms = repo.get_all_permissions(skip, limit)
    return {
        "permissions": [PermissionResponse(**p) for p in perms],
        "skip": skip,
        "limit": limit,
        "total_returned": len(perms),
    }


@router.post("/bulk")
async def bulk_grant_permissions(
    knox_id: str,
    chatbot_ids: List[str],
    can_access: bool = True,
    repo: PermissionRepository = Depends(get_perm_repo),
    current_user: dict = Depends(get_current_user),
):
    """일괄 권한 부여 (여러 챗봘에 동시 권한 설정)"""
    # TODO: 관리자 권한 체크

    results = []
    for chatbot_id in chatbot_ids:
        success = repo.grant_access(knox_id, chatbot_id, can_access)
        results.append({"chatbot_id": chatbot_id, "success": success})

    success_count = sum(1 for r in results if r["success"])
    return {
        "status": "success",
        "knox_id": knox_id,
        "total": len(chatbot_ids),
        "success_count": success_count,
        "results": results,
    }


# ── 관리자용 통계 API ────────────────────────────────────────────
@router.get("/admin/stats")
async def get_permission_stats(
    repo: PermissionRepository = Depends(get_perm_repo),
    chatbot_mgr: ChatbotManager = Depends(get_chatbot_manager),
    current_user: dict = Depends(get_current_user),
):
    """권한 통계 (관리자용)"""
    # TODO: 관리자 권한 체크

    all_perms = repo.get_all_permissions(skip=0, limit=10000)

    # 사용자별 통계
    user_stats = {}
    for p in all_perms:
        knox_id = p["knox_id"]
        if knox_id not in user_stats:
            user_stats[knox_id] = {"total": 0, "accessible": 0}
        user_stats[knox_id]["total"] += 1
        if p["can_access"]:
            user_stats[knox_id]["accessible"] += 1

    # 챗봘별 통계
    chatbot_stats = {}
    all_chatbots = chatbot_mgr.list_all()
    for cb in all_chatbots:
        chatbot_stats[cb.id] = {"name": cb.name, "users": 0, "access_count": 0}

    for p in all_perms:
        cb_id = p["chatbot_id"]
        if cb_id in chatbot_stats:
            chatbot_stats[cb_id]["users"] += 1
            if p["can_access"]:
                chatbot_stats[cb_id]["access_count"] += 1

    return {
        "total_permissions": len(all_perms),
        "unique_users": len(user_stats),
        "unique_chatbots": len(chatbot_stats),
        "user_stats": user_stats,
        "chatbot_stats": chatbot_stats,
    }
