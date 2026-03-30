from __future__ import annotations
"""
retrieval/ingestion_client.py - Ingestion 서버 API 클라이언트
INGESTION_API.md 기준으로 단일 DB / 다중 DB 검색 요청을 처리한다.
SSL verify=False (사내망 설정)
"""
import requests
import urllib3

from backend.config import settings

# 사내망 SSL 경고 억제
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class IngestionClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or settings.INGESTION_BASE_URL).rstrip("/")
        self._session = requests.Session()
        self._session.verify = settings.SSL_VERIFY

    def search_single(
        self,
        db_id: str,
        query: str,
        k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """
        POST /databases/{db_id}/search
        단일 DB 검색
        """
        payload: dict = {"query": query, "k": k}
        if filter_metadata:
            payload["filter_metadata"] = filter_metadata

        try:
            resp = self._session.post(
                f"{self._base_url}/databases/{db_id}/search",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data if isinstance(data, list) else [])
        except Exception as e:
            print(f"[IngestionClient] search_single 오류 (db_id={db_id}): {e}")
            return []

    def search_multi(
        self,
        db_ids: list[str],
        query: str,
        k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """
        POST /search/multi
        다중 DB 검색
        db_ids가 1개면 단일 검색으로 대체한다.
        """
        if not db_ids:
            return []

        if len(db_ids) == 1:
            return self.search_single(
                db_id=db_ids[0],
                query=query,
                k=k,
                filter_metadata=filter_metadata,
            )

        payload: dict = {"query": query, "k": k, "db_ids": db_ids}
        if filter_metadata:
            payload["filter_metadata"] = filter_metadata

        try:
            resp = self._session.post(
                f"{self._base_url}/search/multi",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data if isinstance(data, list) else [])
        except Exception as e:
            print(f"[IngestionClient] search_multi 오류 (db_ids={db_ids}): {e}")
            return []

    def search(
        self,
        db_ids: list[str],
        query: str,
        k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """
        챗봇 정의의 db_ids 수에 따라 자동으로 단일/다중 검색을 선택한다.
        """
        if len(db_ids) == 1:
            return self.search_single(db_ids[0], query, k, filter_metadata)
        return self.search_multi(db_ids, query, k, filter_metadata)


def format_context(results: list[dict]) -> str:
    """검색 결과를 LLM 프롬프트에 삽입할 컨텍스트 문자열로 변환한다."""
    if not results:
        return "관련 문서를 찾지 못했습니다."
    lines = []
    for i, r in enumerate(results, 1):
        content = r.get("content", r.get("text", str(r)))
        source = r.get("source", r.get("doc_id", ""))
        lines.append(f"[{i}] {content}" + (f"  (출처: {source})" if source else ""))
    return "\n\n".join(lines)
