from __future__ import annotations
"""
managers/chatbot_manager.py - 챗봇 정의 관리
chatbots/*.json 파일을 읽어 ChatbotDef 객체로 관리한다.
선언형 등록 원칙: JSON 파일 추가/삭제만으로 챗봇을 추가/제거할 수 있다.
"""
import json
from pathlib import Path

from backend.core.models import ChatbotDef
from backend.config import settings


class ChatbotManager:
    def __init__(self, chatbots_dir: Path | None = None):
        self._dir = chatbots_dir or settings.CHATBOTS_DIR
        self._chatbots: dict[str, ChatbotDef] = {}
        self._load_all()

    # ── 로딩 ──────────────────────────────────────────────────────
    def _load_all(self) -> None:
        self._chatbots.clear()
        for json_file in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                chatbot = ChatbotDef.from_dict(data)
                self._chatbots[chatbot.id] = chatbot
            except Exception as e:
                print(f"[ChatbotManager] {json_file.name} 로드 실패: {e}")

    def reload(self) -> None:
        """런타임 중 챗봇 정의를 다시 불러온다."""
        self._load_all()

    # ── 조회 ──────────────────────────────────────────────────────
    def get(self, chatbot_id: str) -> ChatbotDef | None:
        return self._chatbots.get(chatbot_id)

    def get_active(self, chatbot_id: str) -> ChatbotDef | None:
        chatbot = self._chatbots.get(chatbot_id)
        return chatbot if (chatbot and chatbot.active) else None

    def list_all(self) -> list[ChatbotDef]:
        return list(self._chatbots.values())

    def list_active(self) -> list[ChatbotDef]:
        return [c for c in self._chatbots.values() if c.active]

    # ── 쓰기 (선언형 등록 지원) ─────────────────────────────────
    def save(self, chatbot: ChatbotDef) -> None:
        """챗봇 정의를 JSON 파일로 저장하고 인메모리 상태를 갱신한다."""
        file_path = self._dir / f"{chatbot.id}.json"
        file_path.write_text(
            json.dumps(chatbot.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._chatbots[chatbot.id] = chatbot

    def delete(self, chatbot_id: str) -> bool:
        """챗봇 정의 파일을 삭제한다. 성공 여부를 반환한다."""
        file_path = self._dir / f"{chatbot_id}.json"
        if file_path.exists():
            file_path.unlink()
            self._chatbots.pop(chatbot_id, None)
            return True
        return False
