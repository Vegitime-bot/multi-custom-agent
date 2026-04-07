# Multi Custom Agent Service

멀티 테넌트 RAG 챗봇 플랫폼입니다. 여러 독립적인 챗봇을 하나의 서버에서 운영하며, 계층적 위임(Hierarchical Delegation)과 SSE 스트리밍을 지원합니다.

## 문서

| 문서 | 내용 |
|------|------|
| [01. 프로젝트 개요](docs/01_PROJECT_OVERVIEW.md) | 목적, 주요 기능, 사용자 흐름, 기술 스택 |
| [02. 아키텍처](docs/02_ARCHITECTURE.md) | 시스템 구성, 컴포넌트 다이어그램, 데이터 흐름 |
| [03. API 명세](docs/03_API_SPECIFICATION.md) | 전체 API 엔드포인트, 요청/응답 스키마, 에러 코드 |
| [04. 데이터 모델](docs/04_DATA_MODEL.md) | DB 스키마, JSON 구조, 도메인 모델 관계도 |
| [05. 설정 & 배포](docs/05_CONFIGURATION.md) | 환경변수, .env 예시, 배포 가이드 |
| [06. 테스트](docs/06_TESTING.md) | 테스트 전략, 실행 방법, 수동 테스트 |
| [07. 변경 이력](docs/07_CHANGELOG.md) | Git 커밋 기반 기능 추가/변경/삭제 내역 |
| [08. 문제 해결](docs/08_TROUBLESHOOTING.md) | Known Issues, 디버깅 가이드, FAQ |

기타 참고 문서:
- [SSO 연동 가이드](docs/SSO_INTEGRATION.md)
- [Ingestion API 명세](INGESTION_API.md)
- [환경변수 상세](ENV.md)

---

## 빠른 시작

### 1. 환경 설정

```bash
cd multi-custom-agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Mock Ingestion 서버 실행 (터미널 1)

```bash
python mock_ingestion_server.py
# → http://localhost:8001
```

### 3. 메인 서버 실행 (터미널 2)

```bash
python app.py
# → http://localhost:8080
```

> Ingestion 서버가 먼저 실행되어 있어야 합니다.

### 4. 접속

| URL | 설명 |
|-----|------|
| `http://localhost:8080` | 챗봇 UI |
| `http://localhost:8080/admin` | 관리자 패널 |
| `http://localhost:8080/docs` | API 문서 (Swagger) |
| `http://localhost:8080/health` | 헬스체크 |

---

## 주요 API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/chat` | POST | 챗봇 대화 (SSE 스트리밍) |
| `/api/sessions` | POST | 세션 생성 |
| `/api/sessions/{id}/history` | GET | 대화 기록 |
| `/admin/api/chatbots` | GET/POST | 챗봇 목록/생성 |
| `/admin/api/chatbots/{id}` | PUT/DELETE | 챗봇 수정/삭제 |
| `/api/permissions/` | GET/POST | 접근 권한 관리 |
| `/api/conversations/stats` | GET | 대화 통계 |
| `/health` | GET | 헬스체크 |

---

## 핵심 설정

`config.py` 또는 `.env` 파일로 설정합니다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `USE_MOCK_DB` | `true` | `false` → PostgreSQL 사용 |
| `USE_MOCK_AUTH` | `true` | `false` → SSO 인증 사용 |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | LLM API 엔드포인트 |
| `INGESTION_BASE_URL` | `http://localhost:8001` | 벡터 검색 서버 |
| `PORT` | `8080` | 서버 포트 |

전체 환경변수 목록: [docs/05_CONFIGURATION.md](docs/05_CONFIGURATION.md)

---

## 디렉토리 구조

```
multi-custom-agent/
├── app.py              # FastAPI 앱 진입점
├── config.py           # 전역 설정
├── requirements.txt    # Python 의존성
├── backend/            # 백엔드 핵심 로직
│   ├── api/            # REST API 라우터
│   ├── core/           # 도메인 모델 & 팩토리
│   ├── managers/       # 챗봇/세션/메모리 관리
│   ├── executors/      # 실행 엔진
│   └── ...
├── chatbots/           # 챗봇 정의 JSON 파일
├── database/           # PostgreSQL 스키마
├── static/             # 웹 UI
├── tests/              # 통합 테스트
└── docs/               # 문서
```
