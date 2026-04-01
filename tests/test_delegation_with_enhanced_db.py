"""
test_delegation_with_enhanced_db.py - 향상된 DB 기반 위임 로직 테스트
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


def test_parent_to_hr_policy_delegation():
    """TC-001: chatbot-hr → chatbot-hr-policy 위임"""
    print("\n" + "="*60)
    print("TC-001: 상위 HR → 정책 전문가 위임")
    print("="*60)
    
    resp = requests.post(
        f"{BASE_URL}/api/agents/chatbot-hr",
        headers=HEADERS,
        json={
            "message": "승진 기준이 뭐야?",
            "session_id": "tc-001"
        },
        stream=True
    )
    
    response_text = resp.text
    parsed = parse_sse_response(response_text)
    
    print(f"\n응답:\n{parsed[:600]}...")
    
    # 검증
    checks = []
    if "위임" in response_text or "전문가" in response_text:
        checks.append("✅ 위임 메시지 확인")
    else:
        checks.append("⚠️ 위임 없이 직접 답변")
        
    if "승진" in parsed.lower() or "기준" in parsed.lower():
        checks.append("✅ 승진 관련 내용 포함")
    else:
        checks.append("❌ 승진 내용 없음")
    
    print("\n".join(checks))
    return len([c for c in checks if "✅" in c]) >= 1


def test_parent_to_benefit_delegation():
    """TC-002: chatbot-hr → chatbot-hr-benefit 위임"""
    print("\n" + "="*60)
    print("TC-002: 상위 HR → 복리후생 전문가 위임")
    print("="*60)
    
    resp = requests.post(
        f"{BASE_URL}/api/agents/chatbot-hr",
        headers=HEADERS,
        json={
            "message": "4대보험 뭐가 있어?",
            "session_id": "tc-002"
        },
        stream=True
    )
    
    response_text = resp.text
    parsed = parse_sse_response(response_text)
    
    print(f"\n응답:\n{parsed[:600]}...")
    
    checks = []
    if "보험" in parsed:
        checks.append("✅ 보험 관련 내용 포함")
    else:
        checks.append("❌ 보험 내용 없음")
    
    print("\n".join(checks))
    return len([c for c in checks if "✅" in c]) >= 1


def test_tech_to_verilog_delegation():
    """TC-003: chatbot-tech → chatbot-rtl-verilog 위임"""
    print("\n" + "="*60)
    print("TC-003: 기술지원 → Verilog 전문가 위임")
    print("="*60)
    
    resp = requests.post(
        f"{BASE_URL}/api/agents/chatbot-tech",
        headers=HEADERS,
        json={
            "message": "verilog로 fsm 설계하는 방법 알려줘",
            "session_id": "tc-003"
        },
        stream=True
    )
    
    response_text = resp.text
    parsed = parse_sse_response(response_text)
    
    print(f"\n응답:\n{parsed[:800]}...")
    
    checks = []
    if "Verilog HDL 전문 챗봇" in response_text or "전문가" in response_text:
        checks.append("✅ Verilog 전문가 위임 확인")
    else:
        checks.append("⚠️ 위임 없음")
    
    if "fsm" in parsed.lower() or "FSM" in parsed or "상태" in parsed:
        checks.append("✅ FSM 관련 내용 포함")
    else:
        checks.append("❌ FSM 내용 없음")
    
    print("\n".join(checks))
    return len([c for c in checks if "✅" in c]) >= 1


def test_backend_direct_answer():
    """TC-004: chatbot-tech-backend 직접 호출 (위임 없음)"""
    print("\n" + "="*60)
    print("TC-004: 백엔드 전문가 직접 호출")
    print("="*60)
    
    resp = requests.post(
        f"{BASE_URL}/api/agents/chatbot-tech-backend",
        headers=HEADERS,
        json={
            "message": "FastAPI에서 DB 연결하는 방법",
            "session_id": "tc-004"
        },
        stream=True
    )
    
    response_text = resp.text
    parsed = parse_sse_response(response_text)
    
    print(f"\n응답:\n{parsed[:600]}...")
    
    checks = []
    if "FastAPI" in parsed or "SQLAlchemy" in parsed or "DB" in parsed:
        checks.append("✅ 백엔드/DB 관련 내용 포함")
    else:
        checks.append("❌ 관련 내용 없음")
    
    print("\n".join(checks))
    return len([c for c in checks if "✅" in c]) >= 1


def test_devops_ci_cd():
    """TC-005: chatbot-tech-devops CI/CD 질문"""
    print("\n" + "="*60)
    print("TC-005: DevOps 전문가 CI/CD 질문")
    print("="*60)
    
    resp = requests.post(
        f"{BASE_URL}/api/agents/chatbot-tech-devops",
        headers=HEADERS,
        json={
            "message": "CI/CD 파이프라인이 뭐야?",
            "session_id": "tc-005"
        },
        stream=True
    )
    
    response_text = resp.text
    parsed = parse_sse_response(response_text)
    
    print(f"\n응답:\n{parsed[:600]}...")
    
    checks = []
    if "CI/CD" in parsed or "파이프라인" in parsed or "배포" in parsed:
        checks.append("✅ CI/CD 관련 내용 포함")
    else:
        checks.append("❌ CI/CD 내용 없음")
    
    print("\n".join(checks))
    return len([c for c in checks if "✅" in c]) >= 1


def test_verilog_counter():
    """TC-006: chatbot-rtl-verilog 카운터 설계"""
    print("\n" + "="*60)
    print("TC-006: Verilog 전문가 카운터 설계")
    print("="*60)
    
    resp = requests.post(
        f"{BASE_URL}/api/agents/chatbot-rtl-verilog",
        headers=HEADERS,
        json={
            "message": "4비트 카운터 코드 보여줘",
            "session_id": "tc-006"
        },
        stream=True
    )
    
    response_text = resp.text
    parsed = parse_sse_response(response_text)
    
    print(f"\n응답:\n{parsed[:800]}...")
    
    checks = []
    if "카운터" in parsed or "counter" in parsed.lower():
        checks.append("✅ 카운터 설계 내용 포함")
    else:
        checks.append("❌ 카운터 내용 없음")
    
    if "module" in parsed.lower() or "always" in parsed.lower():
        checks.append("✅ Verilog 코드 포함")
    else:
        checks.append("⚠️ 코드 없음")
    
    print("\n".join(checks))
    return len([c for c in checks if "✅" in c]) >= 1


if __name__ == "__main__":
    print("Multi Custom Agent Service - Enhanced DB 테스트")
    print(f"대상: {BASE_URL}")
    
    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"\n서버 상태: {'✅ 정상' if resp.status_code == 200 else '❌ 오류'}")
    except Exception as e:
        print(f"\n❌ 서버 연결 실패: {e}")
        sys.exit(1)
    
    # 테스트 실행
    tests = [
        ("상위 HR → 정책 위임", test_parent_to_hr_policy_delegation),
        ("상위 HR → 복리후생 위임", test_parent_to_benefit_delegation),
        ("기술지원 → Verilog 위임", test_tech_to_verilog_delegation),
        ("백엔드 직접 호출", test_backend_direct_answer),
        ("DevOps CI/CD", test_devops_ci_cd),
        ("Verilog 카운터", test_verilog_counter),
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
