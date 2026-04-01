from __future__ import annotations
"""
executors/agent_executor.py - Agent 모드 Executor
대화 주체처럼 실행: 메모리 유지, 대화형
"""
from typing import Generator

from backend.core.models import ChatbotDef, Message
from backend.executors.base_executor import BaseExecutor
from backend.managers.memory_manager import MemoryManager
from backend.retrieval.ingestion_client import IngestionClient


class AgentExecutor(BaseExecutor):
    """
    Agent 모드 Executor
    - 메모리 유지 (히스토리 저장)
    - 대화형 (세션 기반)
    - 사용자와 지속적 대화에 적합
    """

    def __init__(
        self,
        chatbot_def: ChatbotDef,
        ingestion_client: IngestionClient,
        memory_manager: MemoryManager,
    ):
        super().__init__(chatbot_def, ingestion_client)
        self.memory = memory_manager

    def execute(
        self,
        message: str,
        session_id: str,
    ) -> Generator[str, None, None]:
        """
        Agent 모드 실행
        
        Args:
            message: 사용자 입력
            session_id: 필수 (Agent는 세션 기반)
            
        Yields:
            LLM 응답 청크
        """
        # 1. 메모리에서 히스토리 복원
        history = self.memory.get_history(self.chatbot_def.id, session_id)

        # 2. RAG 검색 (DB 스코프 적용)
        context = self._retrieve(
            query=message,
            db_ids=self.chatbot_def.retrieval.db_ids,
        )

        # 2.5 Confidence 체크 - 검색 결과가 부족하거나 정책 질문인 경우 상위 Agent에게 위임 안내
        confidence = self._calculate_confidence(context, message)
        
        # 정책/규정 관련 키워드 체크
        policy_keywords = ['규정', '정책', '제도', '지침', '방침', '법규']
        is_policy_question = any(kw in message for kw in policy_keywords)
        
        if confidence < 20 or (is_policy_question and confidence < 50):
            fallback_msg = (
                "죄송합니다. 해당 내용은 제 전문 분야가 아닙니다. "
                "인사정책 전문 챗봘에게 문의해 주세요."
            )
            yield fallback_msg
            # 메모리에도 저장
            self.memory.append_pair(
                chatbot_id=self.chatbot_def.id,
                session_id=session_id,
                user_content=message,
                assistant_content=fallback_msg,
                max_messages=self.chatbot_def.memory.max_messages,
            )
            return

        # 3. 메시지 구성 (히스토리 포함 - Agent 특성)
        messages = self._build_messages_with_history(
            system_prompt=self.chatbot_def.system_prompt,
            history=history,
            user_message=message,
            context=context,
        )

        # 4. LLM 스트리밍 호출 + 메모리 저장
        full_response = []
        for chunk in self._stream_chat(messages):
            full_response.append(chunk)
            yield chunk

        # 5. 메모리 저장 (Agent 특성)
        self.memory.append_pair(
            chatbot_id=self.chatbot_def.id,
            session_id=session_id,
            user_content=message,
            assistant_content="".join(full_response),
            max_messages=self.chatbot_def.memory.max_messages,
        )
