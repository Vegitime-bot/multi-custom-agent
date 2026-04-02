from __future__ import annotations
"""
executors/hierarchical_agent_executor.py - 계층적 Agent Executor (3-tier hierarchy 지원)

계층 구조에서 상위로 위임하는 기능 추가:
- Confidence 기반 위임 결정
- 상위 Agent로 위임 (현재 Agent가 답변할 수 없는 경우)
- Context 누적 (상위로 전달)
- Root에서 최종 합성

기존 parent_agent_executor.py 기능 확장
"""
import re
import asyncio
import os
import logging
from typing import Generator, Optional, List, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.core.models import ChatbotDef, ExecutionRole, Message
from backend.executors.agent_executor import AgentExecutor
from backend.managers.memory_manager import MemoryManager
from backend.retrieval.ingestion_client import IngestionClient
from backend.services.embedding_service import get_embedding_service
from backend.llm.client import get_llm_client

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_hybrid_score_threshold() -> float:
    """환경변수에서 HYBRID_SCORE_THRESHOLD 값을 가져옴 (기본값: 0.15)"""
    return float(os.getenv('HYBRID_SCORE_THRESHOLD', '0.15'))


class HierarchicalAgentExecutor(AgentExecutor):
    """
    계층적 Agent Executor (3-tier hierarchy 지원)
    
    실행 흐름:
    1. 자체 DB로 답변 시도
    2. 검색 결과 기반 Confidence 계산
    3. Confidence < threshold:
       - 하위 Agent 있으면 하위로 위임 (기존 동작)
       - 하위 Agent 없거나 실패:
         - 부모 있으면 부모로 위임 (신규)
         - 부모 없으면 (Root) 실패 처리 또는 sub_chatbots 시도
    4. Context 누적 및 상위 전달
    5. Root에서 최종 합성
    
    위임 체인:
    User Query
       ↓
    Current Agent (Level 2 - Child)
       ↓ (low confidence)
    Delegate to Parent (Level 1)
       ↓ (still low confidence)
    Delegate to Grand-Parent (Level 0 - Root)
       ↓
    Root synthesizes final response
    """

    # 키워드 기반 매칭 (하위 호환 유지)
    KEYWORDS_MAP = {
        'chatbot-hr-policy': ['정책', '규정', '채용', '평가', '승진', '인사제도', '징계', '인사', '제도'],
        'chatbot-hr': ['인사', 'hr', '복리후생', '인사팀', '인사관리', '사내', '회사'],
        'chatbot-hr-benefit': ['급여', '연차', '휴가', '복지', '보험', '경조사', '교육지원', '수당', '상여', '복리후생', '의료비', '대출', '자금'],
        'chatbot-tech-backend': ['backend', '백엔드', 'python', 'fastapi', 'django', 'db', 'sql', 'api', '서버'],
        'chatbot-tech-frontend': ['frontend', '프론트엔드', 'react', 'vue', 'javascript', 'css', 'html', 'ui', '화면'],
        'chatbot-tech-devops': ['devops', 'docker', 'kubernetes', 'k8s', 'ci/cd', 'infra', '배포', '모니터링', '인프라'],
        'chatbot-rtl-verilog': ['rtl', 'verilog', 'fpga', '반도체', '디지털 회로', 'hdl', '합성'],
        'chatbot-rtl-synthesis': ['synthesis', '합성', '타이밍', '최적화', '면적', '전력'],
    }

    # 하이브리드 가중치 (keyword : embedding)
    KEYWORD_WEIGHT = 0.4
    EMBEDDING_WEIGHT = 0.6
    
    # 하이브리드 스코어 임계값 (이 값 이상인 후보만 선택)
    # 환경변수 HYBRID_SCORE_THRESHOLD로 오버라이드 가능
    HYBRID_SCORE_THRESHOLD = get_hybrid_score_threshold()
    
    # 위임 관련 상수
    DEFAULT_DELEGATION_THRESHOLD = 70
    MAX_DELEGATION_DEPTH = 5  # 최대 위임 깊이

    def __init__(
        self,
        chatbot_def: ChatbotDef,
        ingestion_client: IngestionClient,
        memory_manager: MemoryManager,
        chatbot_manager=None,
        accumulated_context: str = "",
        delegation_depth: int = 0,
    ):
        super().__init__(chatbot_def, ingestion_client, memory_manager)
        self.chatbot_manager = chatbot_manager
        self.accumulated_context = accumulated_context  # 상위에서 전달된 컨텍스트
        self.delegation_depth = delegation_depth  # 현재 위임 깊이 (순환 방지)
        
        # Policy 설정
        self.delegation_threshold = chatbot_def.policy.get(
            'delegation_threshold', self.DEFAULT_DELEGATION_THRESHOLD
        )
        self.multi_sub_execution = chatbot_def.policy.get('multi_sub_execution', False)
        self.max_parallel_subs = chatbot_def.policy.get('max_parallel_subs', 3)
        self.synthesis_mode = chatbot_def.policy.get('synthesis_mode', 'parallel')
        self.hybrid_score_threshold = chatbot_def.policy.get(
            'hybrid_score_threshold',
            get_hybrid_score_threshold()  # fallback to env/default
        )
        self.enable_parent_delegation = chatbot_def.policy.get(
            'enable_parent_delegation', True
        )  # 상위 위임 활성화 여부
        
        self._embedding_service = get_embedding_service()

    def execute(
        self,
        message: str,
        session_id: str,
    ) -> Generator[str, None, None]:
        """
        계층적 Agent 실행
        
        위임 체인:
        1. 자체 답변 시도 (Confidence 계산)
        2. Confidence 낮음:
           a. sub_chatbots 있으면 하위로 위임
           b. sub_chatbots 없거나 실패:
              - 부모 있으면 부모로 위임
              - 부모 없으면 (Root) 최종 시도 또는 실패
        """
        logger.info(f"[EXECUTE] Chatbot: {self.chatbot_def.name} (ID: {self.chatbot_def.id})")
        logger.info(f"[EXECUTE] Message: {message[:50]}...")
        logger.info(f"[EXECUTE] Session: {session_id}")
        logger.info(f"[EXECUTE] Delegation depth: {self.delegation_depth}")
        logger.info(f"[EXECUTE] Sub chatbots: {[s.id for s in self.chatbot_def.sub_chatbots]}")
        logger.info(f"[EXECUTE] Parent ID: {self.chatbot_def.parent_id}")
        
        # 위임 깊이 초과 체크
        if self.delegation_depth >= self.MAX_DELEGATION_DEPTH:
            logger.warning(f"[EXECUTE] Max delegation depth exceeded: {self.delegation_depth}")
            yield f"⚠️ 최대 위임 깊이({self.MAX_DELEGATION_DEPTH})를 초과했습니다. "
            yield f"현재 Agent [{self.chatbot_def.name}]가 최선의 답변을 제공합니다.\n\n"
            for chunk in self._execute_with_context(message, session_id, ""):
                yield chunk
            return

        # 1. RAG 검색 수행
        context = self._retrieve(message, self.chatbot_def.retrieval.db_ids)
        logger.info(f"[EXECUTE] Retrieved context length: {len(context)} chars")
        logger.info(f"[EXECUTE] DB IDs: {self.chatbot_def.retrieval.db_ids}")
        
        # 누적 컨텍스트 결합 (상위에서 전달된 컨텍스트가 있으면 결합)
        combined_context = self._combine_contexts(self.accumulated_context, context)
        
        # 2. 검색 결과 기반 Confidence 계산
        confidence = self._calculate_confidence(combined_context, message)
        logger.info(f"[EXECUTE] Confidence: {confidence}% (threshold: {self.delegation_threshold}%)")
        
        # 3. Confidence 체크 및 위임 결정
        if confidence < self.delegation_threshold:
            # 먼저 하위 Agent 위임 시도 (기존 동작)
            if self.chatbot_def.sub_chatbots:
                yield from self._delegate_to_sub_chatbots(
                    message, session_id, combined_context, confidence
                )
            # 하위 Agent 없거나 실패 시 부모로 위임 (신규)
            elif self.enable_parent_delegation and self.chatbot_def.parent_id:
                yield from self._delegate_to_parent(
                    message, session_id, combined_context, confidence
                )
            else:
                # 위임할 곳이 없음 - Root거나 Leaf
                if self.chatbot_def.is_root:
                    # Root: 최종 답변 제공
                    yield from self._execute_final(
                        message, session_id, combined_context, confidence
                    )
                else:
                    # Leaf but has parent: delegate up
                    if self.enable_parent_delegation and self.chatbot_def.parent_id:
                        yield from self._delegate_to_parent(
                            message, session_id, combined_context, confidence
                        )
                    else:
                        yield from self._execute_final(
                            message, session_id, combined_context, confidence
                        )
        else:
            # Confidence 충분 - 자체 답변
            yield from self._execute_confident(
                message, session_id, combined_context, confidence
            )

    def _combine_contexts(self, accumulated: str, current: str) -> str:
        """
        누적된 컨텍스트와 현재 컨텍스트를 결합
        """
        if not accumulated:
            return current
        if not current:
            return accumulated
        
        return f"[상위 컨텍스트]\n{accumulated}\n\n[현재 검색 결과]\n{current}"

    def _delegate_to_sub_chatbots(
        self,
        message: str,
        session_id: str,
        context: str,
        confidence: float,
    ) -> Generator[str, None, None]:
        """하위 챗봇으로 위임 (기존 동행 개선)"""
        logger.info(f"[DELEGATE] Starting sub delegation from {self.chatbot_def.name}")
        logger.info(f"[DELEGATE] Sub chatbots: {[s.id for s in self.chatbot_def.sub_chatbots]}")
        
        yield f"📋 이 질문은 전문가 상담이 필요합니다.\n\n"
        yield f"({self.chatbot_def.name} 신뢰도: {confidence}% → 하위 Agent 위임)\n\n"
        yield f"---\n📡 **전문가 챗봇을 호출합니다...**\n\n"
        
        if self.multi_sub_execution:
            logger.info(f"[DELEGATE] Multi-sub execution enabled")
            # 다중 하위 Agent 선택 및 실행
            sub_candidates = self._select_sub_chatbot_hybrid_multi(message)
            logger.info(f"[DELEGATE] Selected {len(sub_candidates)} candidates")
            for chatbot, info, scores in sub_candidates:
                logger.info(f"[DELEGATE]   - {chatbot.name} (ID: {chatbot.id}): hybrid={scores['hybrid']:.3f}, kw={scores['keyword']:.3f}, emb={scores['embedding']:.3f}")
                yield f"**선택된 전문가**: {', '.join([c[0].name for c in sub_candidates])}\n\n"
                
                # 다중 하위 Agent 실행
                sub_responses = self._execute_multiple_subs(
                    sub_candidates, message, session_id, context
                )
                
                if sub_responses:
                    # 응답 종합
                    yield f"\n---\n🔄 **응답을 종합하는 중입니다...**\n\n"
                    synthesized = self._synthesize_responses(
                        parent_context=context,
                        user_message=message,
                        sub_responses=sub_responses
                    )
                    yield synthesized
                else:
                    # 하위 Agent 실패 - 부모로 위임 시도
                    if self.enable_parent_delegation and self.chatbot_def.parent_id:
                        yield "\n❌ 하위 Agent들이 응답할 수 없습니다. 상위 Agent로 위임합니다...\n"
                        yield from self._delegate_to_parent(
                            message, session_id, context, confidence
                        )
                    else:
                        yield "❌ 하위 Agent 실행 중 오류가 발생했습니다.\n"
                        for chunk in self._execute_with_context(message, session_id, context):
                            yield chunk
            else:
                # 적합한 하위 Agent 없음 - 부모로 위임
                if self.enable_parent_delegation and self.chatbot_def.parent_id:
                    yield "\n⚠️ 적합한 하위 Agent를 찾을 수 없습니다. 상위 Agent로 위임합니다...\n"
                    yield from self._delegate_to_parent(
                        message, session_id, context, confidence
                    )
                else:
                    yield "❌ 적합한 하위 Agent를 찾을 수 없습니다.\n"
                    for chunk in self._execute_with_context(message, session_id, context):
                        yield chunk
        else:
            # 단일 하위 Agent 실행
            sub_chatbot, selection_info = self._select_sub_chatbot_hybrid(message)
            if sub_chatbot:
                yield f"**[{sub_chatbot.name}]** {selection_info}\n\n"
                for sub_chunk in self._delegate_to_sub(
                    sub_chatbot, message, session_id, context
                ):
                    yield sub_chunk
            else:
                # 하위 Agent 선택 실패 - 부모로 위임
                if self.enable_parent_delegation and self.chatbot_def.parent_id:
                    yield "\n⚠️ 적합한 하위 Agent를 찾을 수 없습니다. 상위 Agent로 위임합니다...\n"
                    yield from self._delegate_to_parent(
                        message, session_id, context, confidence
                    )
                else:
                    yield "❌ 적합한 하위 Agent를 찾을 수 없습니다.\n"
                    for chunk in self._execute_with_context(message, session_id, context):
                        yield chunk

    def _delegate_to_parent(
        self,
        message: str,
        session_id: str,
        context: str,
        confidence: float,
    ) -> Generator[str, None, None]:
        """
        상위(부모) Agent로 위임
        
        Args:
            message: 사용자 메시지
            session_id: 세션 ID
            context: 누적된 컨텍스트
            confidence: 현재 Confidence (로깅용)
        """
        if not self.chatbot_manager:
            yield "❌ ChatbotManager가 설정되지 않아 부모 Agent로 위임할 수 없습니다.\n"
            for chunk in self._execute_with_context(message, session_id, context):
                yield chunk
            return
        
        parent_id = self.chatbot_def.parent_id
        if not parent_id:
            yield "⚠️ 부모 Agent가 없습니다. 현재 Agent로 답변합니다.\n"
            for chunk in self._execute_with_context(message, session_id, context):
                yield chunk
            return
        
        parent_def = self.chatbot_manager.get_active(parent_id)
        if not parent_def:
            yield f"⚠️ 부모 Agent '{parent_id}'를 찾을 수 없습니다. 현재 Agent로 답변합니다.\n"
            for chunk in self._execute_with_context(message, session_id, context):
                yield chunk
            return
        
        # 위임 정보 출력
        yield f"\n📤 **[{self.chatbot_def.name}] → [{parent_def.name}]**로 위임합니다.\n"
        yield f"(Confidence: {confidence}% / Level: {self.chatbot_def.level} → {parent_def.level})\n\n"
        
        # 상위 Executor 생성 (누적 컨텍스트 전달)
        parent_executor = HierarchicalAgentExecutor(
            chatbot_def=parent_def,
            ingestion_client=self.ingestion,
            memory_manager=self.memory,
            chatbot_manager=self.chatbot_manager,
            accumulated_context=context,  # 컨텍스트 누적
            delegation_depth=self.delegation_depth + 1,  # 위임 깊이 증가
        )
        
        # 부모 Agent 실행
        for chunk in parent_executor.execute(message, session_id):
            yield chunk

    def _execute_confident(
        self,
        message: str,
        session_id: str,
        context: str,
        confidence: float,
    ) -> Generator[str, None, None]:
        """Confidence가 충분한 경우 실행"""
        yield f"📢 **[{self.chatbot_def.name}]** (신뢰도: {confidence}% / Level: {self.chatbot_def.level})\n\n"
        for chunk in self._execute_with_context(message, session_id, context):
            yield chunk

    def _execute_final(
        self,
        message: str,
        session_id: str,
        context: str,
        confidence: float,
    ) -> Generator[str, None, None]:
        """최종 답변 (Root에서 호출)"""
        yield f"📢 **[{self.chatbot_def.name}]** (최종 답변 / 신뢰도: {confidence}% / Level: {self.chatbot_def.level})\n\n"
        
        # 누적된 컨텍스트가 있으면 활용하여 향상된 답변 생성
        if self.accumulated_context:
            yield "*(하위 Agent들의 컨텍스트를 종합하여 답변합니다)*\n\n"
        
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
    # 하위 Agent 선택 (하이브리드 방식)
    # ====================================================================
    def _select_sub_chatbot_hybrid(self, message: str) -> Tuple[Optional[ChatbotDef], str]:
        """하이브리드 하위 Agent 선택 (단일 반환)"""
        candidates = self._select_sub_chatbot_hybrid_multi(message)
        if candidates:
            best = candidates[0]
            info = f"(kw:{best[2]['keyword']}, emb:{best[2]['embedding']}, hybrid:{best[2]['hybrid']})"
            return best[0], info
        return None, ""

    def _select_sub_chatbot_hybrid_multi(
        self, message: str
    ) -> List[Tuple[ChatbotDef, str, dict]]:
        """하이브리드 하위 Agent 선택 (다중 반환)"""
        if not self.chatbot_manager:
            return []

        candidates = []

        for sub_ref in self.chatbot_def.sub_chatbots:
            sub_def = self.chatbot_manager.get_active(sub_ref.id)
            if not sub_def:
                continue
            candidates.append(sub_def)

        if not candidates:
            return []

        message_lower = message.lower()
        scores = []

        for sub_def in candidates:
            kw_score = self._keyword_score(sub_def.id, message_lower)
            emb_score = self._embedding_score(message, sub_def)
            hybrid = self.KEYWORD_WEIGHT * kw_score + self.EMBEDDING_WEIGHT * emb_score

            scores.append({
                'chatbot': sub_def,
                'keyword': round(kw_score, 3),
                'embedding': round(emb_score, 3),
                'hybrid': round(hybrid, 3),
            })

        scores.sort(key=lambda x: x['hybrid'], reverse=True)
        filtered = [s for s in scores if s['hybrid'] >= self.hybrid_score_threshold]

        # Fail-safe: if no candidates pass hybrid threshold, include best keyword match
        # if keyword_score >= 0.3 (at least 1 keyword matched)
        if not filtered:
            keyword_matches = [s for s in scores if s['keyword'] >= 0.3]
            if keyword_matches:
                # Sort by keyword score descending, then hybrid
                keyword_matches.sort(key=lambda x: (x['keyword'], x['hybrid']), reverse=True)
                filtered = keyword_matches[:1]  # Take the best keyword match
            elif scores:
                # Ultimate fallback: include top candidate even if below threshold
                filtered = scores[:1]

        selected = filtered[:self.max_parallel_subs]

        result = []
        for s in selected:
            info = f"(kw:{s['keyword']}, emb:{s['embedding']}, hybrid:{s['hybrid']})"
            result.append((s['chatbot'], info, {
                'keyword': s['keyword'],
                'embedding': s['embedding'],
                'hybrid': s['hybrid']
            }))

        return result

    def _keyword_score(self, chatbot_id: str, message_lower: str) -> float:
        """키워드 매칭 점수 (0~1 정규화)"""
        keywords = self.KEYWORDS_MAP.get(chatbot_id, [])
        if not keywords:
            return 0.0
        
        matched = sum(1 for kw in keywords if kw.lower() in message_lower)
        return min(matched / max(len(keywords) * 0.3, 1), 1.0)

    def _embedding_score(self, message: str, sub_def: ChatbotDef) -> float:
        """임베딩 코사인 유사도 점수 (0~1)"""
        profile_parts = [sub_def.name, sub_def.description]
        
        keywords = self.KEYWORDS_MAP.get(sub_def.id, [])
        if keywords:
            profile_parts.append(' '.join(keywords))
        
        if sub_def.system_prompt:
            profile_parts.append(sub_def.system_prompt[:200])
        
        profile_text = ' '.join(profile_parts)
        
        return self._embedding_service.cosine_similarity(message, profile_text)

    # ====================================================================
    # 다중 하위 Agent 실행
    # ====================================================================
    def _execute_multiple_subs(
        self,
        sub_candidates: List[Tuple[ChatbotDef, str, dict]],
        message: str,
        session_id: str,
        parent_context: str = "",
    ) -> List[Tuple[str, str, str]]:
        """다중 하위 Agent 실행"""
        if self.synthesis_mode == 'sequential':
            return self._execute_multiple_subs_sequential(
                sub_candidates, message, session_id, parent_context
            )
        else:
            return self._execute_multiple_subs_parallel(
                sub_candidates, message, session_id, parent_context
            )

    def _execute_multiple_subs_sequential(
        self,
        sub_candidates: List[Tuple[ChatbotDef, str, dict]],
        message: str,
        session_id: str,
        parent_context: str = "",
    ) -> List[Tuple[str, str, str]]:
        """순차적으로 다중 하위 Agent 실행"""
        results = []
        
        for sub_chatbot, selection_info, scores in sub_candidates:
            try:
                response = self._execute_single_sub(
                    sub_chatbot, message, session_id, parent_context
                )
                if response:
                    results.append((sub_chatbot.id, sub_chatbot.name, response))
            except Exception as e:
                results.append((
                    sub_chatbot.id,
                    sub_chatbot.name,
                    f"[오류: 응답 생성 실패 - {str(e)}]"
                ))
        
        return results

    def _execute_multiple_subs_parallel(
        self,
        sub_candidates: List[Tuple[ChatbotDef, str, dict]],
        message: str,
        session_id: str,
        parent_context: str = "",
    ) -> List[Tuple[str, str, str]]:
        """병렬로 다중 하위 Agent 실행"""
        results = []
        errors = []
        
        def execute_single(sub_chatbot: ChatbotDef) -> Tuple[str, str, Optional[str]]:
            try:
                response = self._execute_single_sub(
                    sub_chatbot, message, session_id, parent_context
                )
                return (sub_chatbot.id, sub_chatbot.name, response)
            except Exception as e:
                return (sub_chatbot.id, sub_chatbot.name, None)
        
        with ThreadPoolExecutor(max_workers=min(len(sub_candidates), 5)) as executor:
            future_to_sub = {
                executor.submit(execute_single, sub[0]): sub 
                for sub in sub_candidates
            }
            
            for future in as_completed(future_to_sub):
                sub_id, sub_name, response = future.result()
                if response:
                    results.append((sub_id, sub_name, response))
                else:
                    errors.append((sub_id, sub_name))
        
        if errors:
            print(f"[HierarchicalAgentExecutor] Failed sub-agents: {errors}")
        
        return results

    def _execute_single_sub(
        self,
        sub_chatbot: ChatbotDef,
        message: str,
        session_id: str,
        parent_context: str = "",
    ) -> str:
        """단일 하위 Agent 실행 (전체 응답 수집)"""
        from backend.executors import AgentExecutor

        sub_executor = AgentExecutor(
            sub_chatbot,
            self.ingestion,
            self.memory
        )
        
        enhanced_message = message
        if parent_context:
            enhanced_message = f"[상위 Agent 컨텍스트] {parent_context[:500]}...\n\n[질문] {message}"

        full_response = []
        for chunk in sub_executor.execute(enhanced_message, session_id):
            full_response.append(chunk)
        
        return "".join(full_response)

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

    # ====================================================================
    # 응답 종합
    # ====================================================================
    def _synthesize_responses(
        self,
        parent_context: str,
        user_message: str,
        sub_responses: List[Tuple[str, str, str]],
    ) -> str:
        """다중 하위 Agent 응답을 종합하여 하나의 응답 생성"""
        if not sub_responses:
            return "❌ 하위 Agent로부터 응답을 받지 못했습니다."
        
        if len(sub_responses) == 1:
            _, name, response = sub_responses[0]
            return f"**[{name}]**\n\n{response}"
        
        synthesis_prompt = self._build_synthesis_prompt(
            parent_context, user_message, sub_responses
        )
        
        try:
            client = get_llm_client()
            messages = [
                {"role": "system", "content": synthesis_prompt["system"]},
                {"role": "user", "content": synthesis_prompt["user"]}
            ]
            
            response = client.chat.completions.create(
                model=self.chatbot_def.llm.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
                stream=False,
            )
            
            synthesized = response.choices[0].message.content or ""
            
            if sub_responses:
                synthesized += "\n\n---\n**참고 전문가:** " + ", ".join([
                    f"[{name}]" for _, name, _ in sub_responses
                ])
            
            return synthesized
            
        except Exception as e:
            return self._fallback_synthesis(sub_responses)

    def _build_synthesis_prompt(
        self,
        parent_context: str,
        user_message: str,
        sub_responses: List[Tuple[str, str, str]],
    ) -> dict:
        """응답 종합을 위한 프롬프트 구성"""
        expert_responses = []
        for sub_id, sub_name, response in sub_responses:
            expert_responses.append(
                f"### [{sub_name}]\n{response.strip()}"
            )
        
        experts_text = "\n\n".join(expert_responses)
        
        system_prompt = """당신은 여러 전문가 챗봇의 응답을 종합하는 통합 어시스턴트입니다.

사용자의 질문에 대해 여러 전문가가 각자의 관점에서 답변했습니다. 
이를 하나의 일관된 응답으로 정리해주세요.

종합 시 다음 원칙을 따르세요:
1. 중복되는 내용은 한 번만 포함하고, 보강되는 내용은 합쳐주세요
2. 각 전문가의 핵심 포인트를 유지하되, 자연스러운 흐름으로 연결하세요
3. 필요시 [전문가명] 형식으로 출처를 표기하세요
4. 사용자 질문의 모든 측면을 다루었는지 확인하세요
5. 모순되는 정보가 있다면, 더 신뢰할 수 있는 측면을 우선시하되 양쪽 의견을 명시하세요

답변은 한국어로 작성하세요."""

        user_prompt = f"""**사용자 질문:**
{user_message}

**상위 Agent 검색 컨텍스트:**
{parent_context[:500] if parent_context else "(컨텍스트 없음)"}

**전문가별 응답:**
{experts_text}

위 전문가들의 응답을 종합하여 사용자에게 하나의 일관된 답변을 제공해주세요."""

        return {'system': system_prompt, 'user': user_prompt}

    def _fallback_synthesis(
        self,
        sub_responses: List[Tuple[str, str, str]],
    ) -> str:
        """LLM 종합 실패 시 수동 종합"""
        parts = []
        parts.append("다음은 관련 전문가들의 답변을 종합한 내용입니다:\n")
        
        for i, (sub_id, sub_name, response) in enumerate(sub_responses, 1):
            parts.append(f"\n**[{sub_name}]**\n{response}")
        
        return "\n".join(parts)
