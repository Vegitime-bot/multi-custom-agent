"""
test_hierarchical_delegation.py - 3-Tier Hierarchy 테스트

테스트 항목:
1. 3-tier delegation chain
2. Circular reference prevention
3. Max depth enforcement
4. Context accumulation across levels
5. Hierarchy traversal methods
"""
import pytest
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.models import ChatbotDef, ExecutionRole, RetrievalConfig, LLMConfig, MemoryConfig
from backend.managers.chatbot_manager import ChatbotManager


class TestHierarchyStructure:
    """계층 구조 모델 테스트"""
    
    def test_chatbotdef_has_hierarchy_fields(self):
        """ChatbotDef에 hierarchy 필드가 있는지 확인"""
        chatbot = ChatbotDef(
            id="test-bot",
            name="Test Bot",
            description="Test",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            parent_id="parent-bot",
            level=2,
        )
        
        assert chatbot.parent_id == "parent-bot"
        assert chatbot.level == 2
        assert not chatbot.is_root
        assert chatbot.is_leaf  # sub_chatbots가 비어있음
    
    def test_root_chatbot_properties(self):
        """Root 챗봉 속성 테스트"""
        root = ChatbotDef(
            id="root-bot",
            name="Root Bot",
            description="Root",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            parent_id=None,
            level=0,
        )
        
        assert root.is_root
        assert root.level == 0
        assert root.parent_id is None
    
    def test_is_leaf_with_sub_chatbots(self):
        """sub_chatbots가 있으면 is_leaf=False"""
        from backend.core.models import SubChatbotRef
        
        parent = ChatbotDef(
            id="parent-bot",
            name="Parent Bot",
            description="Parent",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            sub_chatbots=[
                SubChatbotRef(id="child1", level=1, default_role=ExecutionRole.AGENT)
            ],
            level=1,
        )
        
        assert not parent.is_leaf
    
    def test_to_dict_includes_hierarchy_fields(self):
        """to_dict()에 hierarchy 필드가 포함되는지 확인"""
        chatbot = ChatbotDef(
            id="test-bot",
            name="Test Bot",
            description="Test",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            parent_id="parent",
            level=2,
        )
        
        data = chatbot.to_dict()
        assert "parent_id" in data
        assert "level" in data
        assert data["parent_id"] == "parent"
        assert data["level"] == 2
    
    def test_from_dict_parses_hierarchy_fields(self):
        """from_dict()이 hierarchy 필드를 파싱하는지 확인"""
        data = {
            "id": "test-bot",
            "name": "Test Bot",
            "description": "Test",
            "role": "agent",
            "active": True,
            "retrieval": {"db_ids": ["db1"], "k": 5, "filter_metadata": {}},
            "llm": {"model": "test", "temperature": 0.3, "max_tokens": 1024, "stream": True},
            "memory": {"enabled": True, "max_messages": 20},
            "system_prompt": "Test",
            "sub_chatbots": [],
            "parent_id": "parent-bot",
            "level": 2,
        }
        
        chatbot = ChatbotDef.from_dict(data)
        assert chatbot.parent_id == "parent-bot"
        assert chatbot.level == 2


class TestChatbotManagerHierarchy:
    """ChatbotManager 계층 기능 테스트"""
    
    @pytest.fixture
    def temp_manager(self, tmp_path):
        """임시 ChatbotManager 생성"""
        chatbots_dir = tmp_path / "chatbots"
        chatbots_dir.mkdir()
        
        # Create test chatbot files
        (chatbots_dir / "chatbot-company.json").write_text("""
        {
            "id": "chatbot-company",
            "name": "Company Root",
            "description": "Root chatbot",
            "role": "agent",
            "active": true,
            "retrieval": {"db_ids": ["db1"], "k": 5, "filter_metadata": {}},
            "llm": {"model": "test", "temperature": 0.3, "max_tokens": 1024, "stream": true},
            "memory": {"enabled": true, "max_messages": 20},
            "system_prompt": "Root",
            "sub_chatbots": [],
            "parent_id": null,
            "level": 0
        }
        """)
        
        (chatbots_dir / "chatbot-hr.json").write_text("""
        {
            "id": "chatbot-hr",
            "name": "HR Parent",
            "description": "HR parent",
            "role": "agent",
            "active": true,
            "retrieval": {"db_ids": ["db2"], "k": 5, "filter_metadata": {}},
            "llm": {"model": "test", "temperature": 0.3, "max_tokens": 1024, "stream": true},
            "memory": {"enabled": true, "max_messages": 20},
            "system_prompt": "HR",
            "sub_chatbots": [],
            "parent_id": "chatbot-company",
            "level": 1
        }
        """)
        
        (chatbots_dir / "chatbot-hr-policy.json").write_text("""
        {
            "id": "chatbot-hr-policy",
            "name": "HR Policy Child",
            "description": "HR policy",
            "role": "agent",
            "active": true,
            "retrieval": {"db_ids": ["db3"], "k": 5, "filter_metadata": {}},
            "llm": {"model": "test", "temperature": 0.3, "max_tokens": 1024, "stream": true},
            "memory": {"enabled": true, "max_messages": 20},
            "system_prompt": "Policy",
            "sub_chatbots": [],
            "parent_id": "chatbot-hr",
            "level": 2
        }
        """)
        
        return ChatbotManager(chatbots_dir)
    
    def test_get_parent_chain(self, temp_manager):
        """get_parent_chain 테스트"""
        chain = temp_manager.get_parent_chain("chatbot-hr-policy")
        
        assert len(chain) == 3
        assert chain[0].id == "chatbot-company"  # Root
        assert chain[1].id == "chatbot-hr"       # Parent
        assert chain[2].id == "chatbot-hr-policy" # Self
    
    def test_get_children(self, temp_manager):
        """get_children 테스트"""
        children = temp_manager.get_children("chatbot-company")
        
        assert len(children) == 1
        assert children[0].id == "chatbot-hr"
    
    def test_get_descendants(self, temp_manager):
        """get_descendants 테스트"""
        descendants = temp_manager.get_descendants("chatbot-company")
        
        ids = [d.id for d in descendants]
        assert "chatbot-hr" in ids
        assert "chatbot-hr-policy" in ids
        assert len(descendants) == 2
    
    def test_get_ancestors(self, temp_manager):
        """get_ancestors 테스트"""
        ancestors = temp_manager.get_ancestors("chatbot-hr-policy")
        
        assert len(ancestors) == 2
        assert ancestors[0].id == "chatbot-company"  # Root
        assert ancestors[1].id == "chatbot-hr"       # Parent
    
    def test_get_root(self, temp_manager):
        """get_root 테스트"""
        root = temp_manager.get_root("chatbot-hr-policy")
        
        assert root is not None
        assert root.id == "chatbot-company"
    
    def test_get_tree(self, temp_manager):
        """get_tree 테스트"""
        tree = temp_manager.get_tree("chatbot-company")
        
        assert "chatbot" in tree
        assert "children" in tree
        assert tree["chatbot"].id == "chatbot-company"
    
    def test_circular_reference_detection(self, temp_manager):
        """순환 참조 방지 테스트"""
        # Create a bot that would create a cycle
        cycle_bot = ChatbotDef(
            id="chatbot-company",  # Try to set root's parent
            name="Cycle",
            description="Test",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            parent_id="chatbot-hr-policy",  # Would create cycle
            level=3,
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            temp_manager.save(cycle_bot)
        
        assert "순환 참조" in str(exc_info.value)
    
    def test_max_depth_enforcement(self, temp_manager):
        """최대 깊이 제한 테스트"""
        # Create chain that exceeds MAX_HIERARCHY_DEPTH
        level_4 = ChatbotDef(
            id="level-4",
            name="Level 4",
            description="Test",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            parent_id="chatbot-hr-policy",  # Level 2's child = Level 3
            level=3,
        )
        
        # Should succeed (level 3 is within limit of 5)
        temp_manager.save(level_4)
        
        # Try to create level 6 (exceeds limit)
        level_5 = ChatbotDef(
            id="level-5",
            name="Level 5",
            description="Test",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            parent_id="level-4",
            level=4,
        )
        temp_manager.save(level_5)
        
        # This should fail (depth 6)
        level_6 = ChatbotDef(
            id="level-6",
            name="Level 6",
            description="Test",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            parent_id="level-5",
            level=5,
        )
        
        with pytest.raises(ValueError) as exc_info:
            temp_manager.save(level_6)
        
        assert "최대 깊이" in str(exc_info.value)
    
    def test_get_siblings(self, temp_manager):
        """get_siblings 테스트"""
        # Create sibling
        hr_benefit = ChatbotDef(
            id="chatbot-hr-benefit",
            name="HR Benefit",
            description="Benefit",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Benefit",
            parent_id="chatbot-hr",
            level=2,
        )
        temp_manager.save(hr_benefit)
        
        siblings = temp_manager.get_siblings("chatbot-hr-policy")
        
        assert len(siblings) == 1
        assert siblings[0].id == "chatbot-hr-benefit"
    
    def test_get_leaves(self, temp_manager):
        """get_leaves 테스트"""
        leaves = temp_manager.get_leaves("chatbot-company")
        
        # chatbot-hr-policy is the only leaf in this tree
        ids = [l.id for l in leaves]
        assert "chatbot-hr-policy" in ids


class TestHierarchicalExecutor:
    """HierarchicalAgentExecutor 테스트"""
    
    def test_executor_imports(self):
        """Executor가 정상적으로 import되는지 확인"""
        from backend.executors.hierarchical_agent_executor import HierarchicalAgentExecutor
        from backend.executors.parent_agent_executor import ParentAgentExecutor
        
        # ParentAgentExecutor는 HierarchicalAgentExecutor를 상속
        assert issubclass(ParentAgentExecutor, HierarchicalAgentExecutor)
    
    def test_executor_has_delegation_depth(self):
        """Executor에 delegation_depth 필드가 있는지 확인"""
        from backend.executors.hierarchical_agent_executor import HierarchicalAgentExecutor
        from unittest.mock import MagicMock
        
        chatbot = ChatbotDef(
            id="test",
            name="Test",
            description="Test",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
            parent_id="parent",
            level=2,
        )
        
        ingestion = MagicMock()
        memory = MagicMock()
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=ingestion,
            memory_manager=memory,
            chatbot_manager=None,
            accumulated_context="previous context",
            delegation_depth=2,
        )
        
        assert executor.delegation_depth == 2
        assert executor.accumulated_context == "previous context"
        assert executor.enable_parent_delegation is True


class TestContextAccumulation:
    """Context 누적 테스트"""
    
    def test_combine_contexts(self):
        """컨텍스트 결합 테스트"""
        from backend.executors.hierarchical_agent_executor import HierarchicalAgentExecutor
        from unittest.mock import MagicMock
        
        chatbot = ChatbotDef(
            id="test",
            name="Test",
            description="Test",
            role=ExecutionRole.AGENT,
            active=True,
            retrieval=RetrievalConfig(db_ids=["db1"]),
            llm=LLMConfig(model="test"),
            memory=MemoryConfig(),
            system_prompt="Test",
        )
        
        executor = HierarchicalAgentExecutor(
            chatbot_def=chatbot,
            ingestion_client=MagicMock(),
            memory_manager=MagicMock(),
        )
        
        # Both contexts present
        combined = executor._combine_contexts("accumulated", "current")
        assert "[상위 컨텍스트]" in combined
        assert "accumulated" in combined
        assert "[현재 검색 결과]" in combined
        assert "current" in combined
        
        # Only accumulated
        combined = executor._combine_contexts("accumulated", "")
        assert combined == "accumulated"
        
        # Only current
        combined = executor._combine_contexts("", "current")
        assert combined == "current"
        
        # Neither
        combined = executor._combine_contexts("", "")
        assert combined == ""


class TestBackwardCompatibility:
    """하위 호환성 테스트"""
    
    def test_legacy_chatbot_without_hierarchy_fields(self):
        """hierarchy 필드 없는 legacy 데이터 처리"""
        data = {
            "id": "legacy-bot",
            "name": "Legacy Bot",
            "description": "Legacy",
            "role": "agent",
            "active": True,
            "retrieval": {"db_ids": ["db1"], "k": 5, "filter_metadata": {}},
            "llm": {"model": "test", "temperature": 0.3, "max_tokens": 1024, "stream": True},
            "memory": {"enabled": True, "max_messages": 20},
            "system_prompt": "Legacy",
            "sub_chatbots": [],
            # No parent_id or level
        }
        
        chatbot = ChatbotDef.from_dict(data)
        
        # Should default to None and 0
        assert chatbot.parent_id is None
        assert chatbot.level == 0
        assert chatbot.is_root


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
