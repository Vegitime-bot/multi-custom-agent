"""
mock_ingestion_server.py - Mock Ingestion 서버 (포트 8001)
새 API 스펙:
{
  "query": "string",
  "index_names": ["string"],
  "top_k": 5,
  "threshold": 0
}

실행:
    uvicorn mock_ingestion_server:app --port 8001
"""
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Ingestion Server", version="2.0.0")


# ── 목업 데이터 ────────────────────────────────────────────────────
MOCK_DATA: dict[str, list[dict]] = {
    "db_001": [
        {"doc_id": "a1", "content": "FastAPI는 Python 기반의 고성능 웹 프레임워크입니다. 비동기 처리를 지원하며 자동 API 문서 생성 기능이 있습니다.", "source": "tech_doc_001.txt"},
        {"doc_id": "a2", "content": "uvicorn은 ASGI 서버로 FastAPI와 함께 사용됩니다. 고성능 비동기 웹 서버로 Gunicorn과 함께 프로덕션에서 사용됩니다.", "source": "tech_doc_002.txt"},
    ],
    "db_002": [
        {"doc_id": "b1", "content": "SQLAlchemy는 Python ORM 라이브러리입니다. 관계형 데이터베이스와 객체 간 매핑을 제공합니다.", "source": "dev_guide_001.txt"},
        {"doc_id": "b2", "content": "PostgreSQL은 오픈소스 관계형 데이터베이스입니다. JSONB 지원, 트랜잭션, 복제 기능이 강력합니다.", "source": "dev_guide_002.txt"},
    ],
    "db_003": [
        {"doc_id": "c1", "content": "연차 신청은 사내 포털을 통해 진행합니다. 신청은 최소 3일 전에 해야 하며, 팀장 승인이 필요합니다.", "source": "hr_policy_001.txt"},
        {"doc_id": "c2", "content": "복리후생 안내: 의료비 지원(연간 100만원 한도), 교육비 지원, 경조사 지원, 휴양비 지원이 있습니다.", "source": "hr_policy_002.txt"},
    ],
    # ========== HR Policy 전문 DB ==========
    "db_hr_policy": [
        {"doc_id": "hr_p1", "content": "인사평가제도: 연 2회(상반기/하반기) 자기평가-상사평가-면담 순으로 진행. 평가 항목: 업무성과(60%), 역량(25%), 태도(15%).", "source": "hr_policy_detail.txt"},
        {"doc_id": "hr_p2", "content": "채용 프로세스: 서류전형-1차 면접-2차 면접-최종 합격. 채용공고는 사내 포털 및 외부 채용사이트에 게시.", "source": "recruitment_guide.txt"},
    ],
    # ========== HR Benefit 전문 DB ==========
    "db_hr_benefit": [
        {"doc_id": "hr_b1", "content": "급여체계: 기본급 + 직급수당 + 성과급 + 기타수당. 매월 25일 지급. 연봉협상은 연말에 진행.", "source": "salary_guide.txt"},
        {"doc_id": "hr_b2", "content": "연차휴가: 입사 후 1년 근무 시 15일 발생. 3년 이상 근무 시 2년마다 1일씩 가산(최대 25일).", "source": "annual_leave_policy.txt"},
    ],
    # ========== HR Overview (상위 Agent용) ==========
    "db_hr_overview": [
        {"doc_id": "hr_ov1", "content": "인사팀 주요 업무: 채용, 교육, 평가, 승진, 복리후생, 노무관리. 사내 인사제도 총괄.", "source": "hr_overview.txt"},
    ],
    # ========== Tech Backend 전문 DB ==========
    "db_backend": [
        {"doc_id": "be_1", "content": "FastAPI ORM: SQLAlchemy와 함께 사용. SessionLocal으로 DB 세션 관리, Depends로 의존성 주입.", "source": "fastapi_db_guide.txt"},
    ],
    # ========== Tech Frontend 전문 DB ==========
    "db_frontend": [
        {"doc_id": "fe_1", "content": "React Hooks: useState(상태관리), useEffect(사이드이펙트), useContext(전역상태), useRef(DOM접근).", "source": "react_hooks.txt"},
    ],
    # ========== Tech DevOps 전문 DB ==========
    "db_devops": [
        {"doc_id": "do_1", "content": "Docker 이미지 최적화: 멀티스테이지 빌드, .dockerignore 사용, 작은 베이스 이미지(alpine) 선택.", "source": "docker_best_practice.txt"},
    ],
    # ========== Tech Overview (상위 Agent용) ==========
    "db_tech_overview": [
        {"doc_id": "tech_ov1", "content": "기술지원팀: 소프트웨어 개발(FastAPI, Python, DB), 프론트엔드(React, Vue), 인프라(Docker, K8s) 지원.", "source": "tech_overview.txt"},
    ],
}


# ── 새 요청 스키마 ────────────────────────────────────────────────
class SearchRequest(BaseModel):
    """통합 검색 요청"""
    query: str
    index_names: list[str]
    top_k: int = 5
    threshold: float = 0.0


# ── 검색 헬퍼 ─────────────────────────────────────────────────────
def _search_index(index_name: str, query: str, top_k: int, threshold: float) -> list[dict]:
    """지정된 인덱스에서 목업 결과를 반환한다."""
    results = MOCK_DATA.get(index_name, [])
    query_lower = query.lower()
    scored = []
    
    for doc in results:
        # 간단한 키워드 매칭으로 스코어 계산
        content_lower = doc["content"].lower()
        if query_lower in content_lower:
            score = 0.8 + 0.2 * (len(query_lower) / len(content_lower))
        else:
            # 키워드 부분 매칭
            query_words = query_lower.split()
            matches = sum(1 for word in query_words if len(word) > 1 and word in content_lower)
            score = 0.3 * (matches / max(len(query_words), 1))
        
        if score >= threshold:
            scored.append({
                **doc,
                "score": round(score, 3),
                "index_name": index_name,
            })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ── 통합 검색 API (신규 스펙) ───────────────────────────────────
@app.post("/search")
async def search(req: SearchRequest):
    """
    통합 검색 API
    POST /search
    {
      "query": "string",
      "index_names": ["string"],
      "top_k": 5,
      "threshold": 0
    }
    """
    if not req.index_names:
        return {
            "query": req.query,
            "index_names": [],
            "total_results": 0,
            "results": [],
        }
    
    all_results = []
    for index_name in req.index_names:
        results = _search_index(index_name, req.query, req.top_k, req.threshold)
        all_results.extend(results)
    
    # 전체 결과를 score 기준으로 재정렬
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # 전체 중 top_k 개만 반환
    final_results = all_results[:req.top_k]
    
    return {
        "query": req.query,
        "index_names": req.index_names,
        "total_results": len(final_results),
        "results": final_results,
    }


# ── 하위호환성 유지 (선택적) ──────────────────────────────────────
class LegacySearchRequest(BaseModel):
    """하위호환성용 레거시 요청"""
    query: str
    db_ids: list[str]


@app.post("/search/legacy")
async def search_legacy(req: LegacySearchRequest):
    """구 API 호환용"""
    results = []
    for db_id in req.db_ids:
        results.extend(_search_index(db_id, req.query, 10, 0.0))
    return {
        "query": req.query,
        "db_ids_received": req.db_ids,
        "results": results,
    }


# ── 헬스체크 ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "available_indices": list(MOCK_DATA.keys()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mock_ingestion_server:app", host="0.0.0.0", port=8001, reload=False)
