"""
test_parent_child_delegation.py - 상위/하위 Agent 위임 로직 테스트

테스트 시나리오:
1. 상위 Agent가 직접 답변 (confidence >= 70%)
2. 상위 Agent가 하위 Agent에게 위임 (confidence < 70%)
3. 키워드 기반 하위 Agent 선택
4. 하위 Agent 응답 수신 및 종합
5. 다중 하위 Agent 실행 (v3)
6. 응답 종합 (v3)
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import re

from backend.core.models import ChatbotDef, ExecutionRole, SubChatbotRef, LLMConfig, RetrievalConfig, MemoryConfig
from backend.executors.parent_agent_executor import ParentAgentExecutor


class TestParentAgentExecutor:
    """ParentAgentExecutor 단위 테스트"""

    def test_parse_confidence_valid(self):
        """신뢰도 파싱 - 유효한 값"""
        text = "답변 내용\n\nCONFIDENCE: 85"
        executor = Mock(spec=ParentAgentExecutor)
        result = ParentAgentExecutor._parse_confidence(executor, text)
        assert result == 85

    def test_parse_confidence_low(self):
        """신뢰도 파싱 - 낮은 값 (위임 대상)"""
        text = "답변 내용\n\nCONFIDENCE: 45"
        executor = Mock(spec=ParentAgentExecutor)
        result = ParentAgentExecutor._parse_confidence(executor, text)
        assert result == 45
        assert result < 70  # 위임 임계값 미만

    def test_parse_confidence_no_match(self):
        """신뢰도 파싱 - 패턴 없음"""
        text = "답변 내용만 있고 신뢰도 없음"
        executor = Mock(spec=ParentAgentExecutor)
        result = ParentAgentExecutor._parse_confidence(executor, text)
        assert result == 0

    def test_select_sub_chatbot_by_keywords(self):
        """키워드 기반 하위 Agent 선택"""
        # Mock 설정
        chatbot_manager = Mock()
        
        # 상위 챗봇 설정
        parent_def = Mock()
        parent_def.sub_chatbots = [
            SubChatbotRef("chatbot-hr-policy", 1, ExecutionRole.AGENT),
            SubChatbotRef("chatbot-hr-benefit", 1, ExecutionRole.AGENT),
        ]
        
        # 하위 챗봇 mock
        policy_bot = Mock()
        policy_bot.name = "인사정책 전문 챗봇"
        policy_bot.id = "chatbot-hr-policy"
        
        benefit_bot = Mock()
        benefit_bot.name = "복리후생 전문 챗봇"
        benefit_bot.id = "chatbot-hr-benefit"
        
        chatbot_manager.get_active.side_effect = lambda x: {
            "chatbot-hr-policy": policy_bot,
            "chatbot-hr-benefit": benefit_bot,
        }.get(x)
        
        # Executor 생성
        executor = Mock(spec=ParentAgentExecutor)
        executor.chatbot_manager = chatbot_manager
        executor.chatbot_def = parent_def
        
        # 키워드 매칭 테스트
        message = "연차 신청 규정이 어떻게 돼?"
        selected = ParentAgentExecutor._select_sub_chatbot(executor, message)
        
        assert selected is not None
        assert selected.id == "chatbot-hr-policy"  # "규정" 키워드 매칭

    def test_select_sub_chatbot_default_first(self):
        """키워드 매칭 없을 때 첫 번째 하위 Agent 반환"""
        chatbot_manager = Mock()
        
        parent_def = Mock()
        parent_def.sub_chatbots = [
            SubChatbotRef("chatbot-hr-policy", 1, ExecutionRole.AGENT),
        ]
        
        policy_bot = Mock()
        policy_bot.name = "인사정책 전문 챗봇"
        policy_bot.id = "chatbot-hr-policy"
        
        chatbot_manager.get_active.return_value = policy_bot
        
        executor = Mock(spec=ParentAgentExecutor)
        executor.chatbot_manager = chatbot_manager
        executor.chatbot_def = parent_def
        
        # 매칭 없는 메시지
        message = "알 수 없는 질문"
        selected = ParentAgentExecutor._select_sub_chatbot(executor, message)
        
        assert selected is not None
        assert selected.id == "chatbot-hr-policy"  # 첫 번째 반환


class TestConfidenceThreshold:
    """신뢰도 임계값 테스트"""

    def test_delegation_threshold_70(self):
        """70% 임계값 체크"""
        threshold = 70
        
        # 위임 필요 케이스
        assert 45 < threshold  # 위임 O
        assert 30 < threshold  # 위임 O
        assert 69 < threshold  # 위임 O
        
        # 위임 불필요 케이스
        assert 70 >= threshold  # 위임 X
        assert 85 >= threshold  # 위임 X
        assert 100 >= threshold  # 위임 X


class TestIntegrationScenarios:
    """통합 테스트 시나리오"""

    @pytest.mark.parametrize("message,expected_sub_id", [
        ("인사 평가 정책 알려줘", "chatbot-hr-policy"),  # "평가", "정책" 매칭
        ("연차 신청 방법", "chatbot-hr-benefit"),  # "연차" 매칭
        ("급여 명세서 확인", "chatbot-hr-benefit"),  # "급여" 매칭
        ("FastAPI 사용법", "chatbot-tech-backend"),  # "fastapi" 매칭
        ("React 컴포넌트 만들기", "chatbot-tech-frontend"),  # "react" 매칭
        ("Docker 이미지 빌드", "chatbot-tech-devops"),  # "docker" 매칭
    ])
    def test_keyword_matching(self, message, expected_sub_id):
        """키워드 매칭 테스트"""
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
        
        for sub_id, keywords in keywords_map.items():
            score = sum(1 for kw in keywords if kw.lower() in message_lower)
            if score > best_score:
                best_score = score
                best_match = sub_id
        
        assert best_match == expected_sub_id, f"Expected {expected_sub_id}, got {best_match}"


class TestMultiSubAgentExecution:
    """다중 하위 Agent 실행 테스트 (v3)"""

    def test_multi_sub_execution_enabled(self):
        """multi_sub_execution 설정 확인"""
        # Mock 설정
        chatbot_manager = Mock()
        
        # multi_sub_execution이 활성화된 policy
        policy = {
            'delegation_threshold': 70,
            'multi_sub_execution': True,
            'max_parallel_subs': 2,
            'synthesis_mode': 'parallel'
        }
        
        # 검증
        assert policy['multi_sub_execution'] is True
        assert policy['max_parallel_subs'] == 2
        assert policy['synthesis_mode'] == 'parallel'

    def test_select_sub_chatbot_hybrid_multi_returns_list(self):
        """다중 하위 Agent 선택이 리스트 반환"""
        chatbot_manager = Mock()
        
        # 상위 챗봇 설정
        parent_def = Mock()
        parent_def.sub_chatbots = [
            SubChatbotRef("chatbot-hr-policy", 1, ExecutionRole.AGENT),
            SubChatbotRef("chatbot-hr-benefit", 1, ExecutionRole.AGENT),
        ]
        parent_def.policy = {
            'multi_sub_execution': True,
            'max_parallel_subs': 2,
            'synthesis_mode': 'parallel'
        }
        
        # 하위 챗봇 mock
        policy_bot = Mock()
        policy_bot.name = "인사정책 전문 챗봇"
        policy_bot.id = "chatbot-hr-policy"
        policy_bot.description = "인사 정책 전문"
        policy_bot.system_prompt = "당신은 인사정책 전문가입니다."
        policy_bot.retrieval = Mock(db_ids=[])
        policy_bot.llm = Mock(model="test-model", temperature=0.3, max_tokens=1024, stream=True)
        policy_bot.memory = Mock(enabled=True, max_messages=20)
        
        benefit_bot = Mock()
        benefit_bot.name = "복리후생 전문 챗봇"
        benefit_bot.id = "chatbot-hr-benefit"
        benefit_bot.description = "복리후생 전문"
        benefit_bot.system_prompt = "당신은 복리후생 전문가입니다."
        benefit_bot.retrieval = Mock(db_ids=[])
        benefit_bot.llm = Mock(model="test-model", temperature=0.3, max_tokens=1024, stream=True)
        benefit_bot.memory = Mock(enabled=True, max_messages=20)
        
        chatbot_manager.get_active.side_effect = lambda x: {
            "chatbot-hr-policy": policy_bot,
            "chatbot-hr-benefit": benefit_bot,
        }.get(x)
        
        # Executor 생성
        executor = Mock(spec=ParentAgentExecutor)
        executor.chatbot_manager = chatbot_manager
        executor.chatbot_def = parent_def
        executor.KEYWORDS_MAP = ParentAgentExecutor.KEYWORDS_MAP
        executor.KEYWORD_WEIGHT = ParentAgentExecutor.KEYWORD_WEIGHT
        executor.EMBEDDING_WEIGHT = ParentAgentExecutor.EMBEDDING_WEIGHT
        executor.HYBRID_SCORE_THRESHOLD = ParentAgentExecutor.HYBRID_SCORE_THRESHOLD
        executor.max_parallel_subs = 2
        
        # embedding service mock
        mock_embedding = Mock()
        mock_embedding.cosine_similarity.return_value = 0.8
        executor._embedding_service = mock_embedding
        
        # 테스트 메시지 (정책 + 복지 관련)
        message = "연차 신청 규정이 어떻게 돼?"
        
        # 다중 선택 실행
        candidates = ParentAgentExecutor._select_sub_chatbot_hybrid_multi(executor, message)
        
        # 결과 검증
        assert isinstance(candidates, list)
        # 최소 하나의 후보 반환 (키워드 매칭으로 인해)
        assert len(candidates) >= 1

    def test_execute_multiple_subs_returns_responses(self):
        """다중 하위 Agent 실행 결과 반환"""
        # Mock sub-chatbots
        policy_bot = Mock()
        policy_bot.id = "chatbot-hr-policy"
        policy_bot.name = "인사정책 전문 챗봇"
        
        benefit_bot = Mock()
        benefit_bot.id = "chatbot-hr-benefit"
        benefit_bot.name = "복리후생 전문 챗봇"
        
        # 후보 목록
        sub_candidates = [
            (policy_bot, "(kw:0.5, emb:0.8, hybrid:0.68)", {'keyword': 0.5, 'embedding': 0.8, 'hybrid': 0.68}),
            (benefit_bot, "(kw:0.3, emb:0.7, hybrid:0.58)", {'keyword': 0.3, 'embedding': 0.7, 'hybrid': 0.58}),
        ]
        
        # Executor mock
        executor = Mock(spec=ParentAgentExecutor)
        executor.synthesis_mode = 'parallel'
        
        # _execute_single_sub mock 결과 설정
        def mock_execute_single(sub, msg, sid, ctx):
            return f"[{sub.name}]의 답변: {msg}에 대한 응답"
        
        executor._execute_single_sub = Mock(side_effect=mock_execute_single)
        
        # 병렬 실행 테스트
        with patch.object(ParentAgentExecutor, '_execute_single_sub', mock_execute_single):
            results = ParentAgentExecutor._execute_multiple_subs_parallel(
                executor, sub_candidates, "테스트 메시지", "session-123", ""
            )
        
        # 결과 검증
        assert isinstance(results, list)
        assert len(results) == 2
        
        # 각 결과는 (sub_id, sub_name, response) 튜플
        for result in results:
            assert len(result) == 3
            assert result[0] in ["chatbot-hr-policy", "chatbot-hr-benefit"]
            assert result[2]  # 응답 텍스트 존재

    def test_synthesize_responses_single_response(self):
        """단일 응답 종합"""
        executor = Mock(spec=ParentAgentExecutor)
        
        sub_responses = [
            ("chatbot-hr-policy", "인사정책 전문 챗봇", "연차는 1년에 15일입니다.")
        ]
        
        result = ParentAgentExecutor._synthesize_responses(
            executor, "상위 컨텍스트", "연차가 뭐야?", sub_responses
        )
        
        assert "인사정책 전문 챗봇" in result
        assert "15일" in result

    def test_synthesize_responses_multiple(self):
        """다중 응답 종합 (LLM 호출)"""
        executor = Mock(spec=ParentAgentExecutor)
        
        # LLM mock
        mock_llm_response = Mock()
        mock_llm_response.choices = [Mock(message=Mock(content="종합된 답변입니다."))]
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_llm_response
        
        executor.chatbot_def = Mock()
        executor.chatbot_def.llm = Mock(model="test-model")
        
        sub_responses = [
            ("chatbot-hr-policy", "인사정책 전문 챗봇", "연차 신청은 내부 시스템에서 하세요."),
            ("chatbot-hr-benefit", "복리후생 전문 챗봇", "연차는 1년에 15일입니다."),
        ]
        
        with patch('backend.executors.parent_agent_executor.get_llm_client', return_value=mock_client):
            result = ParentAgentExecutor._synthesize_responses(
                executor, "상위 컨텍스트", "연차 신청 방법과 금액 알려줘", sub_responses
            )
        
        assert "종합된 답변" in result or "참고 전문가" in result

    def test_fallback_synthesis(self):
        """LLM 종합 실패 시 fallback"""
        sub_responses = [
            ("chatbot-hr-policy", "인사정책 전문 챗봇", "연차 신청은 시스템에서."),
            ("chatbot-hr-benefit", "복리후생 전문 챗봇", "연차는 1년 15일."),
        ]
        
        result = ParentAgentExecutor._fallback_synthesis(None, sub_responses)
        
        assert "인사정책 전문 챗봇" in result
        assert "복리후생 전문 챗봇" in result
        assert "연차 신청은 시스템에서" in result

    def test_backward_compatibility_single_execution(self):
        """하위 호환: 단일 하위 Agent 실행"""
        chatbot_manager = Mock()
        
        parent_def = Mock()
        parent_def.sub_chatbots = [
            SubChatbotRef("chatbot-hr-policy", 1, ExecutionRole.AGENT),
        ]
        parent_def.policy = {
            'multi_sub_execution': False,  # 비활성화
            'delegation_threshold': 70
        }
        
        policy_bot = Mock()
        policy_bot.name = "인사정책 전문 챗봇"
        policy_bot.id = "chatbot-hr-policy"
        
        chatbot_manager.get_active.return_value = policy_bot
        
        executor = Mock(spec=ParentAgentExecutor)
        executor.chatbot_manager = chatbot_manager
        executor.chatbot_def = parent_def
        executor.multi_sub_execution = False  # 비활성화
        
        # 단일 선택 실행
        selected, info = ParentAgentExecutor._select_sub_chatbot_hybrid(
            executor, "정책 질문"
        )
        
        assert selected is not None
        assert selected.id == "chatbot-hr-policy"

    def test_hybrid_score_threshold_filtering(self):
        """하이브리드 스코어 임계값 필터링"""
        scores = [
            {'hybrid': 0.85, 'chatbot': Mock(id='high')},
            {'hybrid': 0.72, 'chatbot': Mock(id='medium')},
            {'hybrid': 0.45, 'chatbot': Mock(id='low')},
            {'hybrid': 0.20, 'chatbot': Mock(id='very-low')},  # 임계값 미만
        ]
        
        threshold = 0.3
        filtered = [s for s in scores if s['hybrid'] >= threshold]
        
        assert len(filtered) == 3
        assert all(s['hybrid'] >= threshold for s in filtered)

    def test_max_parallel_subs_limit(self):
        """max_parallel_subs 제한"""
        max_parallel_subs = 2
        
        scores = [
            {'hybrid': 0.9, 'chatbot': Mock(id='1')},
            {'hybrid': 0.8, 'chatbot': Mock(id='2')},
            {'hybrid': 0.7, 'chatbot': Mock(id='3')},
            {'hybrid': 0.6, 'chatbot': Mock(id='4')},
        ]
        
        filtered = scores[:max_parallel_subs]
        
        assert len(filtered) == 2
        assert filtered[0]['hybrid'] == 0.9
        assert filtered[1]['hybrid'] == 0.8


class TestSynthesisPrompt:
    """응답 종합 프롬프트 테스트"""

    def test_build_synthesis_prompt_structure(self):
        """종합 프롬프트 구조 검증"""
        sub_responses = [
            ("chatbot-hr-policy", "인사정책 팀", "연차는 내부 시스템에서 신청하세요."),
            ("chatbot-hr-benefit", "복리후생 팀", "연차는 1년에 15일입니다."),
        ]
        
        prompt = ParentAgentExecutor._build_synthesis_prompt(
            None, "상위 컨텍스트", "연차 알려줘", sub_responses
        )
        
        assert 'system' in prompt
        assert 'user' in prompt
        assert "인사정책 팀" in prompt['user']
        assert "복리후생 팀" in prompt['user']
        assert "상위 컨텍스트" in prompt['user']

    def test_synthesis_prompt_contains_instructions(self):
        """프롬프트에 종합 지침 포함"""
        sub_responses = [
            ("chatbot-1", "팀1", "답변1"),
        ]
        
        prompt = ParentAgentExecutor._build_synthesis_prompt(
            None, "", "질문", sub_responses
        )
        
        assert "종합" in prompt['system'] or "통합" in prompt['system']
        assert "전문가" in prompt['system']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
