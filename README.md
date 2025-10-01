
# 📝 Essay Evaluation Service

AI 기반 **학생 에세이 자동 평가 시스템**

* FastAPI 비동기 엔드포인트
* Azure OpenAI (`gpt-5-mini`) 연동
* Prompt 버전 관리 (Prompt Ops)
* Langfuse Trace 저장 및 성능 분석 지원

---

## 🚀 프로젝트 개요

학생 제출 에세이를 **4단계 레벨 그룹(Basic · Intermediate · Advanced · Expert)** 기준으로 자동 평가합니다.
Rubric 체계(서론, 본론, 결론, 문법)에 따라 **점수, 교정, 피드백**을 생성하며, Prompt 버전 관리와 성능 로그(Trace)를 통해 안정적인 실험과 품질 보장을 제공합니다.

---

## ⚙️ 환경 세팅

### 1. 저장소 클론

```bash
git clone https://github.com/Cheeyoung-Yoon/creverse.git
cd creverse
```

### 2. 환경 변수 설정

`.env` 파일 생성 (샘플: `.env.example` 참고)

```env
AZURE_OPENAI_ENDPOINT=https://<YOUR>.openai.azure.com/
AZURE_OPENAI_API_KEY=<YOUR_KEY>
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini-<YOURNAME>
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# 선택 (Langfuse)
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. 실행 방법

#### 로컬

```bash
conda create -n essay-eval python=3.12
conda activate essay-eval
pip install -r requirements.txt
uvicorn app.main:app --reload
```

→ Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)

#### Docker

```bash
docker compose up --build
```

---

## 📡 API 사용법

### 요청

```http
POST /v1/essay-eval
Content-Type: application/json
```

```json
{
  "rubric_level": "Intermediate",
  "topic_prompt": "Describe your dream vacation.",
  "submit_text": "I want to go to...",
}
```

### 응답 (요약)

```json
{
  "level_group": "Intermediate",
  "grammar": {
    "score": 1,
    "corrections": [
      { "highlight": "I want go", "correction": "I want to go" }
    ]
  },
  "structure": {
    "introduction": { "score": 2, "feedback": "..." }
  },
  "aggregated": { "score": 1, "feedback": "..." },
  "timings": { "total": 1289.4 }
}
```

---

## 📂 프로젝트 구조

```bash
essay-eval/
├── app/
│   ├── api/v1/essay_eval.py     # POST /v1/essay-eval
│   ├── client/azure_openai.py   # Azure OpenAI 어댑터
│   ├── services/evaluation/     # pre/rubric/post 평가 로직
│   ├── utils/                   # PromptLoader, Tracer
│   └── core/                    # 설정, 상수
├── prompts/                     # Prompt 버전 관리 (semver)
├── tests/                       # Unit/Integration 테스트
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## 🧩 평가 로직

1. **Pre-Process**: 언어/길이 검증
2. **Rubric Chain**: 서론 → 본론 → 결론 (순차), 문법 (병렬)
3. **Aggregation**: 점수 합산 및 가중치 반영
4. **Post-Evaluate**: 레벨 그룹별 기준 적용
5. **Trace 저장**: Langfuse 기록

---

## 🧪 테스트

```bash
pytest --maxfail=1 --disable-warnings -q
pytest --cov=app --cov-report=term-missing
```

---

## 📊 성능 리포트

* 평균 처리 시간: XX ms
* 요청당 API 비용: $XX (gpt-5-mini 기준)
* 점수 분포: 레벨 상승에 따라 평균 점수 점진적 감소

| Prompt_Version | Avg_Latency (ms) | Avg_Cost (USD) | 샘플 개수 |
|----------------|------------------|----------------|-----------|
| v1.0.0         | 16,353           | 0.00372        | 32        |
| v1.1.0         | 9,592            | 0.00220        | 31        |
| v1.2.0         | 9,269            | 0.00216        | 37        |
| v1.3.0         | 10,272           | 0.00206        | 32        |
| v1.4.0         | 11,863           | 0.00240        | 32        |
| v1.4.1         | 10,407           | 0.00232        | 32        |
| **v1.5.0**     | **9,324**        | **0.0222**     | 32        |


-v1.0.0 : 작동을 위한 prompt
-v1.1.0 : 1차 최적화 진행
-v1.2.0 : gpt 5 mini 에 맞고, 과도한 feedback 방지 
-v1.3.0 : prompt를 가장 경량화 시킴 (결과가 유의미하지 못함)
-v1.4.0 : v1.2.0을 조금더 경량화 시킴 (약간의 오류 발생)
-v1.4.1 : v11.4.0의 문장 순서 수정 및 강제성 주입
-v1.5.0 : grammer은 v1.4.1 채용 , 나머지는 v1.2.0 채용
---

## 📌 디자인 결정 근거

* **비동기 FastAPI** → 성능 최적화 (`asyncio.gather`)
* **Prompt Ops 버전 관리** → `prompts/vX.Y.Z/` 관리 + 누락 즉시 예외
* **Langfuse Trace 연동** → LLM 호출·프롬프트 기록 자동화
* **Pydantic** → API 경계 검증, 내부 로직은 순수 함수로 유지
* **단순 아키텍처** → api → services → client 단방향 설계

---

## 📋 TODO (향후 고도화)

* [ ] **CEFR 기반 어휘 난이도 평가**
* [ ] **길이 기반 점수 시스템**
* [ ] **언어 기반 가중치 적용**
* [ ] **적응형 레벨 평가 로직**
* [ ] **피드백 고도화 (CEFR/길이/언어 반영)**

---

## 👨‍💻 작성자

* 지원자: 윤치영
* 포지션: AI Agent Engineer
