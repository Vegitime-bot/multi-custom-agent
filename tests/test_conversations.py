"""
tests/test_conversations.py - 대화 히스토리 API 테스트
"""
import pytest
import requests

BASE_URL = "http://localhost:8080"


class TestConversations:
    """대화 히스토리 API 테스트"""
    
    def test_get_session_conversations(self):
        """TC-CONV-001: 세션별 대화 내역 조회"""
        response = requests.get(f"{BASE_URL}/api/conversations/session/sess-001")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # 필수 필드 확인
        for log in data:
            assert "id" in log
            assert "session_id" in log
            assert "knox_id" in log
            assert "chatbot_id" in log
            assert "user_message" in log
            assert "assistant_response" in log
            
    def test_get_user_conversations(self):
        """TC-CONV-002: 사용자별 대화 내역 조회"""
        response = requests.get(f"{BASE_URL}/api/conversations/user/user-001")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # user-001의 대화만 포함
        for log in data:
            assert log["knox_id"] == "user-001"
            
    def test_get_chatbot_conversations(self):
        """TC-CONV-003: 챗봘별 대화 내역 조회"""
        response = requests.get(f"{BASE_URL}/api/conversations/chatbot/chatbot-hr")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # chatbot-hr의 대화만 포함
        for log in data:
            assert log["chatbot_id"] == "chatbot-hr"
            
    def test_get_conversation_stats(self):
        """TC-CONV-004: 대화 통계 조회"""
        response = requests.get(f"{BASE_URL}/api/conversations/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_conversations" in data
        assert "total_messages" in data
        assert "avg_latency_ms" in data
        assert "avg_confidence" in data
        assert "total_tokens" in data
        
    def test_get_user_conversation_stats(self):
        """TC-CONV-005: 특정 사용자 대화 통계"""
        response = requests.get(f"{BASE_URL}/api/conversations/stats?knox_id=user-001")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_messages"] >= 0
        
    def test_get_recent_conversations(self):
        """TC-CONV-006: 최근 대화 내역 조회"""
        response = requests.get(f"{BASE_URL}/api/conversations/recent?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10
        
    def test_conversation_pagination(self):
        """TC-CONV-007: 대화 내역 페이징"""
        response = requests.get(f"{BASE_URL}/api/conversations/user/user-001?limit=2")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) <= 2
        
    def test_conversation_response_format(self):
        """TC-CONV-008: 응답 형식 검증"""
        response = requests.get(f"{BASE_URL}/api/conversations/session/sess-001")
        data = response.json()
        
        if data:
            log = data[0]
            # created_at은 ISO 형식 문자열
            assert isinstance(log["created_at"], str)
            # confidence_score는 float 또는 null
            assert log["confidence_score"] is None or isinstance(log["confidence_score"], float)
            # delegated_to는 string 또는 null
            assert log["delegated_to"] is None or isinstance(log["delegated_to"], str)
            
    def test_conversation_limit_param(self):
        """TC-CONV-009: limit 파라미터 검증"""
        # 기본 limit
        response1 = requests.get(f"{BASE_URL}/api/conversations/user/user-001")
        assert response1.status_code == 200
        
        # 큰 limit
        response2 = requests.get(f"{BASE_URL}/api/conversations/user/user-001?limit=1000")
        assert response2.status_code == 200
        
    def test_nonexistent_session(self):
        """TC-CONV-010: 존재하지 않는 세션 조회"""
        response = requests.get(f"{BASE_URL}/api/conversations/session/nonexistent-99999")
        assert response.status_code == 200  # 빈 리스트 반환
        data = response.json()
        assert data == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
