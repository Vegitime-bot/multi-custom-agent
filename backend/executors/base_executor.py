from __future__ import annotations
"""
executors/base_executor.py - Executor 기반 클래스
공통 기능: RAG 검색, 메시지 구성, LLM 호출
"""
from abc import ABC, abstractmethod
from typing import Generator

from backend.core.models import ChatbotDef
from backend.llm.client import build_messages, stream_chat
from backend.retrieval.ingestion_client import IngestionClient, format_context


class BaseExecutor(ABC):
    """Executor 기반 클래스 - 공통 실행 기능 제공"""

    def __init__(self, chatbot_def: ChatbotDef, ingestion_client: IngestionClient):
        self.chatbot_def = chatbot_def
        self.ingestion = ingestion_client

    def _retrieve(self, query: str, db_ids: list[str]) -> str:
        """RAG 검색 - 공통 기능"""
        if not db_ids:
            return ""
        results = self.ingestion.search(
            db_ids=db_ids,
            query=query,
            k=self.chatbot_def.retrieval.k,
            filter_metadata=self.chatbot_def.retrieval.filter_metadata,
        )
        return format_context(results)

    def _build_messages(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> list[dict]:
        """메시지 구성 - 공통 기능"""
        return build_messages(
            system_prompt=system_prompt,
            history=[],  # Tool은 히스토리 없음
            user_message=user_message,
            context=context,
        )

    def _build_messages_with_history(
        self,
        system_prompt: str,
        history: list,
        user_message: str,
        context: str,
    ) -> list[dict]:
        """히스토리 포함 메시지 구성 - Agent용"""
        full_system = system_prompt
        if context and context.strip():
            full_system += f"\n\n## 참고 문서\n{context}"

        messages = [{"role": "system", "content": full_system}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_message})
        return messages

    def _stream_chat(self, messages: list[dict]) -> Generator[str, None, None]:
        """LLM 스트리밍 호출 - 공통 기능"""
        yield from stream_chat(self.chatbot_def, messages)

    @abstractmethod
    def execute(
        self,
        message: str,
        session_id: str | None = None,
    ) -> Generator[str, None, None]:
        """실행 - 하위 클래스에서 구현"""
        pass
