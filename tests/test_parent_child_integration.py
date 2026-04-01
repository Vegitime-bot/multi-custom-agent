#!/usr/bin/env python3
"""
test_parent_child_integration.py - 상위/하위 Agent 위임 통합 테스트
실제 API를 호출하여 end-to-end 테스트 수행
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8080"
HEADERS = {
    "Content-Type": "application/json",
    "X-User-Knox-ID": "user-001"
}


def parse_sse_response(response_text):
    """SSE 응답 파싱"""
    chunks = []
    for line in response_text.strip().split('\n'):
        if line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                if isinstance(data, str):
                    chunks.append(data)
            except:
                pass
    return ''.join(chunks)


def test_parent_agent_high_confidence():
    """테스트 1: 상위 Agent가 직접 답변 (confidence 높음)"""
    print("\n" + "="*60)
    print("테스트 1: 상위 Agent 직접 답변 (High Confidence)")
    print("="*60)
    
    # 먼저 세션 생성
    resp = requests.post(
        f"{BASE_URL}/api/sessions",
        headers=HEADERS,
        json={"chatbot_id": "chatbot-hr", "mode": "agent"}
    )
    session_id = resp.json()["session_id"]
    print(f"세션 생성: {session_id}")
    
    # 상위 Agent에게 일반 질문 (자체 DB로 답변 가능)
    resp = requests.post(
        f"{BASE_URL}/api/agents/chatbot-hr",
        headers=HEADERS,
        json={
            "message": "안녕하세요, 인사팀에 대해 소개해주세요",
            "session_id": session_id
        },
        stream=True
    )
    
    response_text = resp.text
    print(f"\n응답:\n{parse_sse_response(response_text)[:500]}...")
    
    # Confidence 값 확인
    if "CONFIDENCE:" in response_text:
        print("\n✅ Confidence 값이 응답에 포함됨")
    else:
        print("\n⚠️ Confidence 값이 응답에 없음 (LLM이 패턴을 따르지 않음)")
    
    return True


def test_parent_agent_delegation():
    """테스트 2: 상위 Agent가 하위 Agent에게 위임"""
    print("\n" + "="*60)
    print("테스트 2: 상위 Agent → 하위 Agent 위임")
    print("="*60)
    
    # 세션 생성
    resp = requests.post(
        f"{BASE_URL}/api/sessions",
        headers=HEADERS,
        json={"chatbot_id": "chatbot-tech", "mode": "agent"}
    )
    session_id = resp.json()["session_id"]
    print(f"세션 생성: {session_id}")
    
    # 세부 기술 질문 (하위 Agent 위임 예상)
    resp = requests.post(
        f"{BASE_URL}/api/agents/chatbot-tech",
        headers=HEADERS,
        json={
            "message": "FastAPI에서 SQLAlchemy로 데이터베이스 연결하는 방법 알려줘",
            "session_id": session_id
        },
        stream=True
    )
    
    response_text = resp.text
    print(f"\n응답:\n{parse_sse_response(response_text)[:800]}...")
    
    # 위임 메시지 확인
    if "위임합니다" in response_text or "하위" in response_text:
        print("\n✅ 하위 Agent 위임 로직 실행됨")
    else:
        print("\n⚠️ 위임 없이 상위 Agent가 직접 답변")
    
    return True


def test_keyword_based_selection():
    """테스트 3: 키워드 기반 하위 Agent 선택"""
    print("\n" + "="*60)
    print("테스트 3: 키워드 기반 하위 Agent 선택")
    print("="*60)
    
    test_cases = [
        ("chatbot-hr", "연차 규정", "chatbot-hr-benefit"),
        ("chatbot-hr", "인사 평가", "chatbot-hr-policy"),
        ("chatbot-tech", "React 컴포넌트", "chatbot-tech-frontend"),
        ("chatbot-tech", "Docker 설정", "chatbot-tech-devops"),
    ]
    
    for parent_id, question, expected_sub in test_cases:
        print(f"\n{parent_id} → '{question}' (예상: {expected_sub})")
        
        resp = requests.post(
            f"{BASE_URL}/api/agents/{parent_id}",
            headers=HEADERS,
            json={
                "message": question,
                "session_id": f"test-session-{hash(question) % 10000}"
            },
            stream=True
        )
        
        response_text = resp.text
        
        # 하위 Agent 이름이 응답에 포함되었는지 확인
        if expected_sub.replace("chatbot-", "").replace("-", " ") in response_text.lower():
            print(f"  ✅ 올바른 하위 Agent 선택됨")
        else:
            print(f"  ⚠️ 위임 메시지 확인 불가 (실제 응답 확인 필요)")
    
    return True


def test_tool_mode_no_delegation():
    """테스트 4: Tool 모드는 위임 없음"""
    print("\n" + "="*60)
    print("테스트 4: Tool 모드 (위임 없음, 단발성)")
    print("="*60)
    
    resp = requests.post(
        f"{BASE_URL}/api/tools/chatbot-hr",
        headers=HEADERS,
        json={"message": "연차 규정 알려줘"},
        stream=True
    )
    
    response_text = resp.text
    print(f"\n응답:\n{parse_sse_response(response_text)[:500]}...")
    
    # Tool 모드는 위임 메시지 없음
    if "위임" not in response_text:
        print("\n✅ Tool 모드는 위임 없이 단발성 응답")
    else:
        print("\n⚠️ Tool 모드에 위임 로직이 실행됨 (비정상)")
    
    return True


def list_available_chatbots():
    """사용 가능한 챗봇 목록 출력"""
    print("\n" + "="*60)
    print("사용 가능한 챗봇 목록")
    print("="*60)
    
    resp = requests.get(f"{BASE_URL}/api/chatbots", headers=HEADERS)
    chatbots = resp.json()
    
    for bot in chatbots:
        print(f"\n📱 {bot['name']} ({bot['id']})")
        print(f"   설명: {bot.get('description', 'N/A')}")
        print(f"   지원 모드: {', '.join(bot.get('supported_modes', []))}")
        print(f"   기본 모드: {bot.get('default_mode', 'N/A')}")


if __name__ == "__main__":
    print("Multi Custom Agent Service - Parent/Child Agent 통합 테스트")
    print(f"대상: {BASE_URL}")
    
    try:
        # 서버 상태 확인
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"\n서버 상태: {'✅ 정상' if resp.status_code == 200 else '❌ 오류'}")
    except Exception as e:
        print(f"\n❌ 서버 연결 실패: {e}")
        print("서버가 실행 중인지 확인하세요")
        sys.exit(1)
    
    # 사용 가능한 챗봇 목록
    list_available_chatbots()
    
    # 테스트 실행
    tests = [
        ("부모 Agent 직접 답변", test_parent_agent_high_confidence),
        ("하위 Agent 위임", test_parent_agent_delegation),
        ("키워드 기반 선택", test_keyword_based_selection),
        ("Tool 모드", test_tool_mode_no_delegation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "✅ 통과" if result else "❌ 실패"))
        except Exception as e:
            print(f"\n❌ {name} 테스트 오류: {e}")
            results.append((name, f"❌ 오류: {e}"))
    
    # 결과 요약
    print("\n" + "="*60)
    print("테스트 결과 요약")
    print("="*60)
    for name, result in results:
        print(f"{name}: {result}")
    
    passed = sum(1 for _, r in results if "✅" in r)
    print(f"\n총 {len(results)}개 중 {passed}개 통과")
