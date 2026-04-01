from __future__ import annotations
"""
executors/parent_agent_executor.py - 상위 Agent Executor (위임 기능 포함)
검색 결과 기반 신뢰도 계산 및 하위 Agent 위임
v2: 키워드 매칭 → 키워드 + 임베딩(코사인 유사도) 하이브리드 선택
"""
import re
from typing import Generator, Optional, List, Tuple

from backend.core.models import ChatbotDef, ExecutionRole
from backend.executors.agent_executor import AgentExecutor
from backend.managers.memory_manager import MemoryManager
from backend.retrieval.ingestion_client import IngestionClient
from backend.services.embedding_service import get_embedding_service


class ParentAgentExecutor(AgentExecutor):
    """
    상위 Agent Executor
    - 먼저 자체 DB로 답변 시도
    - 검색 결과 기반 신뢰도(confidence) 계산
    - threshold 미만 시 하위 Agent에게 위임
    - v2: 하위 Agent 선택에 임베딩 기반 코사인 유사도 사용
    """

    # 키워드 기반 매칭 (하위 호환 유지)
    KEYWORDS_MAP = {
        'chatbot-hr-policy': ['정책', '규정', '채용', '평가', '승진', '인사제도', '징계', '인사', '제도'],
        'chatbot-hr-benefit': ['급여', '연차', '휴가', '복지', '보험', '경조사', '교육지원', '수당', '상여'],
        'chatbot-tech-backend': ['backend', '백엔드', 'python', 'fastapi', 'django', 'db', 'sql', 'api', '서버'],
        'chatbot-tech-frontend': ['frontend', '프론트엔드', 'react', 'vue', 'javascript', 'css', 'html', 'ui', '화면'],
        'chatbot-tech-devops': ['devops', 'docker', 'kubernetes', 'k8s', 'ci/cd', 'infra', '배포', '모니터링', '인프라'],
        'chatbot-rtl-verilog': ['rtl', 'verilog', 'fpga', '반도체', '디지털 회로', 'hdl', '합성'],
        'chatbot-rtl-synthesis': ['synthesis', '합성', '타이밍', '최적화', '면적', '전력'],
    }

    # 하이브리드 가중치 (keyword : embedding)
    KEYWORD_WEIGHT = 0.4
    EMBEDDING_WEIGHT = 0.6

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
        self._embedding_service = get_embedding_service()

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
            # 위임 필요
            yield f"📋 이 질문은 전문가 상담이 필요합니다.\n\n"
            yield f"(상위 Agent 신뢰도: {confidence}% → 하위 Agent 위임)\n\n"
            yield f"---\n📡 **전문가 챗봇을 호출합니다...**\n\n"
            
            # 하위 Agent 실행 (하이브리드 선택)
            sub_chatbot, selection_info = self._select_sub_chatbot_hybrid(message)
            if sub_chatbot:
                yield f"**[{sub_chatbot.name}]** {selection_info}\n\n"
                for sub_chunk in self._delegate_to_sub(sub_chatbot, message, session_id, context):
                    yield sub_chunk
            else:
                yield "❌ 적합한 하위 Agent를 찾을 수 없습니다.\n"
                for chunk in self._execute_with_context(message, session_id, context):
                    yield chunk
        else:
            # 위임 불필요
            yield f"📢 **[{self.chatbot_def.name}]** (신뢰도: {confidence}%)\n\n"
            for chunk in self._execute_with_context(message, session_id, context):
                yield chunk

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

    # ====================================================================
    # v1: 기존 키워드 기반 선택 (하위호환 유지)
    # ====================================================================
    def _select_sub_chatbot(self, message: str) -> Optional[ChatbotDef]:
        """키워드 기반 하위 Agent 선택 (레거시)"""
        result, _ = self._select_sub_chatbot_hybrid(message)
        return result

    # ====================================================================
    # v2: 하이브리드 선택 (키워드 + 임베딩 코사인 유사도)
    # ====================================================================
    def _select_sub_chatbot_hybrid(self, message: str) -> Tuple[Optional[ChatbotDef], str]:
        """
        하이브리드 하위 Agent 선택
        
        1단계: 키워드 점수 (0~1 정규화)
        2단계: 임베딩 코사인 유사도 (0~1)
        3단계: 가중 평균 = keyword_weight * kw_score + embedding_weight * emb_score
        
        Returns:
            (선택된 ChatbotDef, 선택 정보 문자열)
        """
        if not self.chatbot_manager:
            return None, ""

        candidates = []
        
        for sub_ref in self.chatbot_def.sub_chatbots:
            sub_def = self.chatbot_manager.get_active(sub_ref.id)
            if not sub_def:
                continue
            candidates.append(sub_def)

        if not candidates:
            return None, ""

        message_lower = message.lower()
        scores = []

        for sub_def in candidates:
            # --- 키워드 점수 ---
            kw_score = self._keyword_score(sub_def.id, message_lower)
            
            # --- 임베딩 유사도 ---
            emb_score = self._embedding_score(message, sub_def)
            
            # --- 하이브리드 점수 ---
            hybrid = self.KEYWORD_WEIGHT * kw_score + self.EMBEDDING_WEIGHT * emb_score
            
            scores.append({
                'chatbot': sub_def,
                'keyword': round(kw_score, 3),
                'embedding': round(emb_score, 3),
                'hybrid': round(hybrid, 3),
            })

        # 하이브리드 점수 기준 내림차순
        scores.sort(key=lambda x: x['hybrid'], reverse=True)
        
        best = scores[0]
        info = f"(kw:{best['keyword']}, emb:{best['embedding']}, hybrid:{best['hybrid']})"
        
        return best['chatbot'], info

    def _keyword_score(self, chatbot_id: str, message_lower: str) -> float:
        """키워드 매칭 점수 (0~1 정규화)"""
        keywords = self.KEYWORDS_MAP.get(chatbot_id, [])
        if not keywords:
            return 0.0
        
        matched = sum(1 for kw in keywords if kw.lower() in message_lower)
        # 정규화: 매칭된 키워드 / 전체 키워드 수
        return min(matched / max(len(keywords) * 0.3, 1), 1.0)

    def _embedding_score(self, message: str, sub_def: ChatbotDef) -> float:
        """임베딩 코사인 유사도 점수 (0~1)"""
        # 하위 Agent의 "프로파일 텍스트" 생성
        profile_parts = [sub_def.name, sub_def.description]
        
        # 키워드도 프로파일에 포함
        keywords = self.KEYWORDS_MAP.get(sub_def.id, [])
        if keywords:
            profile_parts.append(' '.join(keywords))
        
        # 시스템 프롬프트의 첫 200자
        if sub_def.system_prompt:
            profile_parts.append(sub_def.system_prompt[:200])
        
        profile_text = ' '.join(profile_parts)
        
        return self._embedding_service.cosine_similarity(message, profile_text)

    # ====================================================================
    # 위임 실행
    # ====================================================================
    def _delegate_to_sub(
        self,
        sub_chatbot: ChatbotDef,
        message: str,
        session_id: str,
        parent_context: str = "",
    ) -> Generator[str, None, None]:
        """하위 Agent에게 위임 실행"""
        from backend.executors import AgentExecutor

        sub_executor = AgentExecutor(
            sub_chatbot,
            self.ingestion,
            self.memory
        )
        
        enhanced_message = message
        if parent_context:
            enhanced_message = f"[상위 Agent 컨텍스트] {parent_context[:500]}...\n\n[질문] {message}"

        for chunk in sub_executor.execute(enhanced_message, session_id):
            yield chunk
