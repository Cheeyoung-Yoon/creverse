





```
essay-eval/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── essay_eval.py          # POST /v1/essay-eval
│   ├── client/
│   │   └── azure_openai.py            # Azure OpenAI 어댑터(재시도/타임아웃)
│   ├── core/
│   │   ├── config.py                  # .env 로드, Settings
│   │   └── constants.py               # 레벨/길이/CEFR 등 상수
│   ├── services/
│   │   ├── evaluation/
│   │   │   ├── pre_process.py         # 길이·언어·온토픽 체크 (pure)
│   │   │   ├── rubric_chain.py        # 서론→본론→결론(순차), 문법(병렬)
│   │   │   └── post_evaluate.py       # 레벨 가중·정합성 (pure)
│   │   └── essay_evaluator.py         # 오케스트레이션 (DI)
│   └── utils/
│       ├── prompt_loader.py           # prompts/{version}.yaml 로딩
│       └── tracer.py                  # Langfuse 래퍼(선택)
├── prompts/
│   └──              # Prompt Ops (semver)
├── tests/
│   ├── unit/                          # pre/post/loader 순수 함수 테스트
│   └── integration/                   # API + FakeLLM 통합 테스트
├── scripts/                           # (배치/리포트 등 선택)
├── docker-compose.yml
├── pyproject.toml
└── .env.example


```

## Design Rationale

본 프로젝트의 아키텍처 설계는 다음과 같은 현실적 제약과 목적을 기반으로 결정되었습니다.

1. **1인 개발 & 제한된 작업 시간**

   * 실제 구현 가능한 시간이 **8시간 이내**이므로, 가장 중요한 목표는 **빠른 코딩 및 단순한 구조**
   * 복잡한 계층 설계보다는 최소한의 레이어만 두어 개발/디버깅/테스트 속도를 우선의 아키텍팅

2. **명확한 요구사항 & 확장성은 우선 아님**

   * 과제의 요구사항이 **고정된 범위 내에서 명확**하기 때문에, 초기 단계에서 확장성을 고려할 불필요
   * 추후 확장이 필요하다면 `app/` 내부에 모듈 추가 또는 `client/` 레이어를 통한 외부 서비스 연동으로 충분히 대응 가능

3. **Prompt 버전 관리 & 테스트 용이성 확보**

   * Prompt는 `prompts/` 폴더에서 **버전 관리(semver)**를 적용하여 롤백 및 실험 재현성을 보장
   * 핵심 비즈니스 로직(`pre_process`, `post_evaluate`, `rubric_chain`)은 **순수 함수화**하여 단위테스트 및 빠른 리팩토링 가능 
   * 서비스 계층은 `Fake LLM Client`를 주입 가능하도록 설계해 **통합 테스트도 최소 비용**으로 실행



## 🔑 선택한 아키텍처의 의미

* **Simple Layered Architecture** 채택

  * `api → services → client` 단방향 흐름, `core/utils`는 보조 레이어로만 사용.
  * 외부 I/O(Azure OpenAI, Langfuse 등)는 `client`에 격리, 나머지는 테스트 가능하게 설계.
  * `prompts`는 별도 디렉토리에서 버전 관리, `tracer`로 실행 시점 추적.

→ 결과적으로, 이번 과제 목적(제한 시간 내 완성 + 테스트 가능성 + Prompt Ops 관리)에 **최적화된 구조**



여기 README에 들어갈 **간단한 설명** 버전으로 정리해봤어:

---

### Why Pydantic?

**API 입출력(Request/Response) 모델** 정의에 Pydantic을 사용

* **자동 검증 (Validation)**
  클라이언트에서 잘못된 데이터(JSON 형식, 타입 불일치 등)가 들어올 경우 FastAPI + Pydantic이 즉시 검증 오류(422)를 반환으로 예상하지 못한 에러 방지. 중복 검증 코드 감소

* **데이터 변환 (Parsing)**
  문자열 `"123"`을 정수 `123`으로 자동 변환하는 등, 타입 변환을 지원합니다.

* **문서화 (Docs & Schema)**
  `response_model`을 지정하면 OpenAPI 스펙 및 API 문서가 자동으로 생성됩니다.

* **유지보수성 (Maintainability)**
  API 경계에서 명확한 계약(Contract)을 정의하여, 내부 로직과 분리된 안정적인 개발이 가능합니다.

⚡ 내부 서비스 로직에서는 불필요한 오버헤드를 줄이기 위해 **dict 또는 dataclass**를 활용하며, **Pydantic은 API 경계에서만 사용**합니다.

