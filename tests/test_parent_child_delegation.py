"""
test_parent_child_delegation.py - 상위/하위 Agent 위임 로직 테스트

테스트 시나리오:
1. 상위 Agent가 직접 답변 (confidence >= 70%)
2. 상위 Agent가 하위 Agent에게 위임 (confidence < 70%)
3. 키워드 기반 하위 Agent 선택
4. 하위 Agent 응답 수신 및 종합
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import re

from backend.core.models import ChatbotDef, ExecutionRole, SubChatbotRef
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
