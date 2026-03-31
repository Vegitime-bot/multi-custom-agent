# Tool & Agent 통합 테스트 시나리오

## 시나리오 1: Tool → Agent 연쇄 호출
**목적:** Tool로 검색 후 Agent로 대화 이어가기
**흐름:**
1. Tool 모드로 "FastAPI 개요" 검색
2. 검색 결과를 바탕으로 Agent 모드에서 심층 질문
3. Agent가 Tool 결과를 기억하고 답변하는지 확인

## 시나리오 2: Agent → Tool 위임
**목적:** Agent가 복잡한 작업을 Tool에 위임
**흐름:**
1. Agent 모드로 "HR 정책 문서에서 연차 관련 내용 찾아줘" 요청
2. Agent가 판단하여 Tool 모드로 전환 (DB 스코프에 따라)
3. Tool이 검색 결과 반환
4. Agent가 결과를 해석하여 사용자에게 설명

## 시나리오 3: 동일 챗봇 모드 전환
**목적:** 한 챗봇을 Tool과 Agent로 번갈아 사용
**흐름:**
1. chatbot-a를 Agent 모드로 "내 이름은 김철수야" (메모리 저장)
2. 같은 chatbot-a를 Tool 모드로 "FastAPI 설명해줘" (메모리 없음)
3. 다시 Agent 모드로 "내 이름이 뭐야?" (여전히 "김철수" 답변해야 함)

## 시나리오 4: 병렬 Tool 호출 후 Agent 통합
**목적:** 여러 Tool 결과를 Agent가 종합
**흐름:**
1. Tool A (chatbot-b): HR 정책 검색
2. Tool B (chatbot-c): RTL 문서 검색
3. Agent (chatbot-a): 두 결과를 종합하여 답변

## 시나리오 5: 세션 격리 확인
**목적:** 같은 챗봇, 다른 세션 간 데이터 격리
**흐름:**
1. 세션 A (user-001): chatbot-a Agent로 "비밀번호는 1234"
2. 세션 B (user-002): chatbot-a Agent로 "비밀번호는 5678"
3. 각 세션에서 "비밀번호 알려줘" 질문 시 서로 다른 답변 확인

## 시나리오 6: 권한 있는 모드 / 없는 모드
**목적:** 권한에 따른 모드 제한 확인
**흐름:**
1. user-001 (chatbot-b에 Tool만 권한 있음)
   - Tool 호출: 성공
   - Agent 호출: 403
2. user-002 (chatbot-b에 Tool/Agent 모두 권한 있음)
   - Tool 호출: 성공
   - Agent 호출: 성공
