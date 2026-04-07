# Multi Custom Agent - 프로젝트 인수인계 문서

> LLM 인수인계용 문서. 이 문서 하나로 프로젝트의 목적, 구조, 실행 방법, 주의사항을 파악할 수 있도록 작성되었습니다.

---

## 1. 프로젝트 목적

사내 전용 **멀티 테넌트 RAG 챗봇 플랫폼**. 여러 독립적인 챗봇을 하나의 서버에서 운영하며, 각 챗봇은 별도의 벡터 DB, 시스템 프롬프트, 권한 설정을 가집니다.

**핵심 특징:**
- JSON 파일 하나로 새 챗봇 등록 (코드 수정 불필요)
- 계층형 챗봇 구조: 상위 챗봇이 신뢰도(70% 임계값) 기반으로 하위 챗봇에 위임
- Tool 모드(단발성) / Agent 모드(대화형) 선택 실행
- SSE 스트리밍 응답
- 사내 SSO(OIDC) 연동 또는 Mock Auth 개발 모드

---

## 2. 디렉토리 구조

```
multi-custom-agent/
├── app.py                          # FastAPI 진입점 (앱 팩토리)
├── config.py                       # 환경변수 기반 설정 (Settings 클래스)
├── requirements.txt
├── .env / .env.example
│
├── backend/
│   ├── api/
│   │   ├── chat.py                 # POST /api/chat (SSE 스트리밍), 세션 관리
│   │   ├── admin.py                # GET|POST|PUT|DELETE /admin/api/chatbots
│   │   ├── health.py               # GET /health
│   │   ├── conversations.py        # 대화 이력 조회 API
│   │   ├── permissions.py          # 권한 관리 API
│   │   └── sso.py                  # OIDC/OAuth2 SSO (USE_MOCK_AUTH=false 시 활성화)
│   │
│   ├── core/
│   │   ├── models.py               # 도메인 모델 (ChatbotDef, ExecutionContext 등)
│   │   └── factory.py              # ExecutionContext 팩토리
│   │
│   ├── managers/
│   │   ├── chatbot_manager.py      # chatbots/*.json 로드/CRUD/reload
│   │   ├── session_manager.py      # 세션 생성 및 생명주기
│   │   └── memory_manager.py       # (chatbot_id, session_id) 키 기반 대화 메모리
│   │
│   ├── executors/
│   │   ├── tool_executor.py        # Tool 모드: 단발성, 메모리 없음
│   │   ├── agent_executor.py       # Agent 모드: 대화형, 메모리 유지
│   │   ├── parent_agent_executor.py      # 상위 챗봇: 신뢰도 기반 하위 위임
│   │   └── hierarchical_agent_executor.py  # 3단계 계층 처리
│   │
│   ├── roles/
│   │   ├── base.py
│   │   ├── tool_handler.py
│   │   ├── agent_handler.py
│   │   └── router.py               # 역할에 맞는 핸들러 선택
│   │
│   ├── retrieval/
│   │   └── ingestion_client.py     # 외부 Ingestion Server POST /search/multi 호출
│   │
│   ├── llm/
│   │   └── client.py               # OpenAI 호환 LLM API 클라이언트 (스트리밍)
│   │
│   ├── permissions/
│   │   └── repository.py           # 사용자-챗봇 접근 권한 (Mock 또는 PostgreSQL)
│   │
│   ├── conversation/
│   │   └── repository.py           # 대화 로그 저장/조회
│   │
│   ├── users/
│   │   └── repository.py           # 사용자 CRUD
│   │
│   ├── database/
│   │   └── session.py              # SQLAlchemy 세션 및 테이블 초기화
│   │
│   └── auth/
│       └── mock_auth.py            # 개발용 Mock 인증 (knox_id: "user-001")
│
├── chatbots/                        # 챗봇 정의 JSON 파일들
│   ├── chatbot-hr.json              # 상위 챗봇 예시 (HR)
│   ├── chatbot-hr-policy.json       # 하위 챗봇 예시
│   ├── chatbot-hr-benefit.json
│   ├── chatbot-tech.json            # 상위 챗봇 예시 (기술)
│   ├── chatbot-tech-backend.json
│   ├── chatbot-tech-frontend.json
│   ├── chatbot-tech-devops.json
│   ├── chatbot-company.json
│   ├── chatbot-rtl-verilog.json
│   ├── chatbot-rtl-synthesis.json
│   ├── chatbot_a.json ~ chatbot_d.json   # 단독 챗봇 예시
│   └── (자동 생성 test-* 파일들)
│
├── database/
│   ├── schema.sql                   # user_chatbot_access 테이블
│   └── schema_conversation.sql      # conversations 테이블
│
├── static/                          # React/Vite 빌드 결과물
│   ├── index.html                   # 채팅 UI
│   └── admin/                       # 관리자 대시보드 (순수 HTML/CSS/JS)
│
├── tests/
│   ├── test_web_pages.py            # 웹 페이지 E2E 테스트 (현재 사용)
│   └── test_admin_panel.py          # 관리자 패널 통합 테스트 (현재 사용)
│
└── docs/
    ├── ARCHITECTURE.md
    ├── SSO_INTEGRATION.md
    ├── TESTING.md
    └── USERS_DB.md
```

---

## 3. 주요 컴포넌트 설명

### 3-1. 챗봇 정의 (chatbots/*.json)

챗봇 하나 = JSON 파일 하나. 서버 재시작 없이 파일 추가/수정으로 챗봇 등록 가능.

```json
{
  "id": "chatbot-hr",
  "name": "인사지원 상위 챗봇",
  "description": "HR 관련 질문을 처리하는 상위 에이전트",
  "active": true,
  "capabilities": {
    "db_ids": ["db_hr"],
    "model": "GLM4.7",
    "system_prompt": "당신은 HR 전문가입니다..."
  },
  "policy": {
    "temperature": 0.3,
    "max_tokens": 1024,
    "stream": true,
    "default_mode": "agent",
    "max_messages": 20
  },
  "sub_chatbots": [
    {"id": "chatbot-hr-policy", "level": 1, "default_role": "agent"},
    {"id": "chatbot-hr-benefit", "level": 1, "default_role": "agent"}
  ]
}
```

### 3-2. 실행 흐름 (chat.py)

```
POST /api/chat
  │
  ├─ 1. ChatbotManager → 챗봇 정의 조회
  ├─ 2. SessionManager → 세션 확인/생성
  ├─ 3. 모드 결정: 요청 > 세션 > 챗봇 default
  ├─ 4. 권한 확인: check_chatbot_access + check_mode_permission
  ├─ 5. Executor 생성:
  │     ├─ sub_chatbots 있음 → ParentAgentExecutor
  │     ├─ Tool 모드 → ToolExecutor
  │     └─ Agent 모드 → AgentExecutor
  └─ 6. StreamingResponse (SSE) 반환
```

### 3-3. ParentAgentExecutor (계층 위임)

- 상위 챗봇이 먼저 자체 RAG 검색으로 신뢰도 계산
- 신뢰도 ≥ 70%: 직접 답변
- 신뢰도 < 70%: 하위 챗봇 중 키워드 매칭으로 선택하여 위임
- 하위 챗봇의 응답을 스트리밍으로 전달

### 3-4. MemoryManager

- 키: `(chatbot_id, session_id)` → 완전한 멀티 테넌트 격리
- 현재 인메모리 Dict 구현 (서버 재시작 시 초기화)
- `max_messages` 초과 시 FIFO 방식으로 오래된 메시지 제거

### 3-5. 인증 모드

| 설정 | 동작 |
|------|------|
| `USE_MOCK_AUTH=true` (기본) | knox_id="user-001" 자동 주입, 모든 챗봇 접근 허용 |
| `USE_MOCK_AUTH=false` | 사내 SSO(OIDC) 인증 필요, 루트 경로가 SSO로 리다이렉트 |

---

## 4. 테스트 구조

### 현재 사용 중인 테스트

| 파일 | 설명 | 실행 조건 |
|------|------|-----------|
| `tests/test_web_pages.py` | 채팅/관리자 페이지 E2E, CRUD API 테스트 (TC-WEB-001~014) | 서버 실행 중 필요 |
| `tests/test_admin_panel.py` | 관리자 패널 UI 구조, API 연동, 계층 CRUD 테스트 (TC-ADMIN-001~) | 서버 실행 중 필요 |

### 테스트 실행

```bash
# 서버를 먼저 실행한 뒤:
python -m pytest tests/test_web_pages.py -v
python -m pytest tests/test_admin_panel.py -v

# 전체:
python -m pytest tests/ -v
```

**주의:** 두 테스트 파일 모두 실제 HTTP 요청(`requests` 라이브러리)을 사용하는 통합 테스트입니다. `http://localhost:8080`에 서버가 실행 중이어야 합니다.

---

## 5. 환경변수 설정

`.env.example`을 복사해 `.env`로 사용합니다.

```bash
cp .env.example .env
```

### 필수 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `USE_MOCK_DB` | `true` | `false` 시 PostgreSQL 사용 |
| `USE_MOCK_AUTH` | `true` | `false` 시 사내 SSO 필요 |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI 호환 LLM 엔드포인트 |
| `LLM_API_KEY` | `dummy-key` | LLM API 키 |
| `LLM_DEFAULT_MODEL` | `GLM4.7` | 기본 모델명 |
| `INGESTION_BASE_URL` | `http://localhost:8001` | 벡터 검색 서버 주소 |
| `PORT` | `8080` | 서버 포트 |

### PostgreSQL 연동 시 (`USE_MOCK_DB=false`)

```
PG_HOST=localhost
PG_PORT=5432
PG_DB=chatbot_db
PG_USER=postgres
PG_PASSWORD=your_password
```

### SSO 연동 시 (`USE_MOCK_AUTH=false`)

```
SSO_ISSUER=https://sso.company.com
SSO_CLIENT_ID=your-client-id
SSO_CLIENT_SECRET=your-client-secret
SSO_REDIRECT_URI=http://your-server:8080/auth/acs
SECRET_KEY=랜덤-32바이트-이상-문자열
```

---

## 6. API 엔드포인트

### 채팅 API (`/api`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/chatbots` | 활성 챗봇 목록 |
| `POST` | `/api/sessions` | 세션 생성 |
| `DELETE` | `/api/sessions/{session_id}` | 세션 종료 |
| `GET` | `/api/sessions/{session_id}/history` | 대화 이력 조회 |
| `POST` | `/api/chat` | 채팅 (SSE 스트리밍) |
| `POST` | `/api/tools/{chatbot_id}` | Tool 모드 전용 엔드포인트 |
| `POST` | `/api/agents/{chatbot_id}` | Agent 모드 전용 엔드포인트 |

### 관리자 API (`/admin/api`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/admin/api/chatbots` | 전체 챗봇 목록 (타입/계층 포함) |
| `POST` | `/admin/api/chatbots` | 챗봇 생성 (JSON 파일 저장) |
| `PUT` | `/admin/api/chatbots/{id}` | 챗봇 수정 |
| `DELETE` | `/admin/api/chatbots/{id}` | 챗봇 삭제 (상위에서 참조도 제거) |
| `GET` | `/admin/api/stats` | 통계 (총수, 상위봇 수, 활성 수) |

### 페이지 URL

| URL | 설명 |
|-----|------|
| `/` | 채팅 UI (Mock Auth 모드) 또는 SSO 리다이렉트 |
| `/admin` | 관리자 대시보드 |
| `/health` | 헬스체크 |
| `/docs` | Swagger UI (FastAPI 자동 생성) |

### POST /api/chat 요청 예시

```json
{
  "chatbot_id": "chatbot-hr",
  "message": "연차 신청은 어떻게 하나요?",
  "session_id": "session-abc123",
  "mode": "agent",
  "active_level": 1
}
```

**응답:** SSE 스트림
```
event: message
data: "연차"

event: message
data: " 신청은"

event: done
data: {}
```

---

## 7. 서버 실행

### 개발 모드

```bash
# 의존성 설치
pip install -r requirements.txt

# Ingestion Server (벡터 검색 서버) 실행 - 없으면 mock 사용
python mock_ingestion_server.py  # 별도 터미널

# 메인 서버
python app.py
# 또는
uvicorn app:app --reload --port 8080
```

### 접속

- 채팅 UI: http://localhost:8080
- 관리자 패널: http://localhost:8080/admin
- API 문서: http://localhost:8080/docs

---

## 8. 주의사항 / Known Issues

### 8-1. 메모리 휘발성
`MemoryManager`는 인메모리 Dict 기반입니다. **서버 재시작 시 모든 대화 이력이 초기화됩니다.** 프로덕션에서는 Redis 또는 DB로 교체 필요.

### 8-2. chatbots/ 잔류 테스트 파일
관리자 패널 테스트 실행 후 `chatbots/` 디렉토리에 `test-*`, `hierarchy-test-*` 형태의 JSON 파일이 남을 수 있습니다. 테스트에서 cleanup을 수행하지만, 테스트 중단 시 잔류합니다. 주기적으로 제거하거나 무시해도 됩니다.

```bash
# 잔류 테스트 챗봇 파일 제거
rm chatbots/test-*.json chatbots/hierarchy-test-*.json 2>/dev/null
```

### 8-3. Mock Auth에서 권한 우회
`USE_MOCK_AUTH=true`(기본값) 시 모든 사용자가 모든 챗봇에 접근할 수 있습니다. 프로덕션 배포 시 반드시 `USE_MOCK_AUTH=false`로 변경하고 SSO 설정을 완료해야 합니다.

### 8-4. DB 권한 조회 fallback
`USE_MOCK_DB=false`이지만 PostgreSQL 연결 실패 시, 권한 조회가 `MOCK_USER_PERMISSIONS["user-001"]`으로 fallback됩니다 (`chat.py:get_user_permissions`). 의도치 않게 접근이 허용될 수 있으므로 DB 연결 상태를 반드시 확인하세요.

### 8-5. SSL 검증 비활성화
`SSL_VERIFY=false`(기본값)로 Ingestion Server와의 통신에서 SSL 인증서를 검증하지 않습니다. 사내 네트워크 전용이므로 허용되지만, 공개망 배포 시 변경 필요.

### 8-6. SECRET_KEY 기본값
`SessionMiddleware`의 `SECRET_KEY`가 기본값(`change-this-in-production-secret-key-32bytes-minimum`)으로 설정되어 있습니다. SSO 사용 시 반드시 무작위 문자열로 변경하세요.

### 8-7. 대화 로그 Mock 고정
`chat.py`의 `event_generator` 내부에서 `MockConversationRepository()`를 직접 생성합니다(`chat.py:372`). `USE_MOCK_DB=false`여도 대화 로그는 항상 Mock으로 저장됩니다 (실제 DB 미저장). 개선 필요.

### 8-8. admin.py Request 타입
`create_chatbot`과 `update_chatbot`의 파라미터가 `request: dict` 타입으로 선언되어 있어 FastAPI의 자동 유효성 검사가 적용되지 않습니다. 잘못된 요청이 들어올 경우 런타임 에러가 발생할 수 있습니다.
