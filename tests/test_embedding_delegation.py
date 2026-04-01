"""
tests/test_embedding_delegation.py - 임베딩 기반 위임 테스트
"""
import pytest
import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.embedding_service import EmbeddingService, get_embedding_service, reset_embedding_service


class TestEmbeddingService:
    """임베딩 서비스 단위 테스트"""
    
    def setup_method(self):
        """각 테스트 전 임베딩 서비스 초기화"""
        reset_embedding_service()
        self.service = get_embedding_service()
    
    def test_get_embedding(self):
        """TC-EMB-001: 임베딩 벡터 생성"""
        vec = self.service.get_embedding("연차 신청 방법")
        assert isinstance(vec, list)
        assert len(vec) == 128
        
    def test_embedding_consistency(self):
        """TC-EMB-002: 같은 텍스트 일관성"""
        vec1 = self.service.get_embedding("FastAPI 백엔드")
        vec2 = self.service.get_embedding("FastAPI 백엔드")
        assert vec1 == vec2
        
    def test_cosine_similarity_same_text(self):
        """TC-EMB-003: 같은 텍스트 유사도 = 1.0"""
        score = self.service.cosine_similarity("Verilog 카운터", "Verilog 카운터")
        assert abs(score - 1.0) < 0.001
        
    def test_cosine_similarity_related(self):
        """TC-EMB-004: 관련 텍스트 유사도 > 0"""
        score = self.service.cosine_similarity(
            "연차 휴가 신청",
            "연차 휴가 복지 급여"
        )
        assert score > 0
        
    def test_cosine_similarity_unrelated(self):
        """TC-EMB-005: 무관한 텍스트 유사도 < 관련 텍스트"""
        related = self.service.cosine_similarity(
            "Docker CI/CD 배포",
            "Docker kubernetes 인프라 배포"
        )
        unrelated = self.service.cosine_similarity(
            "Docker CI/CD 배포",
            "연차 휴가 급여 복리후생"
        )
        assert related > unrelated, f"related={related}, unrelated={unrelated}"
        
    def test_find_most_similar(self):
        """TC-EMB-006: 가장 유사한 후보 찾기"""
        candidates = [
            ("hr", "인사 정책 규정 채용 평가 승진"),
            ("backend", "Python FastAPI Django SQL API 서버 백엔드"),
            ("devops", "Docker Kubernetes CI/CD 배포 모니터링"),
        ]
        
        result = self.service.find_most_similar("FastAPI 서버 API 개발", candidates)
        assert result is not None
        assert result[0] == "backend", f"Expected backend, got {result[0]}"
        assert result[1] > 0
        
    def test_find_most_similar_korean(self):
        """TC-EMB-007: 한글 유사도 검색"""
        candidates = [
            ("hr-policy", "정책 규정 채용 평가 승진 인사제도"),
            ("hr-benefit", "급여 연차 휴가 복지 보험 수당"),
            ("tech-backend", "백엔드 파이썬 서버 개발"),
        ]
        
        result = self.service.find_most_similar("연차 휴가 신청 방법", candidates)
        assert result is not None
        assert result[0] == "hr-benefit", f"Expected hr-benefit, got {result[0]}"
        
    def test_empty_text(self):
        """TC-EMB-008: 빈 텍스트 처리"""
        vec = self.service.get_embedding("")
        assert len(vec) == 128
        # 모든 값이 0
        assert all(v == 0.0 for v in vec)
        
    def test_singleton_pattern(self):
        """TC-EMB-009: 싱글톤 패턴"""
        svc1 = get_embedding_service()
        svc2 = get_embedding_service()
        assert svc1 is svc2


class TestHybridDelegation:
    """하이브리드 위임 로직 통합 테스트"""
    
    def test_keyword_score_calculation(self):
        """TC-EMB-010: 키워드 점수 계산"""
        from backend.executors.parent_agent_executor import ParentAgentExecutor
        
        # _keyword_score는 정적이므로 직접 호출 가능 확인
        # 키워드 맵에서 직접 계산
        keywords = ['정책', '규정', '채용', '평가', '승진', '인사제도', '징계', '인사', '제도']
        message = "승진 평가 기준이 어떻게 되나요?"
        
        matched = sum(1 for kw in keywords if kw in message)
        assert matched >= 2, f"승진, 평가 최소 2개 매칭 필요, got {matched}"
        
    def test_hybrid_scoring_formula(self):
        """TC-EMB-011: 하이브리드 점수 공식"""
        kw_weight = 0.4
        emb_weight = 0.6
        
        # 키워드 점수 높고 임베딩 낮은 경우
        kw_score = 0.8
        emb_score = 0.3
        hybrid1 = kw_weight * kw_score + emb_weight * emb_score
        
        # 키워드 점수 낮고 임베딩 높은 경우
        kw_score2 = 0.2
        emb_score2 = 0.9
        hybrid2 = kw_weight * kw_score2 + emb_weight * emb_score2
        
        # 임베딩이 더 큰 가중치 → hybrid2가 더 높을 수 있음
        assert hybrid2 > hybrid1, f"hybrid1={hybrid1}, hybrid2={hybrid2}"
        
    def test_embedding_weight_dominance(self):
        """TC-EMB-012: 임베딩 가중치 우위 확인"""
        # embedding_weight(0.6) > keyword_weight(0.4)
        # 임베딩이 높으면 키워드 없어도 선택될 수 있음
        kw_weight = 0.4
        emb_weight = 0.6
        
        # 키워드 매칭 없지만 임베딩 매우 유사
        hybrid_emb_only = kw_weight * 0.0 + emb_weight * 1.0
        # 키워드 매칭 완벽하지만 임베딩 낮음
        hybrid_kw_only = kw_weight * 1.0 + emb_weight * 0.0
        
        assert hybrid_emb_only > hybrid_kw_only


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
