# Ingestion 서버 API 명세

> 챗봇 서버가 Ingestion 서버에 검색을 요청할 때 사용하는 API

---

## Base URL

```
http://<ingestion-server-host>:5500
```

> SSL 비활성화 적용 필요 (verify=False)

---

## 5.1 단일 DB 검색

### POST /databases/{db_id}/search

지정된 DB에서 검색.

**요청:**
```http
POST /databases/{db_id}/search
Content-Type: application/json

{
  "query": "검색어",
  "k": 10,
  "filter_metadata": {"category": "기술"}
}
```

**파라미터:**
| 파라미터 | 필수 | 설명 |
|---------|------|------|
| db_id | ✅ (path) | 검색할 DB ID |
| query | ✅ | 검색 쿼리 |
| k | ❌ | 반환할 결과 수 (기본값: 10) |
| filter_metadata | ❌ | 메타데이터 필터 |

---

### GET /databases/{db_id}/search

GET 방식 검색 (쿼리 파라미터 사용).

**요청:**
```bash
curl "http://localhost:5500/databases/project_a/search?query=FAISS&k=5"
```

---

## 5.2 다중 DB 검색

### POST /search/multi

여러 DB에서 동시에 검색. 하나 또는 여러 DB 선택 가능.

**요청:**
```http
POST /search/multi
Content-Type: application/json

{
  "query": "검색어",
  "k": 10,
  "db_ids": ["project_a", "project_b"],
  "filter_metadata": {"category": "기술"}
}
```

**파라미터:**
| 파라미터 | 필수 | 설명 |
|---------|------|------|
| query | ✅ | 검색 쿼리 |
| k | ❌ | 각 DB별 반환할 결과 수 (기본값: 10) |
| db_ids | ❌ | 검색할 DB ID 목록 |
| filter_metadata | ❌ | 메타데이터 필터 |

**db_ids 동작 규칙:**
- 미제공 (`null`): 모든 DB 검색
- 빈 배열 `[]`: 빈 결과 반환
- 존재하지 않는 DB ID: 자동으로 무시

---

## 챗봇-DB 매핑 전략

챗봇 정의(JSON)에서 각 챗봇이 검색할 `db_ids`를 선언형으로 지정:

```json
{
  "id": "chatbot-a",
  "retrieval": {
    "db_ids": ["project_a", "project_b"],
    "k": 5,
    "filter_metadata": {}
  }
}
```

- 단일 DB 챗봇 → `POST /databases/{db_id}/search`
- 다중 DB 챗봇 → `POST /search/multi`

---

_관련 문서: [ARCHITECTURE.md](./ARCHITECTURE.md) | [ENV.md](./ENV.md)_
