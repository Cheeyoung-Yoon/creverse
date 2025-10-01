
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
```mermaid
flowchart TD
    A[Client Request] --> B[FastAPI Endpoint]
    B --> C[Evaluation Service]
    C --> D[Azure OpenAI gpt-5-mini]
    C --> E[Rubric Logic]
    E --> F[Score & Feedback]
    C --> G[Langfuse Trace]
    F --> H[API Response]
````

* **FastAPI**: 비동기 API 엔드포인트 제공
* **Evaluation Service**: Rubric 기반 점수/교정/피드백 생성
* **Azure OpenAI**: 모델 응답 생성
* **Langfuse**: Prompt 및 Trace 관리

---

## 3. 데이터 및 평가 기준

* 입력 데이터: 40개 (레벨별 10개씩, Basic/Intermediate/Advanced/Expert)
* 평가 Rubric:

  * 서론 / 본론 / 결론 / 문법 (각 0~2점)
* 레벨 그룹별 기준:

  * Basic: 50~100 단어
  * Intermediate: 100~150 단어
  * Advanced: 150~200 단어
  * Expert: 200+ 단어

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

### 5.1 점수 분포

* Basic 평가 기준 평균 점수: XX점
* Intermediate 평가 기준 평균 점수: XX점
* Advanced 평가 기준 평균 점수: XX점
* Expert 평가 기준 평균 점수: XX점

### 5.2 레벨 그룹별 변화

* 동일 데이터셋을 평가했을 때 레벨 기준이 올라감에 따라 점수가 점차 하락하는지 확인

| 레벨 그룹        | 평균 점수 | 표준편차 |
| ------------ | ----- | ---- |
| Basic        | XX    | XX   |
| Intermediate | XX    | XX   |
| Advanced     | XX    | XX   |
| Expert       | XX    | XX   |

### 5.3 오류/피드백 사례

* 공통 문법 오류 패턴: 시제 일관성, 전치사 누락
* 레벨별 차이: Advanced 이상에서 구조적 전개 부족 → 감점

---

## 6. 성능 리포트

* 처리 속도: 평균 25000 ms / 요청
* 모델 호출 비용: 요청당 $0.015 (추정)
* API 동시 요청 처리 성능: XX RPS

---

## 7. 개선 제안

1. **Prompt 개선**: 레벨별 난이도 가이드 추가
5. **Langfuse 활용도**: Langfuse에 대해 study 시간이 부족하여 기능 일부만 사용 및 효율적이지 못한 사용.

1.Langfuse에 대해 처음 사용해보아 이해도 부족, study 시간 부족으로 전반적인 langfuse 을 활용한 버전 관리 미흡 
-> langfuse 의 log -> 다운로드 받아 파싱하여서 prompt 성능 평가진행 등. langfuse 활용도 향상 개선 필요.

2. 물리적 시간 부족으로 대량의 테스트를 통한 최적화 개선 필요.
**prompt**:** 
- prompt version에 대한 평가를 각 rubric_level 당 1회 진행 한 결과 기반으로 테스트 등 통계적 신뢰성이 낮은 상태에서 판단으로 판단의 신뢰성 저하 [유의미한 시간 차이지만, 대표성은 띄지 못함]
- prompt의 micro tuning을 하지 못하여 저 좋은 최적화 실패

**다양한 파이프라인 시도**
- prompt 에서 1차 intro라 판단한 사항을 body에서는 제외하고 진행, 이후 남은 text 만 conclusion에서 진행과 같이 caching을 통한 방법 시도.
- gpt5 nano 같은 소형 llm을 통해 intro, body, conclusion 분리 후 실행 등의 방식을 진행하지 못함.

3. 후처리 로직 부족
- Scoring, correction, feedback에 관련하여 추가 rephrase, scoring rule의 부재로 0,1,2 int로만 처리: 기획 또는 현업과의 소통을 통해 발전 필요.
- Post-Evaluate에서 레벨 그룹 가중치 및 정합성 검증에서   nlp활용한 score valdiation을 통한 fallback 등 처리방안 추가 
- CEFR, 문장길이를 점수에 활용 등

---

## 8. 결론

* Rubric 기반 자동 평가 서비스 구현 완료
* 레벨 그룹별 점수 차이를 확인
* Prompt Ops + FastAPI + Langfuse 기반 구조로 확장성 확보

---
