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

### 3. Mock Ingestion 서버 실행 (RAG 검색용)

```bash
# 터미널 1: Ingestion 서버 (포트 8001)
python mock_ingestion_server.py
```

### 4. 메인 서버 실행

**방법 1: app.py 직접 실행 (권장)**

```bash
# 터미널 2: 메인 서버 (포트 8080)
python app.py
```

**방법 2: uvicorn으로 실행 (FastAPI 표준)**

```bash
# app.py 기준 (신규 구조)
uvicorn app:app --host 0.0.0.0 --port 8080 --reload

# 또는 기존 방식 (하위호환)
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

> **중요:** Ingestion 서버가 먼저 켜져 있어야 챗봇이 문서 검색 및 답변 생성 가능

### 5. 접속

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

`config.py` 또는 `.env` 파일로 설정:

### 기본 설정
- `PORT` - 서버 포트 (기본: 8080)
- `HOST` - 서버 호스트 (기본: 0.0.0.0)
- `USE_MOCK_DB=true` - Mock DB 사용 (PostgreSQL 연결 시 false)
- `USE_MOCK_AUTH=true` - Mock 인증 사용 (SSO 연동 시 false)
- `LLM_BASE_URL` - LLM API 엔드포인트
- `INGESTION_BASE_URL` - 문서 검색 서버

### SSO 연동 (사내 환경)

`.env` 파일에 아래 설정 추가:

```bash
# Mock Auth 비활성화
USE_MOCK_AUTH=false

# 사내 SSO 정보 (OIDC/OAuth2)
SSO_ISSUER=https://sso.company.com
SSO_CLIENT_ID=your-client-id
SSO_CLIENT_SECRET=your-client-secret
SSO_REDIRECT_URI=http://localhost:8080/auth/acs

# 세션 보안 키 (32바이트 이상)
SECRET_KEY=$(openssl rand -base64 32)
```

SSO 연동 상세 가이드: [docs/SSO_INTEGRATION.md](docs/SSO_INTEGRATION.md)
