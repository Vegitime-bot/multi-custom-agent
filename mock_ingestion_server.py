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
        {"doc_id": "a1", "content": "FastAPI는 Python 기반의 고성능 웹 프레임워크입니다.", "source": "tech_doc_001.txt"},
        {"doc_id": "a2", "content": "uvicorn은 ASGI 서버로 FastAPI와 함께 사용됩니다.", "source": "tech_doc_002.txt"},
    ],
    "db_002": [
        {"doc_id": "b1", "content": "SQLAlchemy는 Python ORM 라이브러리입니다.", "source": "dev_guide_001.txt"},
        {"doc_id": "b2", "content": "PostgreSQL은 오픈소스 관계형 데이터베이스입니다.", "source": "dev_guide_002.txt"},
    ],
    "db_003": [
        {"doc_id": "c1", "content": "연차 신청은 사내 포털을 통해 진행합니다.", "source": "hr_policy_001.txt"},
        {"doc_id": "c2", "content": "복리후생 안내: 의료비 지원, 교육비 지원 등.", "source": "hr_policy_002.txt"},
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
