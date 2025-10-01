
# 📑 Essay Evaluation Project Report

## 1. 프로젝트 개요
- 목적: 학생 에세이 자동 평가 시스템 구현
- 주요 요구사항:
  - Prompt Ops 기반 버전 관리
  - FastAPI 비동기 API
  - Rubric 기반 자동 평가 로직
  - Langfuse Trace 기록 및 분석
- 사용 모델: Azure OpenAI `azure openai gpt-5-mini`

---

## 2. 시스템 아키텍처

### 2.1 전체 시스템 구조
```mermaid
flowchart TB
    subgraph "Client Layer"
        A[HTTP Client Request]
    end
    
    subgraph "API Layer"
        B[FastAPI Router]
        C[Request Validation]
        D[Response Formatting]
    end
    
    subgraph "Service Layer"
        E[EssayEvaluator]
        F[Pre-Process]
        G[Grammar Evaluator]
        H[Structure Evaluator]
        I[Post-Process]
    end
    
    subgraph "Infrastructure Layer"
        J[PromptLoader]
        K[Azure OpenAI Client]
        L[Langfuse Tracer]
    end
    
    subgraph "External Services"
        M[Azure OpenAI GPT-4o-mini]
        N[Langfuse Cloud]
    end
    
    A --> B
    B --> C
    C --> E
    E --> F
    F --> G
    F --> H
    G --> I
    H --> I
    I --> D
    D --> A
    
    G --> J
    H --> J
    G --> K
    H --> K
    K --> M
    E --> L
    L --> N
````

### 2.2 핵심 컴포넌트

#### **API Layer**
- **FastAPI Router**: RESTful API 엔드포인트 제공 (`/v1/evaluate`)
- **Dependency Injection**: LLM, PromptLoader, EssayEvaluator 인스턴스 관리
- **Request/Response Models**: Pydantic 기반 데이터 검증

#### **Service Layer** 
- **EssayEvaluator**: 전체 평가 프로세스 오케스트레이션
- **GrammarEvaluator**: 문법 평가 전담 서비스
- **StructureEvaluator**: 서론/본론/결론 구조 평가 전담 서비스

#### **Infrastructure Layer**
- **PromptLoader**: 버전별 프롬프트 관리 (`prompts/v1.x.x/`)
- **ObservedLLM**: Azure OpenAI 클라이언트 + Langfuse 추적 래퍼
- **Price Tracker**: 토큰 사용량 및 비용 추적

#### **Data Flow**
1. **입력 검증**: 텍스트 길이, 언어 체크
2. **병렬 평가**: 문법 평가와 구조 평가 동시 실행
3. **결과 집계**: 개별 점수 통합 및 피드백 생성
4. **후처리**: 레벨별 가중치 적용 및 최종 스코어링

---

## 3. Evaluation Workflow

### 3.1 전체 처리 흐름
```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Router
    participant Eval as EssayEvaluator
    participant Pre as Pre-Process
    participant Grammar as GrammarEvaluator
    participant Structure as StructureEvaluator
    participant Azure as Azure OpenAI
    participant Langfuse
    participant Post as Post-Process

    Client->>API: POST /v1/evaluate
    API->>Eval: evaluate(request)
    
    Eval->>Pre: pre_process_essay()
    Pre-->>Eval: validation result
    
    par 병렬 평가
        Eval->>Grammar: check_grammar()
        Grammar->>Azure: LLM 호출 (문법)
        Grammar->>Langfuse: 추적 로깅
        Azure-->>Grammar: 평가 결과
        Grammar-->>Eval: grammar_result
    and
        Eval->>Structure: run_structure_chain()
        loop 서론, 본론, 결론
            Structure->>Azure: LLM 호출 (구조)
            Structure->>Langfuse: 추적 로깅
            Azure-->>Structure: 섹션 평가
        end
        Structure-->>Eval: structure_result
    end
    
    Eval->>Post: finalize_scf()
    Post-->>Eval: 최종 점수/피드백
    Eval-->>API: EssayEvalResponse
    API-->>Client: JSON Response
```

### 3.2 세부 처리 단계

#### **3.2.1 Pre-Processing**
```python
# app/services/evaluation/pre_process.py
def pre_process_essay(text: str, topic: str, level: str) -> PreProcessResult:
    word_count = len(text.split())
    is_english = detect_language(text) == 'en'
    meets_length_req = check_length_requirement(word_count, level)
    
    return PreProcessResult(
        word_count=word_count,
        meets_length_req=meets_length_req,
        is_english=is_english,
        is_valid=meets_length_req and is_english
    )
```

#### **3.2.2 병렬 평가 실행**
```python
# app/services/essay_evaluator.py
async def _evaluate_impl(self, req: EssayEvalRequest) -> EssayEvalResponse:
    # 평가기 초기화
    grammar_eval = GrammarEvaluator(client=self.llm, loader=self.loader)
    structure_eval = StructureEvaluator(client=self.llm, loader=self.loader)
    
    # 병렬 실행으로 성능 최적화
    grammar_res, structure_res = await asyncio.gather(
        grammar_eval.check_grammar(req.submit_text, level=req.rubric_level),
        structure_eval.run_structure_chain(
            intro=req.submit_text, 
            body=req.submit_text, 
            conclusion=req.submit_text, 
            level=req.rubric_level
        )
    )
```

#### **3.2.3 구조 평가 체인**
```python
# app/services/evaluation/rubric_chain/context_eval.py
async def run_structure_chain(self, intro: str, body: str, conclusion: str, level: str):
    results = {}
    previous_summary = None
    
    # 순차적 구조 평가 (컨텍스트 연결)
    for section, text in [("introduction", intro), ("body", body), ("conclusion", conclusion)]:
        result = await self._evaluate_section(
            rubric_item=section,
            text=text,
            level=level,
            previous_summary=previous_summary
        )
        results[section] = result
        previous_summary = result.get("feedback", "")
    
    return results
```

#### **3.2.4 Langfuse 추적 통합**
```python
# app/utils/tracer.py
@observe(name="llm.client", as_type="span")
async def run_azure_openai(self, *, messages, json_schema, prompt_key="generate", **kwargs):
    with lf.start_as_current_generation(name=f"llm.{prompt_key}") as gen:
        gen.update(input={"messages": messages}, metadata={
            "service": "azure-openai",
            "prompt_key": prompt_key,
            "prompt_version": prompt_version
        })
        
        result = await self.inner.run_azure_openai(messages, json_schema, **kwargs)
        gen.update(output=result)
        return result
```

### 3.3 성능 최적화 특징

- **비동기 처리**: `asyncio.gather()`로 문법/구조 평가 병렬 실행
- **프롬프트 캐싱**: `@lru_cache`를 통한 PromptLoader 인스턴스 재사용
- **연결 풀링**: 단일 Azure OpenAI 클라이언트 인스턴스 공유
- **타이밍 측정**: 각 단계별 처리 시간 추적 및 분석
- **지연 로딩**: Langfuse 클라이언트 조건부 초기화

---

## 4. 데이터 및 평가 기준

* 입력 데이터: 40개 (레벨별 10개씩, Basic/Intermediate/Advanced/Expert)
* 평가 Rubric:

  * 서론 / 본론 / 결론 / 문법 (각 0~2점)

---

## 4. 구현 내용

### 4.1 Pre-Processing

* 텍스트 길이 및 언어 체크
* 입력 데이터 정규화

### 4.2 Rubric Evaluation

* **순차 평가**: 서론 → 본론 → 결론
* **병렬 평가**: 문법

### 4.3 Post-Evaluation

* 레벨 그룹별 기준 적용 (길이/어휘 난이도)
* 점수 스케일링 및 가중치 반영

### 4.4 Trace 관리

* Langfuse 프로젝트: `essay-eval`
* Prompt 버전 관리: `prompt/` 폴더

---

## 5. 결과 분석

### 5.1 레벨 그룹별 변화

* 동일 데이터셋을 평가했을 때 레벨 기준이 올라감에 따라 점수가 점차 하락

| Level        | Prompt_Version | Total_Essays | Successful_Calls | Failed_Calls | Success_Rate | Avg_Response_Time | Avg_Introduction | Avg_Body | Avg_Conclusion | Avg_Grammar |
|--------------|----------------|--------------|------------------|--------------|--------------|-------------------|------------------|----------|----------------|-------------|
| Basic        | v1.5.0         | 40           | 40               | 0            | 100.0%       | 31.86s            | 1.95             | 2.000    | 1.575          | 1.45        |
| Intermediate | v1.5.0         | 40           | 40               | 0            | 100.0%       | 34.86s            | 1.325            | 1.050    | 0.925          | 1.025       |
| Advanced     | v1.5.0         | 40           | 38               | 2            | 95.0%        | 30.70s            | 0.895            | 0.842    | 0.816          | 0.316       |
| Expert       | v1.5.0         | 40           | 39               | 1            | 97.5%        | 37.72s            | 0.154            | 0.103    | 0.026          | 0.615       |


- Basic 으로 채점 시, 전반적으로 높은 점수가 유지되며, 특히 Body는 전원 만점(2점)으로 변별력이 거의 없다.

- Intermediate 으로 채점 시, Grammar, Body, Conclusion 점수가 크게 하락하며 난이도 상승이 반영된다.

- Advanced 으로 채점 시, 모든 항목이 평균 1점 이하로 떨어지며, Grammar는 특히 평균 0.32로 급격히 감소한다.

- Expert 으로 채점 시, Introduction(0.15), Body(0.10), Conclusion(0.03) 점수가 거의 전부 0점에 수렴한다. 이는 Rubric 혹은 Prompt 설계 상 Expert 기준이 지나치게 보수적임을 시사한다.


### 점수 분포

#### BASIC
| 항목           | 0점 | 1점 | 2점 | 평균   |
| ------------ | -- | -- | -- | ---- |
| Grammar      | -  | 22 | 18 | 1.45 |
| Introduction | -  | 2  | 38 | 1.95 |
| Body         | -  | -  | 40 | 2.00 |
| Conclusion   | 6  | 5  | 29 | 1.58 |

#### INTERMEDIATE
| 항목           | 0점 | 1점 | 2점 | 평균   |
| ------------ | -- | -- | -- | ---- |
| Grammar      | 1  | 37 | 2  | 1.03 |
| Introduction | -  | 27 | 13 | 1.33 |
| Body         | -  | 38 | 2  | 1.05 |
| Conclusion   | 5  | 33 | 2  | 0.93 |

#### ADVANCED
| 항목           | 0점 | 1점 | 2점 | 평균   |
| ------------ | -- | -- | -- | ---- |
| Grammar      | 27 | 10 | 1  | 0.32 |
| Introduction | 4  | 34 | -  | 0.89 |
| Body         | 6  | 32 | -  | 0.84 |
| Conclusion   | 7  | 31 | -  | 0.82 |


#### EXPERT
| 항목           | 0점 | 1점 | 2점 | 평균   |
| ------------ | -- | -- | -- | ---- |
| Grammar      | 16 | 22 | 1  | 0.62 |
| Introduction | 33 | 6  | -  | 0.15 |
| Body         | 35 | 4  | -  | 0.10 |
| Conclusion   | 38 | 1  | -  | 0.03 |


### 5.2 항목별 난이도 차이

항목별 점수 분포는 학생 성취도가 아니라 Prompt 기반 체점 로직이 어떻게 작동하는지를 반영한 결과임.  
이를 통해 항목별 난이도 설정과 Prompt 설계 방향성을 파악할 수 있음.

#### Grammar
- Basic: 평균 1.45, 1점과 2점이 균형적으로 분포  
- Intermediate: 평균 1.03, 대부분 1점  
- Advanced: 평균 0.32, 다수 0점  
- Expert: 평균 0.62, 0점과 1점 위주 분포  

→ Grammar 항목은 레벨 상승에 따라 안정적으로 점수가 하락하며, 가장 체계적인 변별력을 제공하는 영역임.  
Prompt가 문법 오류 검출을 단계별 난이도에 맞게 반영하고 있음을 보여주는 사례임.

#### Introduction
- Basic: 평균 1.95, 대부분 2점  
- Intermediate: 평균 1.33, 1점 비중 증가  
- Advanced: 평균 0.89, 주로 1점 분포  
- Expert: 평균 0.15, 대부분 0점  

→ Introduction 항목은 초중급 단계에서는 적절한 분포를 보이지만, Expert 단계에서 급격한 0점 편중 현상이 나타남.  
Prompt가 서론 평가 시 특정 기준 충족 여부에 과도하게 의존하는 경향을 드러내는 지표임.

#### Body
- Basic: 평균 2.00, 전원 만점  
- Intermediate: 평균 1.05, 대부분 1점  
- Advanced: 평균 0.84, 0점·1점 위주 분포  
- Expert: 평균 0.10, 대부분 0점  

→ Body 항목은 Basic 단계에서는 관대한 채점으로 전원 만점을 제공하지만, 상위 레벨에서는 점수가 급격히 감소함.  
Prompt 설계가 본문 평가에서 단순 이분법적 판단에 의존하고 있음을 나타내는 패턴임.

#### Conclusion
- Basic: 평균 1.58, 0~2점이 고르게 분포  
- Intermediate: 평균 0.93, 대부분 1점  
- Advanced: 평균 0.82, 0점·1점 위주 분포  
- Expert: 평균 0.03, 대부분 0점  

→ Conclusion 항목은 모든 레벨에서 가장 높은 변별력을 제공하는 영역임.  
특히 Expert 단계에서는 결론의 형식적 요건 미충족 시 점수가 부여되지 않는 경향을 확인할 수 있음.  
이는 Prompt가 결론 항목에서 강력한 평가 기준을 적용하고 있음을 보여주는 결과임.

---

### 종합 해석
- Grammar 항목은 레벨별 난이도 반영이 가장 성공적으로 이루어진 영역임.  
- Introduction·Body·Conclusion 항목은 초급 단계에서는 합리적인 분포를 보이지만, 상위 레벨로 갈수록 Prompt 기준이 지나치게 가혹하게 작동하는 경향을 확인할 수 있음.  
- 이는 Prompt 설계가 문법 평가에는 안정적으로 작동하나, 구조 평가에서는 편중된 결과를 유발하고 있음을 시사함.  
- 따라서 향후 개선 방향은 문법 기준의 안정성을 유지하면서, 구조 항목에 대해서는 조건 완화 및 세분화를 통해 평가 분포의 균형성을 확보하는 것임.



### 5.3 오류
- submet text에서 json이 받지 못하는 특수 문자 ASCII 가 섞여잇는경우 Fail Calls 발생 

예) \x00, \u0000, \uD800 등


---

## 6. 성능 리포트

* 평균 처리 시간: 9,324 ms
* 요청당 API 비용: $0.0222 (gpt-5-mini 기준)
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


-v1.0.0 : 작동을 위한 기초 prompt
-v1.1.0 : 1차 최적화 진행
-v1.2.0 : gpt 5 mini 에 맞고, 과도한 feedback 방지 
-v1.3.0 : prompt를 가장 경량화 시킴 (체점 결과가 80%가 2점이 방향이 되는 이슈 존재)
-v1.4.0 : v1.2.0을 조금더 경량화 시킴 (채점 결과 score에서 basic에서도 0이 약 70% 로 과한 체점이 이루어짐)
-v1.4.1 : v11.4.0의 문장 순서 수정 및 강제성 주입 (점수 분포는 1.2.0과 유사하나, latency 및 가격 측면에서 grammer 을 제외하고 v1.2.0이 우세)
-v1.5.0 : grammer은 v1.4.1 채용 , 나머지는 v1.2.0 채용

---

## 7. 개선 제안

1. **Prompt 개선**: Expert의 체점 강도 조절. 

2. **Langfuse 활용도**: Langfuse에 대해 study 시간이 부족하여 기능 일부만 사용 및 효율적이지 못한 사용.

1.Langfuse에 대해 처음 사용해보아 이해도 부족, study 시간 부족으로 전반적인 langfuse 을 활용한 버전 관리 미흡 
-> langfuse 의 log -> 다운로드 받아 파싱하여서 prompt 성능 평가진행 등. langfuse 활용도 향상 개선 필요.

3. 물리적 시간 부족으로 대량의 테스트를 통한 최적화 개선 필요.
**prompt**:** 
- prompt version에 대한 평가를 각 rubric_level 당 8회 진행 한 결과 기반으로 테스트 등 통계적 신뢰성이 낮은 상태에서 판단으로 판단의 신뢰성 저하 [유의미한 시간 차이지만, 대표성은 띄지 못함]
- prompt의 micro tuning을 하지 못하여 최적화 및 난의도 조절 미흡

**다양한 파이프라인 시도**
- prompt 에서 1차 intro라 판단한 사항을 body에서는 제외하고 진행, 이후 남은 text 만 conclusion에서 진행과 같이 caching을 통한 방법 시도.
- gpt5 nano 같은 소형 llm을 통해 intro, body, conclusion 분리 후 실행 등의 방식을 진행하지 못함.

3. 후처리 로직 부족
- Scoring, correction, feedback에 관련하여 추가 rephrase, scoring rule의 부재로 0,1,2 int로만 처리: 기획 또는 현업과의 소통을 통해 발전 필요.
- Post-Evaluate에서 레벨 그룹 가중치 및 정합성 검증에서   nlp활용한 score valdiation을 통한 fallback 등 처리방안 추가 
- CEFR, 문장길이를 점수에 활용 등

---

## 8. 결론

## 8. 결론

본 프로젝트를 통해 Rubric 기반의 자동 에세이 평가 서비스를 성공적으로 구현함.  
Prompt Ops를 통한 버전 관리, FastAPI 기반 비동기 처리, Langfuse 추적 통합을 결합하여 안정적이고 확장 가능한 아키텍처를 확보함.  

실험 결과, 레벨 그룹이 상승할수록 점수가 체계적으로 감소하는 패턴을 확인함.  
이는 평가 기준이 난이도별로 차등 적용되고 있음을 보여주는 동시에, Prompt 설계가 문법 평가에서는 안정적으로 작동하지만 구조 평가에서는 다소 편중된 결과를 유발함을 시사함.  

향후 개선 방향은 다음과 같음.  
- Prompt 기준의 세분화 및 가중치 조정을 통한 항목별 균형성 확보  
- Langfuse 로그 기반 성능 분석 강화 및 운영 자동화 확립  
- 후처리 로직 확장을 통한 점수 해석력 제고 및 교육적 활용성 강화  

종합적으로, 본 프로젝트는 에세이 자동 평가 시스템의 기본 골격을 확립.


---
