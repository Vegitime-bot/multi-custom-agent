"""
mock_ingestion_server.py - Mock Ingestion 서버 (포트 8001)
docs/TESTING.md 기준으로 구현.
INGESTION_API.md 명세(단일 DB / 다중 DB)를 모두 지원한다.

실행:
    uvicorn mock_ingestion_server:app --port 8001
"""
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Mock Ingestion Server", version="1.0.0")


# ── 목업 데이터 ────────────────────────────────────────────────────
MOCK_DATA: dict[str, list[dict]] = {
    "db_001": [
        {"doc_id": "a1", "content": "FastAPI는 Python 기반의 고성능 웹 프레임워크입니다. 비동기 처리를 지원하며 자동 API 문서 생성 기능이 있습니다.", "source": "tech_doc_001.txt"},
        {"doc_id": "a2", "content": "uvicorn은 ASGI 서버로 FastAPI와 함께 사용됩니다. 고성능 비동기 웹 서버로 Gunicorn과 함께 프로덕션에서 사용됩니다.", "source": "tech_doc_002.txt"},
        {"doc_id": "a3", "content": "Pydantic은 Python용 데이터 검증 라이브러리입니다. 타입 힌트를 기반으로 데이터 모델을 정의하고 검증합니다.", "source": "tech_doc_003.txt"},
        {"doc_id": "a4", "content": "Python 3.9 이상의 버전을 권장합니다. typing 모듈의 새로운 기능들을 활용할 수 있습니다.", "source": "tech_doc_004.txt"},
        {"doc_id": "a5", "content": "Docker와 Kubernetes를 활용한 컨테이너 배포를 지원합니다. CI/CD 파이프라인과 쉽게 통합됩니다.", "source": "tech_doc_005.txt"},
    ],
    "db_002": [
        {"doc_id": "b1", "content": "SQLAlchemy는 Python ORM 라이브러리입니다. 관계형 데이터베이스와 객체 간 매핑을 제공합니다.", "source": "dev_guide_001.txt"},
        {"doc_id": "b2", "content": "PostgreSQL은 오픈소스 관계형 데이터베이스입니다. JSONB 지원, 트랜잭션, 복제 기능이 강력합니다.", "source": "dev_guide_002.txt"},
        {"doc_id": "b3", "content": "Redis는 인메모리 데이터 저장소입니다. 캐싱, 세션 관리, 메시지 브로커로 활용됩니다.", "source": "dev_guide_003.txt"},
        {"doc_id": "b4", "content": "Git 브랜치 전략: main(master), develop, feature, release, hotfix 브랜치를 활용한 Git Flow 전략을 권장합니다.", "source": "dev_guide_004.txt"},
        {"doc_id": "b5", "content": "JWT(Json Web Token)는 인증 및 인가에 사용됩니다. Access Token과 Refresh Token을 분리하여 관리하세요.", "source": "dev_guide_005.txt"},
    ],
    "db_003": [
        {"doc_id": "c1", "content": "연차 신청은 사내 포털을 통해 진행합니다. 신청은 최소 3일 전에 해야 하며, 팀장 승인이 필요합니다.", "source": "hr_policy_001.txt"},
        {"doc_id": "c2", "content": "복리후생 안내: 의료비 지원(연간 100만원 한도), 교육비 지원, 경조사 지원, 휴양비 지원이 있습니다.", "source": "hr_policy_002.txt"},
        {"doc_id": "c3", "content": "재택근무 규정: 주 2회까지 가능하며, 사전에 팀장과 협의 필요. 코어타임은 10:00-15:00입니다.", "source": "hr_policy_003.txt"},
        {"doc_id": "c4", "content": "성과 평가: 상반기(6월), 하반기(12월) 2회 진행됩니다. 자기 평가와 상사 평가를 포함합니다.", "source": "hr_policy_004.txt"},
        {"doc_id": "c5", "content": "사내 교육: 매월 마지막 금요일 기술 세미나, 외부 교육비 연간 50만원 지원, 온라인 강의 플랫폼 무료 제공.", "source": "hr_policy_005.txt"},
    ],
    "db_004": [
        {"doc_id": "d1", "content": "반도체 설계: RTL(Register Transfer Level) 설계는 하드웨어를 레지스터와 논리 게이트 수준으로 기술합니다.", "source": "rtl_doc_001.txt"},
        {"doc_id": "d2", "content": "Verilog HDL은 하드웨어 기술 언어입니다. 디지털 회로를 모듈 단위로 설계하고 시뮬레이션할 수 있습니다.", "source": "rtl_doc_002.txt"},
        {"doc_id": "d3", "content": "SystemVerilog는 Verilog의 확장입니다. 객체 지향 프로그래밍 지원, Assertion, Coverage 기능이 추가되었습니다.", "source": "rtl_doc_003.txt"},
    ],
    "db_005": [
        {"doc_id": "e1", "content": "AI Agent 아키텍처: RAG(Retrieval-Augmented Generation)는 외부 지식을 검색하여 LLM 응답을 보강하는 기법입니다.", "source": "ai_doc_001.txt"},
        {"doc_id": "e2", "content": "멀티 테넌트 시스템: 하나의 인프라에서 여러 고객(테넌트)의 데이터를 격리하여 관리하는 아키텍처입니다.", "source": "ai_doc_002.txt"},
        {"doc_id": "e3", "content": "Factory Method 패턴: 객체 생성 로직을 캡슐화하여 런타임에 다양한 구현체를 생성할 수 있게 합니다.", "source": "ai_doc_003.txt"},
    ],
}


# ── 요청 스키마 ────────────────────────────────────────────────────
class SingleSearchRequest(BaseModel):
    query: str
    k: int = 10
    filter_metadata: Optional[dict] = None


class MultiSearchRequest(BaseModel):
    query: str
    k: int = 10
    db_ids: Optional[list[str]] = None
    filter_metadata: Optional[dict] = None


# ── 검색 헬퍼 ─────────────────────────────────────────────────────
def _search_db(db_id: str, query: str, k: int) -> list[dict]:
    """지정된 DB에서 목업 결과를 반환한다 (실제 검색 없이 전체 반환)."""
    results = MOCK_DATA.get(db_id, [])
    # 실제 환경에서는 벡터 유사도 기반 검색; 여기서는 쿼리 단어 포함 여부로 간단 필터
    query_lower = query.lower()
    scored = []
    for doc in results:
        score = 1.0 if query_lower in doc["content"].lower() else 0.5
        scored.append({**doc, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


# ── 단일 DB 검색 (POST) ───────────────────────────────────────────
@app.post("/databases/{db_id}/search")
async def search_single_post(db_id: str, req: SingleSearchRequest):
    results = _search_db(db_id, req.query, req.k)
    return {
        "db_id": db_id,
        "query": req.query,
        "results": results,
    }


# ── 단일 DB 검색 (GET) ────────────────────────────────────────────
@app.get("/databases/{db_id}/search")
async def search_single_get(
    db_id: str,
    query: str = Query(...),
    k: int = Query(10),
):
    results = _search_db(db_id, query, k)
    return {
        "db_id": db_id,
        "query": query,
        "results": results,
    }


# ── 다중 DB 검색 ──────────────────────────────────────────────────
@app.post("/search/multi")
async def search_multi(req: MultiSearchRequest):
    # db_ids=None → 모든 DB 검색
    target_ids = req.db_ids if req.db_ids is not None else list(MOCK_DATA.keys())

    # 빈 배열 → 빈 결과
    if req.db_ids is not None and len(req.db_ids) == 0:
        return {"query": req.query, "db_ids_received": [], "results": []}

    results = []
    for db_id in target_ids:
        if db_id in MOCK_DATA:  # 존재하지 않는 DB ID는 무시
            results.extend(_search_db(db_id, req.query, req.k))

    # 점수 기준 재정렬
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {
        "query": req.query,
        "db_ids_received": target_ids,
        "results": results,
    }


# ── TESTING.md 호환 /search 엔드포인트 ───────────────────────────
class LegacySearchRequest(BaseModel):
    query: str
    db_ids: list[str]


@app.post("/search")
async def search_legacy(req: LegacySearchRequest):
    """docs/TESTING.md의 옵션 A 호환 엔드포인트"""
    results = []
    for db_id in req.db_ids:
        results.extend(MOCK_DATA.get(db_id, []))
    return {
        "query": req.query,
        "db_ids_received": req.db_ids,
        "results": results,
    }


# ── 헬스체크 ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "available_dbs": list(MOCK_DATA.keys())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mock_ingestion_server:app", host="0.0.0.0", port=8001, reload=False)
