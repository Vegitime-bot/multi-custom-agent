"""
mock_ingestion_server.py - Mock Ingestion 서버 (포트 8001)
docs/TESTING.md 기준으로 구현.
INGESTION_API.md 명세(단일 DB / 다중 DB)를 모두 지원한다.

실행:
    uvicorn mock_ingestion_server:app --port 8001
"""
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Mock Ingestion Server", version="1.0.0")


# ── 목업 데이터 ────────────────────────────────────────────────────
MOCK_DATA: dict[str, list[dict]] = {
    "db_001": [
        {"doc_id": "a1", "content": "FastAPI는 Python 기반의 고성능 웹 프레임워크입니다. 비동기 처리를 지원하며 자동 API 문서 생성 기능이 있습니다.", "source": "tech_doc_001.txt"},
        {"doc_id": "a2", "content": "uvicorn은 ASGI 서버로 FastAPI와 함께 사용됩니다. 고성능 비동기 웹 서버로 Gunicorn과 함께 프로덕션에서 사용됩니다.", "source": "tech_doc_002.txt"},
        {"doc_id": "a3", "content": "Pydantic은 Python용 데이터 검증 라이브러리입니다. 타입 힌트를 기반으로 데이터 모델을 정의하고 검증합니다.", "source": "tech_doc_003.txt"},
        {"doc_id": "a4", "content": "Python 3.9 이상의 버전을 권장합니다. typing 모듈의 새로운 기능들을 활용할 수 있습니다.", "source": "tech_doc_004.txt"},
        {"doc_id": "a5", "content": "Docker와 Kubernetes를 활용한 컨테이너 배포를 지원합니다. CI/CD 파이프라인과 쉽게 통합됩니다.", "source": "tech_doc_005.txt"},
    ],
    "db_002": [
        {"doc_id": "b1", "content": "SQLAlchemy는 Python ORM 라이브러리입니다. 관계형 데이터베이스와 객체 간 매핑을 제공합니다.", "source": "dev_guide_001.txt"},
        {"doc_id": "b2", "content": "PostgreSQL은 오픈소스 관계형 데이터베이스입니다. JSONB 지원, 트랜잭션, 복제 기능이 강력합니다.", "source": "dev_guide_002.txt"},
        {"doc_id": "b3", "content": "Redis는 인메모리 데이터 저장소입니다. 캐싱, 세션 관리, 메시지 브로커로 활용됩니다.", "source": "dev_guide_003.txt"},
        {"doc_id": "b4", "content": "Git 브랜치 전략: main(master), develop, feature, release, hotfix 브랜치를 활용한 Git Flow 전략을 권장합니다.", "source": "dev_guide_004.txt"},
        {"doc_id": "b5", "content": "JWT(Json Web Token)는 인증 및 인가에 사용됩니다. Access Token과 Refresh Token을 분리하여 관리하세요.", "source": "dev_guide_005.txt"},
    ],
    "db_003": [
        {"doc_id": "c1", "content": "연차 신청은 사내 포털을 통해 진행합니다. 신청은 최소 3일 전에 해야 하며, 팀장 승인이 필요합니다.", "source": "hr_policy_001.txt"},
        {"doc_id": "c2", "content": "복리후생 안내: 의료비 지원(연간 100만원 한도), 교육비 지원, 경조사 지원, 휴양비 지원이 있습니다.", "source": "hr_policy_002.txt"},
        {"doc_id": "c3", "content": "재택근무 규정: 주 2회까지 가능하며, 사전에 팀장과 협의 필요. 코어타임은 10:00-15:00입니다.", "source": "hr_policy_003.txt"},
        {"doc_id": "c4", "content": "성과 평가: 상반기(6월), 하반기(12월) 2회 진행됩니다. 자기 평가와 상사 평가를 포함합니다.", "source": "hr_policy_004.txt"},
        {"doc_id": "c5", "content": "사내 교육: 매월 마지막 금요일 기술 세미나, 외부 교육비 연간 50만원 지원, 온라인 강의 플랫폼 무료 제공.", "source": "hr_policy_005.txt"},
    ],
    "db_004": [
        {"doc_id": "d1", "content": "반도체 설계: RTL(Register Transfer Level) 설계는 하드웨어를 레지스터와 논리 게이트 수준으로 기술합니다.", "source": "rtl_doc_001.txt"},
        {"doc_id": "d2", "content": "Verilog HDL은 하드웨어 기술 언어입니다. 디지털 회로를 모듈 단위로 설계하고 시뮬레이션할 수 있습니다.", "source": "rtl_doc_002.txt"},
        {"doc_id": "d3", "content": "SystemVerilog는 Verilog의 확장입니다. 객체 지향 프로그래밍 지원, Assertion, Coverage 기능이 추가되었습니다.", "source": "rtl_doc_003.txt"},
    ],
    "db_005": [
        {"doc_id": "e1", "content": "AI Agent 아키텍처: RAG(Retrieval-Augmented Generation)는 외부 지식을 검색하여 LLM 응답을 보강하는 기법입니다.", "source": "ai_doc_001.txt"},
        {"doc_id": "e2", "content": "멀티 테넌트 시스템: 하나의 인프라에서 여러 고객(테넌트)의 데이터를 격리하여 관리하는 아키텍처입니다.", "source": "ai_doc_002.txt"},
        {"doc_id": "e3", "content": "Factory Method 패턴: 객체 생성 로직을 캡슐화하여 런타임에 다양한 구현체를 생성할 수 있게 합니다.", "source": "ai_doc_003.txt"},
    ],
    # ========== HR Policy 전문 DB ==========
    "db_hr_policy": [
        {"doc_id": "hr_p1", "content": "인사평가제도: 연 2회(상반기/하반기) 자기평가-상사평가-면담 순으로 진행. 평가 항목: 업무성과(60%), 역량(25%), 태도(15%).", "source": "hr_policy_detail.txt"},
        {"doc_id": "hr_p2", "content": "채용 프로세스: 서류전형-1차 면접-2차 면접-최종 합격. 채용공고는 사내 포털 및 외부 채용사이트에 게시.", "source": "recruitment_guide.txt"},
        {"doc_id": "hr_p3", "content": "승진 기준: 직급별 최소 근무기간 충족, 성과평가 우수, 직무능력 인정. 승진심의위원회 심의 거쳐 결정.", "source": "promotion_policy.txt"},
        {"doc_id": "hr_p4", "content": "징계 규정: 주의-견책-감봉-정직-해임 순. 징계사유: 품위유지의무 위반, 업무태만, 금품수수 등.", "source": "disciplinary_rules.txt"},
        {"doc_id": "hr_p5", "content": "인사발령: 승진, 전보, 휴직, 복직, 퇴직 등. 인사위원회 심의 후 결정. 발령일 7일 전 통보.", "source": "hr_appointment.txt"},
    ],
    # ========== HR Benefit 전문 DB ==========
    "db_hr_benefit": [
        {"doc_id": "hr_b1", "content": "급여체계: 기본급 + 직급수당 + 성과급 + 기타수당. 매월 25일 지급. 연봉협상은 연말에 진행.", "source": "salary_guide.txt"},
        {"doc_id": "hr_b2", "content": "연차휴가: 입사 후 1년 근무 시 15일 발생. 3년 이상 근무 시 2년마다 1일씩 가산(최대 25일).", "source": "annual_leave_policy.txt"},
        {"doc_id": "hr_b3", "content": "휴가 종류: 연차, 반차(4시간), 경조휴가(3-5일), 생리휴가(월1일), 출산휴가(90일), 육아휴직(1년).", "source": "leave_types.txt"},
        {"doc_id": "hr_b4", "content": "4대보험: 국민연금(4.5%), 건강보험(3.545%), 고용보험(0.9%), 산재보험(사업자부담). 가입 및 변경은 인사팀에서 처리.", "source": "insurance_guide.txt"},
        {"doc_id": "hr_b5", "content": "경조사 지원: 결혼(50만원+화환), 출산(30만원+선물), 본인/배우자 부모상(30만원+화환), 본인/배우자 조부모상(10만원).", "source": "family_event_support.txt"},
    ],
    # ========== HR Overview (상위 Agent용) ==========
    "db_hr_overview": [
        {"doc_id": "hr_ov1", "content": "인사팀 주요 업무: 채용, 교육, 평가, 승진, 복리후생, 노무관리. 사내 인사제도 총괄.", "source": "hr_overview.txt"},
        {"doc_id": "hr_ov2", "content": "인사팀 조직: 채용담당, 교육담당, 평가/보상담당, 복리후생담당, 노무담당. 총 15명 구성.", "source": "hr_team_structure.txt"},
    ],
    # ========== Tech Backend 전문 DB ==========
    "db_backend": [
        {"doc_id": "be_1", "content": "FastAPI ORM: SQLAlchemy와 함께 사용. SessionLocal으로 DB 세션 관리, Depends로 의존성 주입.", "source": "fastapi_db_guide.txt"},
        {"doc_id": "be_2", "content": "Python AsyncIO: async/await 키워드로 비동기 처리. asyncio.run()으로 이벤트 루프 실행.", "source": "python_async.txt"},
        {"doc_id": "be_3", "content": "API 설계 원칙: RESTful 원칙 준수. HTTP 메서드(GET/POST/PUT/DELETE)로 CRUD 표현. 상태코드 명확히 사용.", "source": "api_design_guide.txt"},
        {"doc_id": "be_4", "content": "PostgreSQL 인덱싱: B-tree(기본), Hash, GiST, GIN 인덱스. WHERE절에 자주 사용하는 컬럼에 인덱스 생성.", "source": "db_optimization.txt"},
        {"doc_id": "be_5", "content": "Redis 캐싱: TTL(Time To Live) 설정, 캐시 무효화 전략, Cache-Aside 패턴 사용.", "source": "redis_caching.txt"},
    ],
    # ========== Tech Frontend 전문 DB ==========
    "db_frontend": [
        {"doc_id": "fe_1", "content": "React Hooks: useState(상태관리), useEffect(사이드이펙트), useContext(전역상태), useRef(DOM접근).", "source": "react_hooks.txt"},
        {"doc_id": "fe_2", "content": "Vue.js Composition API: setup() 함수 내에서 reactive, ref, computed, watch 사용. 코드 재사용성 향상.", "source": "vue3_composition.txt"},
        {"doc_id": "fe_3", "content": "CSS Flexbox: 1차원 레이아웃. justify-content(메인축 정렬), align-items(교차축 정렬), flex-wrap(줄바꿈).", "source": "css_flexbox.txt"},
        {"doc_id": "fe_4", "content": "JavaScript ES6+: 구조분해할당, 스프레드 연산자, 화살표함수, 템플릿리터럴, async/await 문법.", "source": "js_modern.txt"},
        {"doc_id": "fe_5", "content": "TypeScript: 정적 타입 검사, 인터페이스, 제네릭, 엄격 모드(strict) 사용 권장.", "source": "typescript_guide.txt"},
    ],
    # ========== Tech DevOps 전문 DB ==========
    "db_devops": [
        {"doc_id": "do_1", "content": "Docker 이미지 최적화: 멀티스테이지 빌드, .dockerignore 사용, 작은 베이스 이미지(alpine) 선택.", "source": "docker_best_practice.txt"},
        {"doc_id": "do_2", "content": "Kubernetes Pod: 컨테이너의 기본 실행 단위. replicas로 확장, readiness/liveness 프로브로 헬스체크.", "source": "k8s_pod_guide.txt"},
        {"doc_id": "do_3", "content": "CI/CD 파이프라인: GitLab CI/GitHub Actions. Build-Test-Deploy 단계. 자동화된 테스트와 코드 품질 게이트.", "source": "cicd_pipeline.txt"},
        {"doc_id": "do_4", "content": "모니터링: Prometheus(메트릭 수집) + Grafana(시각화) + Alertmanager(알림). SLI/SLO 기반 알림 설정.", "source": "monitoring_stack.txt"},
        {"doc_id": "do_5", "content": "GitOps: Git 저장소를 단일 진실의 소스로 사용. ArgoCD로 자동 배포. 변경 이력 관리.", "source": "gitops_guide.txt"},
    ],
    # ========== Tech Overview (상위 Agent용) ==========
    "db_tech_overview": [
        {"doc_id": "tech_ov1", "content": "기술지원팀: 소프트웨어 개발(FastAPI, Python, DB), 프론트엔드(React, Vue), 인프라(Docker, K8s) 지원.", "source": "tech_overview.txt"},
        {"doc_id": "tech_ov2", "content": "기술스택: Python 3.11, FastAPI, PostgreSQL 15, React 18, Docker, Kubernetes, Redis, RabbitMQ.", "source": "tech_stack.txt"},
    ],
    # ========== RTL Verilog 전문 DB ==========
    "db_rtl_verilog": [
        {"doc_id": "rtl_v1", "content": "Verilog 모듈 기본: module 선언, input/output/inout 포트, wire/reg 타입, always 블록(조합/순차).", "source": "verilog_basics.txt"},
        {"doc_id": "rtl_v2", "content": "카운터 설계: 4비트 업카운터, 동기 리셋/비동기 리셋, enable 신호. non-blocking 할당(<=) 사용.", "source": "counter_design.txt"},
        {"doc_id": "rtl_v3", "content": "FSM 설계: Mealy/Moore 머신. 3단계 코딩: 상태 레지스터, 다음 상태 로직, 출력 로직 분리.", "source": "fsm_design.txt"},
        {"doc_id": "rtl_v4", "content": "테스트벤치: timescale, initial 블록, $dumpfile/$dumpvars, # 딜리, $finish. self-checking testbench 권장.", "source": "testbench_guide.txt"},
        {"doc_id": "rtl_v5", "content": "인터페이스: AXI4 프로토콜(Write Address, Write Data, Write Response, Read Address, Read Data 채널).", "source": "axi_protocol.txt"},
        {"doc_id": "rtl_v6", "content": "SystemVerilog 확장: typedef enum, struct, union, interface, modport, always_comb, always_ff.", "source": "systemverilog.txt"},
    ],
    # ========== RTL Synthesis 전문 DB ==========
    "db_rtl_synthesis": [
        {"doc_id": "rtl_s1", "content": "RTL 합성: HDL을 게이트 넷리스트로 변환. Synopsys Design Compiler, Cadence Genus 등 사용.", "source": "synthesis_intro.txt"},
        {"doc_id": "rtl_s2", "content": "타이밍 분석: Setup 시간, Hold 시간. Slack = Required Time - Arrival Time. 음수면 위배.", "source": "timing_analysis.txt"},
        {"doc_id": "rtl_s3", "content": "면적 최적화: 리소스 공유, 상수 전파, 데드 코드 제거. 면적 대비 성능 트레이드오프.", "source": "area_optimization.txt"},
        {"doc_id": "rtl_s4", "content": "전력 최적화: 클럭 게이팅, 멀티-Vt 셀 사용, 동적/정적 전력 관리. 파이프라이닝 고려.", "source": "power_optimization.txt"},
        {"doc_id": "rtl_s5", "content": "FPGA 구현: Xilinx Vivado, Intel Quartus. 제약조건(.xdc/.sdc) 설정, IO Planning, Bitstream 생성.", "source": "fpga_implementation.txt"},
    ],
}


# ── 요청 스키마 ────────────────────────────────────────────────────
class SingleSearchRequest(BaseModel):
    query: str
    k: int = 10
    filter_metadata: Optional[dict] = None


class MultiSearchRequest(BaseModel):
    query: str
    k: int = 10
    db_ids: Optional[list[str]] = None
    filter_metadata: Optional[dict] = None


# ── 검색 헬퍼 ─────────────────────────────────────────────────────
def _search_db(db_id: str, query: str, k: int) -> list[dict]:
    """지정된 DB에서 목업 결과를 반환한다 (실제 검색 없이 전체 반환)."""
    results = MOCK_DATA.get(db_id, [])
    # 실제 환경에서는 벡터 유사도 기반 검색; 여기서는 쿼리 단어 포함 여부로 간단 필터
    query_lower = query.lower()
    scored = []
    for doc in results:
        score = 1.0 if query_lower in doc["content"].lower() else 0.5
        scored.append({**doc, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


# ── 단일 DB 검색 (POST) ───────────────────────────────────────────
@app.post("/databases/{db_id}/search")
async def search_single_post(db_id: str, req: SingleSearchRequest):
    results = _search_db(db_id, req.query, req.k)
    return {
        "db_id": db_id,
        "query": req.query,
        "results": results,
    }


# ── 단일 DB 검색 (GET) ────────────────────────────────────────────
@app.get("/databases/{db_id}/search")
async def search_single_get(
    db_id: str,
    query: str = Query(...),
    k: int = Query(10),
):
    results = _search_db(db_id, query, k)
    return {
        "db_id": db_id,
        "query": query,
        "results": results,
    }


# ── 다중 DB 검색 ──────────────────────────────────────────────────
@app.post("/search/multi")
async def search_multi(req: MultiSearchRequest):
    # db_ids=None → 모든 DB 검색
    target_ids = req.db_ids if req.db_ids is not None else list(MOCK_DATA.keys())

    # 빈 배열 → 빈 결과
    if req.db_ids is not None and len(req.db_ids) == 0:
        return {"query": req.query, "db_ids_received": [], "results": []}

    results = []
    for db_id in target_ids:
        if db_id in MOCK_DATA:  # 존재하지 않는 DB ID는 무시
            results.extend(_search_db(db_id, req.query, req.k))

    # 점수 기준 재정렬
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {
        "query": req.query,
        "db_ids_received": target_ids,
        "results": results,
    }


# ── TESTING.md 호환 /search 엔드포인트 ───────────────────────────
class LegacySearchRequest(BaseModel):
    query: str
    db_ids: list[str]


@app.post("/search")
async def search_legacy(req: LegacySearchRequest):
    """docs/TESTING.md의 옵션 A 호환 엔드포인트"""
    results = []
    for db_id in req.db_ids:
        results.extend(MOCK_DATA.get(db_id, []))
    return {
        "query": req.query,
        "db_ids_received": req.db_ids,
        "results": results,
    }


# ── 헬스체크 ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "available_dbs": list(MOCK_DATA.keys())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mock_ingestion_server:app", host="0.0.0.0", port=8001, reload=False)
