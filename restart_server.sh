#!/bin/bash
# 강제 서버 재시작 스크립트

echo "=== 서버 강제 재시작 ==="

# 1. 모든 Python/uvicorn 프로세스 종료
echo "1. 기존 프로세스 종료 중..."
pkill -9 -f python 2>/dev/null
pkill -9 -f uvicorn 2>/dev/null
pkill -9 -f "backend.main" 2>/dev/null

# 2. 8080 포트 사용 중인 프로세스 종료
echo "2. 8080 포트 프로세스 종료 중..."
for pid in $(lsof -t -i:8080 2>/dev/null); do
    kill -9 $pid 2>/dev/null
done

# 3. 잠시 대기
sleep 3

# 4. Python 캐시 삭제
echo "3. Python 캐시 삭제 중..."
cd /Users/vegitime/.openclaw/workspace/projects/multi-custom-agent
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# 5. 서버 시작
echo "4. 서버 시작 중..."
source .venv/bin/activate
python -m backend.main > /tmp/server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > /tmp/backend.pid

echo "서버 PID: $SERVER_PID"

# 6. 서버 준비 대기
echo "5. 서버 준비 대기 중 (5초)..."
sleep 5

# 7. 헬스 체크
echo "6. 서버 상태 확인..."
if curl -s http://localhost:8080/api/chatbots > /dev/null; then
    echo "✅ 서버 정상 작동 중"
    echo ""
    echo "=== chatbot-hr policy 확인 ==="
    curl -s http://localhost:8080/api/chatbots | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for c in data:
        if c['id'] == 'chatbot-hr':
            print('ID:', c['id'])
            print('Name:', c['name'])
            print('Keys:', list(c.keys()))
            if 'policy' in c:
                print('✅ Policy:', json.dumps(c['policy'], indent=2, ensure_ascii=False))
            else:
                print('❌ Policy 필드 없음')
            break
except Exception as e:
    print('Error:', e)
"
else
    echo "❌ 서버 응답 없음"
    echo "로그 확인: tail -20 /tmp/server.log"
fi
