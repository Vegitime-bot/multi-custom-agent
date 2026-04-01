# Agent 활용 고급 테스트 케이스

## Agent의 핵심 특성
- **메모리 유지**: 대화 맥락 기억
- **세션 기반**: 지속적 대화 가능
- **맥락 이해**: 이전 대화 참조

---

## TC-AGENT-001: 멀티턴 대화 (Multi-turn Conversation)
**목적:** Agent의 대화 맥락 유지 능력 확인
**흐름:**
```
[Turn 1] User: "Python에서 FastAPI를 사용하는 이유가 뭐야?"
         Agent: FastAPI 장점 설명

[Turn 2] User: "장점 중에서 성능은 어때?"
         Agent: 성능 관련 추가 설명 (이전 "장점" 맥락 유지)

[Turn 3] User: "그럼 단점은?"
         Agent: 단점 설명 (FastAPI 주제 유지)

[Turn 4] User: "이전에 언급한 장점 3가지 요약해줘"
         Agent: Turn 1~2 내용 요약 (장점 3가지)
```
**검증:** 대화 흐름이 끊기지 않고 주제 유지

---

## TC-AGENT-002: 맥락 기반 질의 (Context-aware Query)
**목적:** 암시적 참조 해석 능력
**흐름:**
```
[Turn 1] User: "우리 팀 프로젝트는 RTL 설계고 리더는 홍길동이야"
         Agent: 프로젝트 정보 저장

[Turn 2] User: "리더 연락처 알려줘"
         Agent: "홍길동 연락처"로 해석

[Turn 3] User: "그 사람이 담당하는 부분은?"
         Agent: "홍길동이 RTL 설계 리더"로 해석
```
**검증:** 대명사("그", "리더")와 암시적 참조 정확히 해석

---

## TC-AGENT-003: 장기 메모리 테스트 (Long-term Memory)
**목적:** 많은 턴 후에도 초기 정보 기억
**흐름:**
```
[Turn 1]  User: "내 이름은 김개발이야"
          Agent: 인사

[Turn 2-19] User: FastAPI, SQLAlchemy, Docker 등 18개 기술 질문
            Agent: 각 기술 답변

[Turn 20] User: "내 이름이 뭐였지?"
           Agent: "김개발" (Turn 1 기억)
```
**검증:** 20턴 후에도 초기 정보 정확히 기억

---

## TC-AGENT-004: 주제 전환 및 복귀 (Topic Switch & Return)
**목적:** 주제 변경 후 원래 주제로 복귀
**흐름:**
```
[Turn 1-3] User: FastAPI 관련 질문 (3턴)
            Agent: FastAPI 답변

[Turn 4-5] User: Docker 관련 질문 (2턴 - 주제 전환)
            Agent: Docker 답변

[Turn 6]   User: "아까 FastAPI 얘기로 돌아가서..."
            Agent: FastAPI 주제로 복귀, 이전 FastAPI 대화 기억
```
**검증:** 주제 전환 후 복귀 시 이전 주제 맥락 유지

---

## TC-AGENT-005: 정보 누적 및 종합 (Information Accumulation)
**목적:** 단편적 정보를 종합하여 답변
**흐름:**
```
[Turn 1] User: "팀원 A는 Python 잘해"
         Agent: 확인

[Turn 2] User: "팀원 B는 Verilog 전문가야"
         Agent: 확인

[Turn 3] User: "팀원 C는 프로젝트 매니저 경험 있어"
         Agent: 확인

[Turn 4] User: "우리 팀 기술 스택 정리해줘"
         Agent: A(Python), B(Verilog), C(PM) 종합 정리
```
**검증:** 분산된 정보를 종합하여 일관된 답변

---

## TC-AGENT-006: 오해 정정 및 학습 (Correction & Learning)
**목적:** 잘못된 이해 정정
**흐름:**
```
[Turn 1] User: "나는 디자이너야"
         Agent: "디자이너"로 기억

[Turn 2] User: "아니야, 개발자야"
         Agent: "개발자"로 정정

[Turn 3] User: "내 직업이 뭐야?"
         Agent: "개발자" (정정된 정보)
```
**검증:** 사용자 정정 시 정보 업데이트

---

## TC-AGENT-007: 복수 세션 관리 (Multi-Session Management)
**목적:** 여러 독립적 세션 동시 관리
**흐름:**
```
Session A (프로젝트 X)
  [Turn 1] "이 프로젝트는 RTL 설계야"
  [Turn 2] "데드라인은 6월이야"

Session B (프로젝트 Y)
  [Turn 1] "이 프로젝트는 AI 모델이야"
  [Turn 2] "데드라인은 9월이야"

Session A로 돌아가기
  [Turn 3] "우리 프로젝트 데드라인은?"
  → "6월" (RTL 프로젝트 데드라인)

Session B로 돌아가기
  [Turn 3] "우리 프로젝트 데드라인은?"
  → "9월" (AI 프로젝트 데드라인)
```
**검증:** 세션별 독립적 맥락 유지

---

## TC-AGENT-008: 도메인 전문가 모방 (Domain Expert Simulation)
**목적:** 특정 도메인 지식을 바탕으로 전문가처럼 답변
**흐름:**
```
[Turn 1] User: "RTL 설계에서 Setup Time 위반이 발생했어"
         Agent: Setup Time 위반 원인 분석 (db_004 기반)

[Turn 2] User: "Clock Skew가 0.5ns인데 문제야?"
         Agent: Clock Skew 영향 분석 및 해결책 제시

[Turn 3] User: "이전에 언급한 해결책 중에 가장 효과적인 건?"
         Agent: Turn 2의 해결책 중 우선순위 제시
```
**검증:** 도메인 전문가처럼 맥락 유지하며 조언

---

## 실행 방법

```bash
# 멀티턴 대화 테스트
curl -X POST http://localhost:8080/api/agents/chatbot-a \
  -H "Content-Type: application/json" \
  -d '{"message": "...", "session_id": "agent-test-001"}'

# 세션 확인
curl "http://localhost:8080/api/sessions/agent-test-001/history?chatbot_id=chatbot-a"
```

---

## 클라이언트 SSE 파싱 가이드

### 문제
SSE 응답에서 `session_id` 이벤트가 텍스트에 섞여 나오는 현상

### 해결
이벤트 타입별로 구분하여 처리:

```javascript
const eventSource = new EventSource('/api/agents/chatbot-a');

// 메시지 이벤트 (화면에 표시)
eventSource.addEventListener('message', (e) => {
    appendToChat(e.data);
});

// 세션 ID 이벤트 (저장만 하고 표시 안 함)
eventSource.addEventListener('session_id', (e) => {
    localStorage.setItem('session_id', e.data);
});

// 종료 이벤트
eventSource.addEventListener('done', (e) => {
    eventSource.close();
});
```

### 또는 Non-Streaming API 사용
```bash
# 스트리밍 없이 한 번에 응답 받기
POST /api/agents/{id}/complete  # (향후 추가 예정)
```
