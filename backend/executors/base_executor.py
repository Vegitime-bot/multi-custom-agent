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

    def _calculate_confidence(self, context: str, message: str) -> int:
        """
        검색 결과 기반 Confidence 계산 (개선된 버전)
        
        기준:
        - 검색 결과 없음: 10-20%
        - 검색 결과 있지만 관련도 낮음: 30-50%
        - 검색 결과 충분: 60-95%
        """
        if not context or not context.strip():
            return 10  # 검색 결과 없음
        
        content_length = len(context)
        message_words = [kw.lower() for kw in message.split() if len(kw) > 1]
        context_lower = context.lower()
        
        # 키워드 매칭 (중복 제거)
        keywords_found = sum(1 for kw in set(message_words) if kw in context_lower)
        keyword_match_ratio = keywords_found / len(message_words) if message_words else 0
        
        # 컨텍스트 정보 밀도 (문서당 평균 길이 추정)
        # 일반적으로 검색 결과는 ### 구분자로 문서가 구분됨
        doc_count = context.count('###') + context.count('---') + 1
        avg_doc_length = content_length / doc_count if doc_count > 0 else content_length
        
        # 점수 계산 (가중치 조합)
        # content_length: 0~40점 (0자~5000자 기준)
        length_score = min(40, content_length / 125)
        
        # keyword_match_ratio: 0~30점
        keyword_score = keyword_match_ratio * 30
        
        # avg_doc_length: 0~25점 (짧은 문서는 정보 밀도 낮음으로 간주)
        density_score = min(25, avg_doc_length / 40)
        
        total_score = int(length_score + keyword_score + density_score)
        
        # 보넘스/페널티
        if keyword_match_ratio >= 0.7:
            total_score += 10  # 높은 키워드 매칭 보너스
        elif keyword_match_ratio < 0.2:
            total_score -= 10  # 낮은 키워드 매칭 페널티
        
        # 범위 클리핑
        return max(15, min(95, total_score))

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
