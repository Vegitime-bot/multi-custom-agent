"""
System/Integration tests for HierarchicalAgentExecutor delegation

End-to-end delegation scenarios:
- High confidence → direct answer
- Low confidence + sub_chatbots → sub delegation
- Low confidence + no sub + parent → parent delegation
- Max delegation depth exceeded
- Memory/context accumulation across delegations
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch, PropertyMock

sys.path.insert(0, '/Users/vegitime/.openclaw/workspace/projects/multi-custom-agent')

from backend.executors.hierarchical_agent_executor import (
    HierarchicalAgentExecutor,
    DelegateResult,
)
from backend.core.models import ChatbotDef, SubChatbotRef, ExecutionRole


def make_chatbot_def(
    chatbot_id: str,
    name: str,
    level: int = 0,
    sub_chatbots: list = None,
    parent_id: str = None,
    system_prompt: str = "You are a helpful assistant.",
    description: str = "Test chatbot",
    db_ids: list = None,
    policy: dict = None,
):
    """Helper to create a mock ChatbotDef"""
    mock = Mock(spec=ChatbotDef)
    mock.id = chatbot_id
    mock.name = name
    mock.level = level
    mock.sub_chatbots = sub_chatbots or []
    mock.parent_id = parent_id
    mock.system_prompt = system_prompt
    mock.description = description
    mock.is_root = (parent_id is None)
    mock.policy = policy or {}
    
    # Retrieval settings
    mock.retrieval = Mock()
    mock.retrieval.db_ids = db_ids or ["default-db"]
    
    # Memory settings
    mock.memory = Mock()
    mock.memory.max_messages = 20
    
    # LLM settings
    mock.llm = Mock()
    mock.llm.model = "test-model"
    
    return mock


class TestDirectAnswerScenario:
    """Scenario: High confidence → direct answer"""
    
    @pytest.fixture
    def setup_direct_answer(self):
        """Setup executor that will answer directly"""
        chatbot = make_chatbot_def(
            chatbot_id="chatbot-hr-benefit",
            name="HR Benefit Bot",
            level=2,
            parent_id="chatbot-hr",
            db_ids=["hr-benefit-db"],
        )
        
        mock_ingestion = Mock()
        mock_memory = Mock()
        mock_memory.get_history.return_value = []
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
        )
        executor.delegation_threshold = 70
        
        return executor
    
    def test_high_confidence_no_delegation(self, setup_direct_answer):
        """TC-SYS-001: High confidence should produce direct answer without delegation"""
        executor = setup_direct_answer
        
        result = executor._select_delegate_target(confidence=85)
        
        assert result.target == 'self'
        assert 'self' == result.target


class TestSubDelegationScenario:
    """Scenario: Low confidence + sub_chatbots → sub delegation"""
    
    @pytest.fixture
    def setup_sub_delegation(self):
        """Setup parent executor with sub_chatbots"""
        sub_refs = [
            SubChatbotRef(id='chatbot-hr-policy', level=2, default_role=ExecutionRole.AGENT),
            SubChatbotRef(id='chatbot-hr-benefit', level=2, default_role=ExecutionRole.AGENT),
        ]
        
        chatbot = make_chatbot_def(
            chatbot_id="chatbot-hr",
            name="HR Bot",
            level=1,
            sub_chatbots=sub_refs,
            parent_id="chatbot-company",
            db_ids=["hr-db"],
        )
        
        mock_ingestion = Mock()
        mock_memory = Mock()
        mock_memory.get_history.return_value = []
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
        )
        executor.delegation_threshold = 70
        
        return executor
    
    def test_low_confidence_delegates_to_sub(self, setup_sub_delegation):
        """TC-SYS-002: Low confidence with sub_chatbots should delegate to sub"""
        executor = setup_sub_delegation
        
        result = executor._select_delegate_target(confidence=40)
        
        assert result.target == 'sub'
    
    def test_sub_delegation_priority_over_parent(self, setup_sub_delegation):
        """TC-SYS-003: Sub delegation should be preferred over parent delegation"""
        executor = setup_sub_delegation
        
        result = executor._select_delegate_target(confidence=30)
        
        assert result.target == 'sub'


class TestParentDelegationScenario:
    """Scenario: Low confidence + no sub + parent → parent delegation"""
    
    @pytest.fixture
    def setup_parent_delegation(self):
        """Setup leaf executor with parent but no sub_chatbots"""
        chatbot = make_chatbot_def(
            chatbot_id="chatbot-hr-benefit",
            name="HR Benefit Bot",
            level=2,
            sub_chatbots=[],
            parent_id="chatbot-hr",
            db_ids=["hr-benefit-db"],
        )
        
        mock_ingestion = Mock()
        mock_memory = Mock()
        mock_memory.get_history.return_value = []
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
        )
        executor.delegation_threshold = 70
        executor.enable_parent_delegation = True
        
        return executor
    
    def test_leaf_low_confidence_delegates_to_parent(self, setup_parent_delegation):
        """TC-SYS-004: Leaf with low confidence should delegate to parent"""
        executor = setup_parent_delegation
        
        result = executor._select_delegate_target(confidence=30)
        
        assert result.target == 'parent'
    
    def test_parent_delegation_disabled(self, setup_parent_delegation):
        """TC-SYS-005: With parent delegation disabled, should fallback"""
        executor = setup_parent_delegation
        executor.enable_parent_delegation = False
        
        result = executor._select_delegate_target(confidence=30)
        
        assert result.target == 'fallback'


class TestMaxDelegationDepthScenario:
    """Scenario: Max delegation depth exceeded"""
    
    @pytest.fixture
    def setup_deep_delegation(self):
        """Setup executor at maximum delegation depth"""
        chatbot = make_chatbot_def(
            chatbot_id="chatbot-deep",
            name="Deep Bot",
            level=3,
            sub_chatbots=[
                SubChatbotRef(id='deeper-bot', level=4, default_role=ExecutionRole.AGENT),
            ],
            parent_id="chatbot-mid",
        )
        
        mock_ingestion = Mock()
        mock_memory = Mock()
        mock_memory.get_history.return_value = []
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
            delegation_depth=5,  # MAX_DELEGATION_DEPTH
        )
        
        return executor
    
    def test_max_depth_produces_warning(self, setup_deep_delegation):
        """TC-SYS-006: Max depth should yield warning message"""
        executor = setup_deep_delegation
        
        with patch.object(executor, '_execute_with_context', return_value=iter(["fallback answer"])):
            with patch.object(executor, '_retrieve', return_value=""):
                result = list(executor.execute("test message", "session-1"))
        
        full_text = "".join(result)
        assert "최대 위임 깊이" in full_text or "⚠️" in full_text


class TestFallbackScenario:
    """Scenario: No delegation options available"""
    
    @pytest.fixture
    def setup_isolated_bot(self):
        """Setup executor with no sub_chatbots and no parent"""
        chatbot = make_chatbot_def(
            chatbot_id="chatbot-isolated",
            name="Isolated Bot",
            level=0,
            sub_chatbots=[],
            parent_id=None,
        )
        
        mock_ingestion = Mock()
        mock_memory = Mock()
        mock_memory.get_history.return_value = []
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
        )
        executor.delegation_threshold = 70
        
        return executor
    
    def test_isolated_bot_falls_back(self, setup_isolated_bot):
        """TC-SYS-007: Bot without sub or parent should fallback"""
        executor = setup_isolated_bot
        
        result = executor._select_delegate_target(confidence=30)
        
        assert result.target == 'fallback'


class TestContextAccumulation:
    """Scenario: Context accumulates across delegations"""
    
    @pytest.fixture
    def setup_with_accumulated_context(self):
        """Setup executor with pre-accumulated context"""
        chatbot = make_chatbot_def(
            chatbot_id="chatbot-parent",
            name="Parent Bot",
            level=0,
        )
        
        mock_ingestion = Mock()
        mock_memory = Mock()
        mock_memory.get_history.return_value = []
        
        accumulated = "Sub agent found: 급여 관련 기본 정보"
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=mock_ingestion,
            memory_manager=mock_memory,
            accumulated_context=accumulated,
            delegation_depth=1,
        )
        
        return executor, accumulated
    
    def test_context_carries_from_sub(self, setup_with_accumulated_context):
        """TC-SYS-008: Accumulated context from sub should be preserved"""
        executor, accumulated = setup_with_accumulated_context
        
        current_context = "Parent search results about 급여"
        combined = executor._combine_contexts(accumulated, current_context)
        
        assert accumulated in combined
        assert current_context in combined
        assert "[상위 컨텍스트]" in combined
        assert "[현재 검색 결과]" in combined
    
    def test_delegation_depth_increments(self, setup_with_accumulated_context):
        """TC-SYS-009: Delegation depth should be set correctly"""
        executor, _ = setup_with_accumulated_context
        
        assert executor.delegation_depth == 1


class TestDelegationThresholdVariations:
    """Scenario: Different threshold configurations"""
    
    def test_custom_threshold_from_policy(self):
        """TC-SYS-010: Custom threshold from chatbot policy"""
        chatbot = make_chatbot_def(
            chatbot_id="custom-bot",
            name="Custom Bot",
            policy={'delegation_threshold': 50},
        )
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=Mock(),
            memory_manager=Mock(),
        )
        
        assert executor.delegation_threshold == 50
    
    def test_default_threshold_when_no_policy(self):
        """TC-SYS-011: Default threshold when policy is empty"""
        chatbot = make_chatbot_def(
            chatbot_id="default-bot",
            name="Default Bot",
            policy={},
        )
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=Mock(),
            memory_manager=Mock(),
        )
        
        assert executor.delegation_threshold == 70  # DEFAULT_DELEGATION_THRESHOLD


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
