# Multi Custom Agent Service - 기본 요구사항 테스트 플랜

## 테스트 개요
- **대상**: Multi Custom Agent Service (멀티 테넌트 RAG 챗봇 플랫폼)
- **목적**: 기본 기능 및 아키텍처 원칙 검증
- **환경**: Mock 모드 (USE_MOCK_DB=true, USE_MOCK_AUTH=true)

## 테스트 항목

### 1. 서버 구동 테스트
| ID | 항목 | 기대 결과 |
|----|------|----------|
| SRV-01 | 메인 서버 시작 | FastAPI 앱이 포트 8080에서 실행 |
| SRV-02 | Ingestion 서버 시작 | Mock Ingestion 서버가 포트 8001에서 실행 |
| SRV-03 | 헬스체크 응답 | /health 엔드포인트가 정상 응답 |

### 2. 챗봇 관리 테스트
| ID | 항목 | 기대 결과 |
|----|------|----------|
| BOT-01 | 활성 챗봇 목록 조회 | /api/chatbots가 JSON 배열 반환 |
| BOT-02 | 챗봇 정의 로드 | chatbots/*.json에서 챗봇 설정 로드 |

### 3. 세션 관리 테스트
| ID | 항목 | 기대 결과 |
|----|------|----------|
| SES-01 | 세션 생성 | /api/sessions에서 세션 ID 생성 |
| SES-02 | 세션 조회 | 생성된 세션의 정보 조회 가능 |
| SES-03 | 대화 기록 조회 | /api/sessions/{id}/history 반환 |

### 4. 채팅 API 테스트
| ID | 항목 | 기대 결과 |
|----|------|----------|
| CHAT-01 | Tool 역할 챗봇 호출 | chatbot_a (Tool) 정상 응답 |
| CHAT-02 | Agent 역할 챗봇 호출 | chatbot_b (Agent) 정상 응답 |
| CHAT-03 | SSE 스트리밍 | 응답이 스트림으로 전송됨 |

### 5. RAG 검색 테스트
| ID | 항목 | 기대 결과 |
|----|------|----------|
| RAG-01 | 단일 DB 검색 | /databases/{db_id}/search 반환 |
| RAG-02 | 다중 DB 검색 | /search/multi에서 병합 결과 반환 |
| RAG-03 | Ingestion 헬스체크 | /health에서 사용 가능 DB 목록 반환 |

### 6. 메모리/격리 테스트
| ID | 항목 | 기대 결과 |
|----|------|----------|
| MEM-01 | 세션별 메모리 격리 | 챗봇 A와 B의 메모리가 분리됨 |
| MEM-02 | 대화 기록 저장 | 메시지 쌍이 메모리에 저장됨 |

### 7. Factory Method 테스트 (핵심 아키텍처)
| ID | 항목 | 기대 결과 |
|----|------|----------|
| FAC-01 | ExecutionContext 생성 | Factory가 실행 컨텍스트 생성 |
| FAC-02 | Role Router 동작 | Tool/Agent 역할에 따른 핸들러 선택 |
| FAC-03 | DB Scope 필터링 | 사용자 권한에 따른 DB 접근 제한 |

## 테스트 실행 순서
1. 서버 구동 (SRV-01, SRV-02)
2. 헬스체크 확인 (SRV-03, RAG-03)
3. 챗봇 목록 조회 (BOT-01, BOT-02)
4. 세션 생성 및 조회 (SES-01, SES-02)
5. 채팅 API 호출 (CHAT-01, CHAT-02, CHAT-03)
6. RAG 검색 테스트 (RAG-01, RAG-02)
7. 대화 기록 확인 (SES-03, MEM-01, MEM-02)
8. Factory/Router 검증 (FAC-01, FAC-02, FAC-03)

## 테스트 완료 기준
- 모든 API 엔드포인트가 정상 응답
- SSE 스트리밍 동작 확인
- 멀티 테넌트 격리 확인
- Factory Method 패턴 동작 확인
