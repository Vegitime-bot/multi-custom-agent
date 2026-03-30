# 사내 개발 환경 (Company Dev Environment)

> 최초 작성: 2026-03-24

---

## 개발 환경 구성

| 항목 | 내용 |
|------|------|
| IDE | WebIDE (VSCode 기반 원격 개발) |
| 버전관리 | GitHub Repository 사용 가능 |
| 컨테이너 | Docker 기반 구성 |
| 환경 구분 | 개발(Dev) / 운영(Prod) 분리 |

---

## 운영체제 사양

| 항목 | 사양 |
|------|------|
| OS | Linux (Kernel 5.14+) |
| 배포판 | Debian/Ubuntu 기반 (Docker: `python:3.10-slim`) |
| 아키텍처 | x86_64 (amd64) |

---

## Python 환경

| 항목 | 내용 |
|------|------|
| 외부 개발 환경 | Python 3.13.4 (직접 다운로드 후 venv 구성) |
| 사내 운영 서버 | **Python 3.12 까지 지원** (최대 버전) |
| 권장 타겟 버전 | **Python 3.12** (운영 서버 기준) |

---

## 네트워크 / 방화벽 제약

- **사내망(폐쇄망)** 환경 → 외부 인터넷 직접 접근 불가
- 외부 서버에서 직접 다운로드하려면 방화벽 해제 필요 (어려움)
- **사용 불가 예시:**
  - `huggingface-cli` 를 통한 모델 직접 다운로드
  - pip install 시 외부 PyPI 직접 접근 (미러 서버 또는 사전 패키징 필요)

### ⚠️ 주의사항
- 외부 의존성(HuggingFace 모델, 외부 API 등)은 **사전에 다운로드 후 내부 반입** 하거나 사내 미러 서버 활용 필요
- 런타임 중 외부 네트워크 호출은 기본적으로 차단된다고 가정하고 설계

### 모델 사용 정책
- HuggingFace 등 외부에서 모델을 **업무 PC에서 직접 다운로드** 후 개발 환경에 복사하여 사용
- 즉, 개발 시에는 **어떤 HuggingFace 모델이든 사용 가능** (런타임 중 직접 다운로드만 불가)
- 현재 사용 중인 임베딩 모델: **BGE-M3** (`BAAI/bge-m3`)

---

---

## LLM 환경

| 항목 | 내용 |
|------|------|
| LLM | 사내 지원 LLM (API 호출 방식) |
| 호출 방식 | **OpenAI 호환 형식** (`/v1/chat/completions`) |
| 클라이언트 | `openai` 라이브러리 사용, `base_url`을 사내 엔드포인트로 지정 |

---

## 기술 스택

### 백엔드
| 항목 | 내용 |
|------|------|
| 서버 프레임워크 | **FastAPI** |
| 임베딩 모델 | **BGE-M3** (BAAI/bge-m3) |
| Vector DB | **FAISS** (기본값, 상황에 따라 교체 가능) |
| 데이터 소스 | **TXT 파일** (Parser를 통해 파싱 후 RAG 주입) |
| 챗봇 정의 저장 | **JSON 파일** (프로젝트 폴더 내 관리) |
| 스트리밍 | **SSE** (Server-Sent Events) |

### 프론트엔드
| 항목 | 내용 |
|------|------|
| 프레임워크 | **React + Vite + TypeScript** |
| UI 컴포넌트 | **shadcn/ui** + **Tailwind CSS** |
| 채팅 렌더링 | **react-markdown** + 코드 하이라이팅 |
| 스트리밍 | SSE 기반 실시간 토큰 출력 |
| 라우팅 | `/` → 채팅 UI, `/admin` → 관리자 대시보드 |
| 빌드 결과물 | FastAPI `/static` 으로 서빙 (단일 서버 구성) |

---

## SSL 설정

- **사내망 특성상 SSL 검증 비활성화 필요**
- 모든 HTTP 클라이언트(requests, httpx 등)에서 `verify=False` 기본 적용
- LLM API 호출, 외부 연동 등 **전체 적용** (매번 수정 불필요하도록 공통 클라이언트로 관리)

```python
# 공통 HTTP 클라이언트 예시
import httpx
client = httpx.Client(verify=False)

import requests
session = requests.Session()
session.verify = False
```

> ⚠️ SSL 비활성화는 사내망 전용 설정. 외부 배포 시 반드시 재활성화 필요.

---

## 코드베이스

- **완전 새로 작성** (기존 코드 없음)

---

## TODO (추후 확인 필요)

- [ ] 사내 LLM API 엔드포인트 및 인증 방식 확인
- [ ] 사내 PyPI 미러 서버 존재 여부 확인
- [ ] GPU 사용 가능 여부 확인

---

_다음: 프로젝트 개요 및 아키텍처 문서 추가 예정_
