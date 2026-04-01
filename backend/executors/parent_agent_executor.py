from __future__ import annotations
"""
executors/parent_agent_executor.py - 상위 Agent Executor (위임 기능 포함)
검색 결과 기반 신뢰도 계산 및 하위 Agent 위임
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
    - 검색 결과 기반 신뢰도(confidence) 계산
    - threshold 미만 시 하위 Agent에게 위임
    """

    def __init__(
        self,
        chatbot_def: ChatbotDef,
        ingestion_client: IngestionClient,
        memory_manager: MemoryManager,
        chatbot_manager=None,
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
        # 1. RAG 검색 수행
        context = self._retrieve(message, self.chatbot_def.retrieval.db_ids)
        
        # 2. 검색 결과 기반 Confidence 계산
        confidence = self._calculate_confidence(context, message)
        
        # 3. Confidence 체크 및 실행 결정
        if confidence < self.delegation_threshold and self.chatbot_def.sub_chatbots:
            # 위임 필요: 상위 Agent는 개요만 제공하고 하위에게 위임
            yield f"📋 이 질문은 전문가 상담이 필요합니다.\n\n"
            yield f"(상위 Agent 신뢰도: {confidence}% → 하위 Agent 위임)\n\n"
            yield f"---\n📡 **전문가 챗봇을 호출합니다...**\n\n"
            
            # 하위 Agent 실행
            sub_chatbot = self._select_sub_chatbot(message)
            if sub_chatbot:
                yield f"**[{sub_chatbot.name}]**\n\n"
                for sub_chunk in self._delegate_to_sub(sub_chatbot, message, session_id, context):
                    yield sub_chunk
            else:
                yield "❌ 적합한 하위 Agent를 찾을 수 없습니다.\n"
                # 대신 상위 Agent로 폴백
                for chunk in self._execute_with_context(message, session_id, context):
                    yield chunk
        else:
            # 위임 불필요: 상위 Agent가 직접 답변
            yield f"📢 **[{self.chatbot_def.name}]** (신뢰도: {confidence}%)\n\n"
            for chunk in self._execute_with_context(message, session_id, context):
                yield chunk

    def _calculate_confidence(self, context: str, message: str) -> int:
        """
        검색 결과 기반 Confidence 계산
        
        기준:
        - 검색 결과 없음: 0-20%
        - 검색 결과 있지만 관련도 낮음: 30-50%
        - 검색 결과 충분: 60-100%
        """
        if not context or not context.strip():
            return 15  # 검색 결과 없음
        
        # 검색 결과 분석
        result_count = context.count('---') + context.count('**') // 2
        content_length = len(context)
        
        # 메시지 키워드 매칭
        keywords_found = sum(1 for kw in message.split() if len(kw) > 1 and kw.lower() in context.lower())
        
        # Confidence 계산
        if result_count == 0 and content_length < 100:
            return 20  # 거의 관련 없음
        elif result_count <= 2 and keywords_found < 2:
            return 40  # 관련도 낮음
        elif result_count <= 3 and keywords_found < 3:
            return 60  # 보통
        else:
            return 85  # 충분한 정보

    def _execute_with_context(
        self,
        message: str,
        session_id: str,
        context: str,
    ) -> Generator[str, None, None]:
        """주어진 컨텍스트로 Agent 실행"""
        history = self.memory.get_history(self.chatbot_def.id, session_id)
        
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

        # 메모리 저장
        self.memory.append_pair(
            chatbot_id=self.chatbot_def.id,
            session_id=session_id,
            user_content=message,
            assistant_content="".join(full_response),
            max_messages=self.chatbot_def.memory.max_messages,
        )

    def _select_sub_chatbot(self, message: str) -> ChatbotDef | None:
        """질문 내용에 따라 적합한 하위 Agent 선택"""
        if not self.chatbot_manager:
            return None

        # 키워드 기반 매칭
        keywords_map = {
            'chatbot-hr-policy': ['정책', '규정', '채용', '평가', '승진', '인사제도', '징계', '인사', '제도'],
            'chatbot-hr-benefit': ['급여', '연차', '휴가', '복지', '보험', '경조사', '교육지원', '수당', '상여'],
            'chatbot-tech-backend': ['backend', '백엔드', 'python', 'fastapi', 'django', 'db', 'sql', 'api', '서버'],
            'chatbot-tech-frontend': ['frontend', '프론트엔드', 'react', 'vue', 'javascript', 'css', 'html', 'ui', '화면'],
            'chatbot-tech-devops': ['devops', 'docker', 'kubernetes', 'k8s', 'ci/cd', 'infra', '배포', '모니터링', '인프라'],
            'chatbot-rtl-verilog': ['rtl', 'verilog', 'fpga', '반도체', '디지털 회로', 'hdl', '합성'],
            'chatbot-rtl-synthesis': ['synthesis', '합성', '타이밍', '최적화', ' 면적 ', '전력'],
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
            score = sum(2 for kw in keywords if kw.lower() in message_lower)
            
            # 하위 챗봇 이름/설명에서도 매칭
            if sub_def.name.lower() in message_lower or any(kw in sub_def.description.lower() for kw in message_lower.split()):
                score += 3

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
        parent_context: str = "",
    ) -> Generator[str, None, None]:
        """하위 Agent에게 위임 실행"""
        from backend.executors import AgentExecutor

        # 상위 컨텍스트를 포함하여 하위 Agent 실행
        sub_executor = AgentExecutor(
            sub_chatbot,
            self.ingestion,
            self.memory
        )
        
        # 하위 Agent에 추가 컨텍스트 제공
        enhanced_message = message
        if parent_context:
            enhanced_message = f"[상위 Agent 컨텍스트] {parent_context[:500]}...\n\n[질문] {message}"

        for chunk in sub_executor.execute(enhanced_message, session_id):
            yield chunk
