"""
Unit tests for HierarchicalAgentExecutor delegation logic

Test coverage:
- DelegateResult dataclass
- _select_delegate_target() method
- _combine_contexts() method
- Delegation path logic (self -> sub -> parent -> fallback)
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, '/Users/vegitime/.openclaw/workspace/projects/multi-custom-agent')

from backend.executors.hierarchical_agent_executor import (
    HierarchicalAgentExecutor,
    DelegateResult,
)
from backend.core.models import ChatbotDef, SubChatbotRef, ExecutionRole


class TestDelegateResult:
    """DelegateResult dataclass tests"""
    
    def test_delegate_result_creation(self):
        """Test DelegateResult can be created with target and reason"""
        result = DelegateResult(target='self', reason='high confidence')
        assert result.target == 'self'
        assert result.reason == 'high confidence'
    
    def test_delegate_result_all_targets(self):
        """Test all valid target values"""
        for target in ['self', 'sub', 'parent', 'fallback']:
            result = DelegateResult(target=target, reason=f'test {target}')
            assert result.target == target


class TestSelectDelegateTarget:
    """_select_delegate_target() method tests"""
    
    @pytest.fixture
    def mock_executor(self):
        """Create a mock executor with configurable chatbot"""
        mock_chatbot = Mock(spec=ChatbotDef)
        mock_chatbot.id = "test-chatbot"
        mock_chatbot.name = "Test Chatbot"
        mock_chatbot.level = 1
        mock_chatbot.sub_chatbots = []
        mock_chatbot.parent_id = None
        mock_chatbot.policy = {}
        
        mock_ingestion = Mock()
        mock_memory = Mock()
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=mock_chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
        )
        return executor
    
    def test_high_confidence_returns_self(self, mock_executor):
        """TC-DELEGATE-001: High confidence (>= threshold) should return 'self'"""
        mock_executor.delegation_threshold = 70
        
        result = mock_executor._select_delegate_target(confidence=75)
        
        assert result.target == 'self'
        assert '75' in result.reason
        assert 'threshold' in result.reason.lower()
    
    def test_low_confidence_with_sub_chatbots_returns_sub(self, mock_executor):
        """TC-DELEGATE-002: Low confidence with sub_chatbots should return 'sub'"""
        mock_executor.delegation_threshold = 70
        mock_executor.chatbot_def.sub_chatbots = [
            SubChatbotRef(id='sub-bot-1', level=2, default_role=ExecutionRole.AGENT)
        ]
        
        result = mock_executor._select_delegate_target(confidence=50)
        
        assert result.target == 'sub'
        assert 'sub_chatbots' in result.reason
    
    def test_low_confidence_without_sub_but_with_parent_returns_parent(self, mock_executor):
        """TC-DELEGATE-003: Low confidence, no sub, has parent should return 'parent'"""
        mock_executor.delegation_threshold = 70
        mock_executor.enable_parent_delegation = True
        mock_executor.chatbot_def.parent_id = "parent-bot"
        
        result = mock_executor._select_delegate_target(confidence=50)
        
        assert result.target == 'parent'
        assert 'parent' in result.reason.lower()
    
    def test_low_confidence_no_sub_no_parent_returns_fallback(self, mock_executor):
        """TC-DELEGATE-004: Low confidence, no sub, no parent should return 'fallback'"""
        mock_executor.delegation_threshold = 70
        mock_executor.enable_parent_delegation = True
        mock_executor.chatbot_def.parent_id = None
        mock_executor.chatbot_def.sub_chatbots = []
        
        result = mock_executor._select_delegate_target(confidence=50)
        
        assert result.target == 'fallback'
    
    def test_parent_delegation_disabled_returns_fallback(self, mock_executor):
        """TC-DELEGATE-005: Parent delegation disabled should not delegate to parent"""
        mock_executor.delegation_threshold = 70
        mock_executor.enable_parent_delegation = False
        mock_executor.chatbot_def.parent_id = "parent-bot"
        mock_executor.chatbot_def.sub_chatbots = []
        
        result = mock_executor._select_delegate_target(confidence=50)
        
        assert result.target == 'fallback'
    
    def test_exact_threshold_boundary(self, mock_executor):
        """TC-DELEGATE-006: Exactly at threshold should return 'self'"""
        mock_executor.delegation_threshold = 70
        
        result = mock_executor._select_delegate_target(confidence=70)
        
        assert result.target == 'self'


class TestCombineContexts:
    """_combine_contexts() method tests"""
    
    @pytest.fixture
    def executor(self):
        mock_chatbot = Mock(spec=ChatbotDef)
        mock_chatbot.id = "test"
        mock_chatbot.name = "Test"
        mock_chatbot.level = 0
        mock_chatbot.sub_chatbots = []
        mock_chatbot.parent_id = None
        mock_chatbot.policy = {}
        mock_ingestion = Mock()
        mock_memory = Mock()
        
        return HierarchicalAgentExecutor(
            chatbot_def=mock_chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
        )
    
    def test_combine_empty_accumulated(self, executor):
        """TC-CONTEXT-001: Empty accumulated context should return current"""
        current = "Current search results"
        
        result = executor._combine_contexts("", current)
        
        assert result == current
    
    def test_combine_empty_current(self, executor):
        """TC-CONTEXT-002: Empty current context should return accumulated"""
        accumulated = "Previously accumulated context"
        
        result = executor._combine_contexts(accumulated, "")
        
        assert result == accumulated
    
    def test_combine_both_contexts(self, executor):
        """TC-CONTEXT-003: Both contexts should be combined with markers"""
        accumulated = "Parent agent context"
        current = "Current search results"
        
        result = executor._combine_contexts(accumulated, current)
        
        assert "[상위 컨텍스트]" in result
        assert "[현재 검색 결과]" in result
        assert accumulated in result
        assert current in result
    
    def test_combine_preserves_order(self, executor):
        """TC-CONTEXT-004: Accumulated should come before current"""
        accumulated = "First"
        current = "Second"
        
        result = executor._combine_contexts(accumulated, current)
        
        assert result.index("First") < result.index("Second")


class TestExecuteDelegationDecision:
    """execute() 단계에서 실제 위임 호출 여부 검증"""

    @pytest.fixture
    def parent_executor(self):
        mock_chatbot = Mock(spec=ChatbotDef)
        mock_chatbot.id = "parent-bot"
        mock_chatbot.name = "Parent Bot"
        mock_chatbot.level = 1
        mock_chatbot.sub_chatbots = [
            SubChatbotRef(id='sub-1', level=2, default_role=ExecutionRole.AGENT),
        ]
        mock_chatbot.parent_id = None
        mock_chatbot.policy = {"delegation_threshold": 70}
        mock_chatbot.retrieval = Mock()
        mock_chatbot.retrieval.db_ids = ["db_parent"]
        mock_chatbot.retrieval.k = 5
        mock_chatbot.retrieval.filter_metadata = None

        mock_ingestion = Mock()
        mock_memory = Mock()

        return HierarchicalAgentExecutor(
            chatbot_def=mock_chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
        )

    def test_execute_parent_answerable_question_should_not_delegate(self, parent_executor):
        """TC-EXEC-001: parent가 답변 가능(고신뢰)하면 하위로 위임하지 않아야 함"""
        # parent가 답할 수 있는 상황 강제
        parent_executor._retrieve = Mock(return_value="PDDI 프로젝트 관련 정책/현황 문서")
        parent_executor._calculate_confidence = Mock(return_value=90)

        # 실행 경로 추적
        parent_executor._respond_directly = Mock(return_value=iter(["parent answer"]))
        parent_executor._delegate = Mock(return_value=iter(["delegated answer"]))

        out = list(parent_executor.execute("PDDI 프로젝트 현황 알려줘", "sess-1"))

        # 기대: 직접 응답 1회, 위임 0회
        parent_executor._respond_directly.assert_called_once()
        parent_executor._delegate.assert_not_called()
        assert out == ["parent answer"]


class TestDelegationPathLogic:
    """Integration tests for delegation path priority"""
    
    @pytest.fixture
    def mock_executor_with_all_options(self):
        """Create executor with sub_chatbots, parent, and policy"""
        mock_chatbot = Mock(spec=ChatbotDef)
        mock_chatbot.id = "test-bot"
        mock_chatbot.name = "Test Bot"
        mock_chatbot.level = 1
        mock_chatbot.sub_chatbots = [
            SubChatbotRef(id='sub-1', level=2, default_role=ExecutionRole.AGENT),
        ]
        mock_chatbot.parent_id = "parent-bot"
        mock_chatbot.policy = {}
        
        mock_ingestion = Mock()
        mock_memory = Mock()
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=mock_chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
        )
        executor.enable_parent_delegation = True
        executor.delegation_threshold = 70
        
        return executor
    
    def test_priority_self_over_sub(self, mock_executor_with_all_options):
        """TC-PRIORITY-001: High confidence should prefer self over sub"""
        result = mock_executor_with_all_options._select_delegate_target(confidence=80)
        
        assert result.target == 'self'
    
    def test_priority_sub_over_parent(self, mock_executor_with_all_options):
        """TC-PRIORITY-002: With sub_chatbots, should prefer sub over parent"""
        result = mock_executor_with_all_options._select_delegate_target(confidence=50)
        
        assert result.target == 'sub'
    
    def test_priority_parent_over_fallback(self, mock_executor_with_all_options):
        """TC-PRIORITY-003: Without sub but with parent, should prefer parent"""
        mock_executor_with_all_options.chatbot_def.sub_chatbots = []
        
        result = mock_executor_with_all_options._select_delegate_target(confidence=50)
        
        assert result.target == 'parent'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
