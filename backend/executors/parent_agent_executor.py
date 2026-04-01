from __future__ import annotations
"""
executors/parent_agent_executor.py - 상위 Agent Executor (위임 기능 포함)
신뢰도 기반으로 하위 Agent에게 위임하는 상위 Executor
"""
import re
from typing import Generator

from backend.core.models import ChatbotDef, ExecutionRole
from backend.executors.agent_executor import AgentExecutor
from backend.managers.memory_manager import MemoryManager
from backend.retrieval.ingestion_client import IngestionClient


class ParentAgentExecutor(AgentExecutor):
    """
    상위 Agent Executor
    - 먼저 자체 DB로 답변 시도
    - 신뢰도(confidence) 파싱
    - threshold 미만 시 하위 Agent에게 위임
    """

    def __init__(
        self,
        chatbot_def: ChatbotDef,
        ingestion_client: IngestionClient,
        memory_manager: MemoryManager,
        chatbot_manager=None,  # 하위 Agent 조회용
    ):
        super().__init__(chatbot_def, ingestion_client, memory_manager)
        self.chatbot_manager = chatbot_manager
        self.delegation_threshold = chatbot_def.policy.get('delegation_threshold', 70)

    def execute(
        self,
        message: str,
        session_id: str,
    ) -> Generator[str, None, None]:
        """
        상위 Agent 실행 + 위임 로직
        """
        # 1. 먼저 상위 Agent로 응답 생성
        full_response = []
        confidence = 0

        # 상위 Agent 응답 스트리밍
        for chunk in self._execute_parent(message, session_id):
            # Confidence 파싱
            if "CONFIDENCE:" in chunk:
                confidence = self._parse_confidence(chunk)
            full_response.append(chunk)
            yield chunk

        # 2. Confidence 체크 및 위임 결정
        if confidence < self.delegation_threshold and self.chatbot_def.sub_chatbots:
            # 하위 Agent 중 적합한 것 선택
            sub_chatbot = self._select_sub_chatbot(message)
            if sub_chatbot:
                yield f"\n\n---\n📡 **{sub_chatbot.name}에게 위임합니다...**\n\n"
                
                # 하위 Agent 실행
                for sub_chunk in self._delegate_to_sub(sub_chatbot, message, session_id):
                    yield sub_chunk

    def _execute_parent(
        self,
        message: str,
        session_id: str,
    ) -> Generator[str, None, None]:
        """상위 Agent 기본 실행 (부모 클래스 활용)"""
        # AgentExecutor의 기본 로직 사용
        history = self.memory.get_history(self.chatbot_def.id, session_id)
        context = self._retrieve(message, self.chatbot_def.retrieval.db_ids)

        messages = self._build_messages_with_history(
            system_prompt=self.chatbot_def.system_prompt,
            history=history,
            user_message=message,
            context=context,
        )

        full_response = []
        for chunk in self._stream_chat(messages):
            full_response.append(chunk)
            yield chunk

        # 상위 Agent 메모리 저장
        self.memory.append_pair(
            chatbot_id=self.chatbot_def.id,
            session_id=session_id,
            user_content=message,
            assistant_content="".join(full_response),
            max_messages=self.chatbot_def.memory.max_messages,
        )

    def _parse_confidence(self, text: str) -> int:
        """Confidence 값 파싱 (CONFIDENCE: XX 형식)"""
        match = re.search(r'CONFIDENCE:\s*(\d+)', text)
        if match:
            return int(match.group(1))
        return 0

    def _select_sub_chatbot(self, message: str) -> ChatbotDef | None:
        """질문 내용에 따라 적합한 하위 Agent 선택"""
        if not self.chatbot_manager:
            return None

        # 키워드 기반 매칭 (간단한 버전)
        keywords_map = {
            'chatbot-hr-policy': ['정책', '규정', '채용', '평가', '승진', '인사제도', '징계'],
            'chatbot-hr-benefit': ['급여', '연차', '휴가', '복지', '보험', '경조사', '교육지원'],
            'chatbot-tech-backend': ['backend', '백엔드', 'python', 'fastapi', 'django', 'db', 'sql', 'api'],
            'chatbot-tech-frontend': ['frontend', '프론트엔드', 'react', 'vue', 'javascript', 'css', 'html', 'ui'],
            'chatbot-tech-devops': ['devops', 'docker', 'kubernetes', 'k8s', 'ci/cd', 'infra', '배포', '모니터링'],
        }

        message_lower = message.lower()
        best_match = None
        best_score = 0

        for sub_ref in self.chatbot_def.sub_chatbots:
            sub_def = self.chatbot_manager.get_active(sub_ref.id)
            if not sub_def:
                continue

            # 키워드 매칭 점수 계산
            keywords = keywords_map.get(sub_ref.id, [])
            score = sum(1 for kw in keywords if kw.lower() in message_lower)

            if score > best_score:
                best_score = score
                best_match = sub_def

        # 매칭 없으면 첫 번째 하위 Agent 반환
        if not best_match and self.chatbot_def.sub_chatbots:
            first_id = self.chatbot_def.sub_chatbots[0].id
            best_match = self.chatbot_manager.get_active(first_id)

        return best_match

    def _delegate_to_sub(
        self,
        sub_chatbot: ChatbotDef,
        message: str,
        session_id: str,
    ) -> Generator[str, None, None]:
        """하위 Agent에게 위임 실행"""
        from backend.executors import AgentExecutor

        sub_executor = AgentExecutor(
            sub_chatbot,
            self.ingestion,
            self.memory
        )

        for chunk in sub_executor.execute(message, session_id):
            yield chunk
