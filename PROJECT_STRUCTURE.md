# 프로젝트 폴더 구조

> 확정일: 2026-03-24

---

```
multi-custom-agent/
│
├── chatbots/                        # 챗봇 정의 JSON
│   ├── chatbot_a.json
│   └── chatbot_b.json
│
├── backend/
│   ├── main.py                      # FastAPI 앱 진입점
│   ├── config.py                    # 환경설정 (LLM endpoint, Ingestion URL, SSL 등)
│   │
│   ├── core/
│   │   ├── models.py                # 도메인 모델 (ChatbotDef, Session, Message 등)
│   │   └── factory.py               # Factory Method (실행 컨텍스트 생성)
│   │
│   ├── managers/
│   │   ├── chatbot_manager.py       # 챗봇 JSON 정의 CRUD
│   │   ├── session_manager.py       # 세션 생성/조회/종료
│   │   └── memory_manager.py        # 대화 메모리 관리 (챗봇/세션 단위 격리)
│   │
│   ├── retrieval/
│   │   └── ingestion_client.py      # Ingestion 서버 API 클라이언트 (SSL off)
│   │                                # → 단일 DB / 다중 DB 검색 요청
│   │
│   ├── llm/
│   │   └── client.py                # OpenAI 호환 LLM 클라이언트 (SSL off, streaming)
│   │
│   ├── roles/
│   │   ├── base.py                  # 공통 인터페이스
│   │   ├── tool_handler.py          # Tool 모드 처리
│   │   └── agent_handler.py         # Agent 모드 처리
│   │
│   └── api/
│       ├── chat.py                  # 채팅 API + SSE 스트리밍
│       ├── admin.py                 # 관리자 API (챗봇 CRUD)
│       └── health.py                # 헬스체크
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Chat.tsx             # 채팅 UI (스트리밍)
│   │   │   └── Admin.tsx            # 관리자 대시보드
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx       # 채팅창 메인
│   │   │   ├── MessageBubble.tsx    # 메시지 말풍선
│   │   │   ├── ChatbotSelector.tsx  # 챗봇 선택
│   │   │   └── RoleOverridePanel.tsx # 세션 역할 오버라이드 설정
│   │   └── api/
│   │       └── client.ts            # API 호출 + SSE 클라이언트
│   ├── package.json
│   └── vite.config.ts
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 설계 원칙 반영

| 폴더/파일 | 아키텍처 원칙 |
|-----------|-------------|
| `chatbots/*.json` | Declarative Chatbot Registration (3.5) |
| `core/factory.py` | Factory Method-Based Runtime Context Creation (3.3) |
| `managers/` | Manager-Oriented Resource Control (3.4) |
| `roles/` | Selectable Execution Role (3.6) + 3 Level Hierarchy (3.7) |
| `retrieval/ingestion_client.py` | Retrieval Contract (섹션 7) |
| `managers/memory_manager.py` | Memory Isolation (섹션 8) |
| `api/chat.py` | Streaming Response (섹션 9) |

---

## 주요 설계 결정

- **Ingestion 서버 분리**: 벡터 검색/임베딩은 외부 Ingestion 서버가 담당, 이 프로젝트는 챗봇 로직만
- **챗봇 정의**: 프로젝트 루트 `chatbots/` 폴더에 JSON으로 관리 (유지보수 용이)
- **단일 서버 구성**: FastAPI가 백엔드 API + React 빌드 파일 서빙 동시 처리
- **SSL 전역 비활성화**: `config.py`에서 공통 관리

---

_관련 문서: [ARCHITECTURE.md](./ARCHITECTURE.md) | [ENV.md](./ENV.md) | [INGESTION_API.md](./INGESTION_API.md)_
