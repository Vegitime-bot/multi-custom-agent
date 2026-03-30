# Multi Custom Agent Service

멀티 테넌트 RAG 챗봇 플랫폼입니다.

## 서버 실행 방법

### 1. 환경 설정

```bash
cd multi-custom-agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 환경변수 설정 (선택)

```bash
# 기본 포트: 8080
export PORT=8080

# 또는 .env 파일 생성
cp .env.example .env
# .env 파일 수정
```

### 3. 서버 실행

**방법 1: uvicorn 직접 실행 (권장)**

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

**방법 2: main.py 직접 실행**

```bash
python backend/main.py
```

### 4. 접속

- 챗봇 UI: `http://localhost:8080`
- API 문서: `http://localhost:8080/docs`
- API: `http://localhost:8080/api/chatbots`

## API 엔드포인트

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/chatbots` | 활성 챗봇 목록 |
| `POST /api/chat` | 챗봇 대화 (SSE 스트리밍) |
| `POST /api/sessions` | 세션 생성 |
| `GET /api/sessions/{id}/history` | 대화 기록 |
| `GET /api/admin/chatbots` | 전체 챗봇 관리 |

## 디렉토리 구조

```
multi-custom-agent/
├── backend/          # FastAPI 서버
│   ├── api/         # API 라우터
│   ├── managers/    # 챗봇/세션/메모리 관리
│   └── ...
├── chatbots/        # 챗봇 설정 JSON
├── static/          # 웹 UI
└── docs/            # 문서
```

## 설정

`backend/config.py` 또는 환경변수로 설정:

- `PORT` - 서버 포트 (기본: 8080)
- `HOST` - 서버 호스트 (기본: 0.0.0.0)
- `USE_MOCK_DB=true` - Mock DB 사용
- `USE_MOCK_AUTH=true` - Mock 인증 사용
- `LLM_BASE_URL` - LLM API 엔드포인트
- `INGESTION_BASE_URL` - 문서 검색 서버
