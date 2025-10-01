# JSONL robust parser for notebooks (no argparse)
# - JSONL 실패 시: concatenated JSON, JSON array 형태까지 폴백
# - 디버깅 출력 포함: 파일 존재/크기/라인 수/파싱 결과
# - 요청 컬럼: version, promtlatency, input_cost_usd, output_cost_usd, total_cost_usd, prompt_key
# %%
import os, json
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# >>> 여기를 네 파일 경로로 바꾸세요 <<<
PATH = "/home/cyyoon/test_area/ai_text_classification/creverse2/eval/langfuse_eval/inital_all_ver_langfuse_log.jsonl"
OUT_CSV = os.path.splitext(PATH)[0] + ".parsed.csv"

# >>> 원하는 시점 이후만 읽기 (없으면 None)
TS_AFTER = "2025-10-01T02:46:17.593Z"  # 또는 None



from datetime import datetime

def _get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for part in path.split('.'):
        if not isinstance(cur, dict):
            return default
        if part not in cur:
            return default
        cur = cur[part]
    return cur if cur is not None else default

def _prefer_costs(obj: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    # metadata first
    meta_in = _get(obj, 'metadata.input_cost_usd')
    meta_out = _get(obj, 'metadata.output_cost_usd')
    meta_total = _get(obj, 'metadata.cost_usd')
    if any(v is not None for v in (meta_in, meta_out, meta_total)):
        return meta_in, meta_out, meta_total

    # usage camelCase fallback
    u_in = _get(obj, 'usage.inputCost')
    u_out = _get(obj, 'usage.outputCost')
    u_total = _get(obj, 'usage.totalCost')
    if any(v is not None for v in (u_in, u_out, u_total)):
        return u_in, u_out, u_total

    # output.usage fallback
    u2_in = _get(obj, 'output.usage.input_cost_usd')
    u2_out = _get(obj, 'output.usage.output_cost_usd')
    u2_total = _get(obj, 'output.usage.total_cost_usd')
    if any(v is not None for v in (u2_in, u2_out, u2_total)):
        return u2_in, u2_out, u2_total

    return None, None, None

def _prefer_latency_seconds(obj: Dict[str, Any]) -> Optional[float]:
    # seconds preferred
    for key in ('latency', 'metadata.latency'):
        v = _get(obj, key)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    # ms variants -> seconds
    for key in ('latency_ms', 'requestLatencyMs', 'latencyMs', 'metadata.latency_ms'):
        v = _get(obj, key)
        if v is not None:
            try:
                return float(v) / 1000.0
            except Exception:
                pass
    return None

def _extract_row(obj: Dict[str, Any]) -> Dict[str, Any]:
    version = _get(obj, 'metadata.prompt_version')
    promtlatency = _prefer_latency_seconds(obj)
    in_cost, out_cost, total_cost = _prefer_costs(obj)
    prompt_key = _get(obj, 'metadata.prompt_key') or _get(obj, 'input.prompt_key')

    return {
        'version': version,
        'promtlatency': promtlatency,
        'input_cost_usd': in_cost,
        'output_cost_usd': out_cost,
        'total_cost_usd': total_cost,
        'prompt_key': prompt_key,
        # 참고 필드
        'id': obj.get('id'),
        'name': obj.get('name'),
        'timestamp': obj.get('timestamp')
    }

from datetime import datetime

def _read_jsonl(path: str, ts_after: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Tuple[int, str, str]], int]:
    """
    JSONL을 라인 단위로 읽되, ts_after가 주어지면 timestamp가 cutoff보다
    빠른 레코드는 즉시 스킵한다. (형식 불량 timestamp도 스킵)
    반환: (objs, bad_lines, skipped_count)
    """
    objs, bad = [], []
    skipped = 0

    cutoff = None
    if ts_after:
        try:
            cutoff = datetime.fromisoformat(ts_after)
        except Exception as e:
            print(f"[warn] 잘못된 --after 값: {ts_after} ({e}). 필터 미적용.")
            cutoff = None

    with open(path, 'r', encoding='utf-8-sig') as f:
        for idx, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError as e:
                bad.append((idx, s[:200], str(e)))
                continue

            if cutoff is not None:
                ts = obj.get("timestamp")
                if not ts:
                    skipped += 1
                    continue
                try:
                    ts_dt = datetime.fromisoformat(ts)
                except Exception:
                    # timestamp 형식 불량 → 스킵
                    skipped += 1
                    continue

                if ts_dt < cutoff:
                    skipped += 1
                    continue

            objs.append(obj)

    return objs, bad, skipped


def _read_concatenated(path: str) -> List[Dict[str, Any]]:
    """여러 JSON이 공백으로 이어진 형태 파싱."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        blob = f.read()
    dec = json.JSONDecoder()
    i, n = 0, len(blob)
    objs = []
    while i < n:
        while i < n and blob[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, j = dec.raw_decode(blob, idx=i)
        except json.JSONDecodeError:
            nxt = blob.find('{', i + 1)
            if nxt == -1:
                break
            i = nxt
            continue
        objs.append(obj)
        i = j
    return objs

def _read_json_array(path: str) -> List[Dict[str, Any]]:
    """파일 전체가 하나의 JSON 배열인 경우."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return []

# ============= 실행부 =============

size = os.path.getsize(PATH)
line_count = sum(1 for _ in open(PATH, 'r', encoding='utf-8-sig'))
print(f"[info] path={PATH}")
print(f"[info] size_bytes={size}, line_count={line_count}")

# 1) JSONL 시도
# 1) JSONL 시도 (필터 적용)
objs, bad_lines, skipped = _read_jsonl(PATH, ts_after=TS_AFTER)
print(f"[info] jsonl parsed(kept)={len(objs)} rows, skipped={skipped}, bad_lines={len(bad_lines)}")

# 2) 폴백: concatenated JSON
if len(objs) == 0:
    objs = _read_concatenated(PATH)
    print(f"[info] concatenated parsed={len(objs)} rows")

# 3) 폴백: 단일 JSON array
if len(objs) == 0:
    try:
        objs = _read_json_array(PATH)
        print(f"[info] json array parsed={len(objs)} rows")
    except Exception as e:
        print(f"[warn] json array parse failed: {e}")

# 실패 라인 일부 미리보기
if bad_lines:
    print("[debug] first 3 bad lines preview:")
    for i, (ln, snippet, err) in enumerate(bad_lines[:3], 1):
        print(f"  - line {ln}: {snippet} ... :: {err}")

# 추출 -> DF
records = [_extract_row(o) for o in objs]
cols = [
    'version','promtlatency','input_cost_usd','output_cost_usd','total_cost_usd','prompt_key',
    'id','name','timestamp'
]
df = pd.DataFrame(records, columns=cols)

print(f"[info] extracted rows={len(df)}")
if len(df) == 0:
    print("[hint] 컬럼 경로가 다를 수 있어요. metadata.prompt_key / metadata.prompt_version / metadata.cost_usd 등이 없는지 확인 필요.")

# 저장 & 미리보기
df.to_csv(OUT_CSV, index=False)
print(f"[info] saved csv -> {OUT_CSV}")


# %%
df.groupby(['prompt_key', 'version']).agg(
    count=('total_cost_usd', 'count'),
    total_cost_usd=('total_cost_usd', 'sum'),
    avg_cost_usd=('total_cost_usd', 'mean'),
    total_input_cost_usd=('input_cost_usd', 'sum'),
    total_output_cost_usd=('output_cost_usd', 'sum'),
    avg_latency_seconds=('promtlatency', 'mean'),
).reset_index().sort_values(['prompt_key', 'total_cost_usd', 'avg_latency_seconds'])
# %%
## 결과 v1.2.0 의 가격 및 속도 측면에서 가장 우위를 보임.
## v1.4.1 은 grammar 의 성능이 가장 좋음.
## 다른 버전은 4회의 반복이여도, 유의미한 차이를 보여 주어 v1.2.0, v1.4.1 두가지에 대하여 추가 테스트 진행.

# 이에 따라 전체 테스트 진행은 v1.2.0, v1.4.1 두 버전으로 수행.
# 상세 평가를 위한 return h-eval


import json
import pandas as pd
from datetime import datetime, timezone

# ===== 설정 =====
JSONL_PATH = "/home/cyyoon/test_area/ai_text_classification/creverse2/eval/langfuse_eval/inital_all_ver_langfuse_log.jsonl" # 업로드된 파일 경로
TIME_FROM = "2025-10-01T02:46:17.593Z"   # 이 시각 이후만 사용

# ===== 유틸 =====
def parse_iso8601(s: str) -> datetime:
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def first_nonzero_or_first(*vals):
    # 숫자이면 0이 아닌 첫 값, 전부 0/None이면 첫 non-None
    for v in vals:
        if isinstance(v, (int, float)) and v != 0:
            return v
    for v in vals:
        if v is not None:
            return v
    return None

def extract_prompt_tokens(rec: dict):
    # 다양한 위치/키 대비
    u_top = rec.get("usage", {}) if isinstance(rec.get("usage"), dict) else {}
    u_out = rec.get("output", {}).get("usage", {}) if isinstance(rec.get("output", {}), dict) else {}

    return first_nonzero_or_first(
        u_out.get("prompt_tokens"),
        u_out.get("promptTokens"),
        u_top.get("prompt_tokens"),
        u_top.get("promptTokens"),
    )

def extract_cost_usd(meta: dict):
    if not isinstance(meta, dict):
        return None
    if meta.get("cost_usd") is not None:
        return meta.get("cost_usd")
    ic = meta.get("input_cost_usd")
    oc = meta.get("output_cost_usd")
    if isinstance(ic, (int, float)) or isinstance(oc, (int, float)):
        return (ic or 0) + (oc or 0)
    return None

# ===== 로드 & 필터 =====
cutoff = parse_iso8601(TIME_FROM)
rows = []

with open(JSONL_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            # 불완전/깨진 라인은 스킵
            continue

        # timestamp 필터 (최우선)
        ts = parse_iso8601(rec.get("timestamp"))
        if cutoff and ts and ts <= cutoff:
            continue

        # 공통 필드
        rid = rec.get("id")
        name = rec.get("name")
        latency = rec.get("latency")

        meta = rec.get("metadata", {}) if isinstance(rec.get("metadata"), dict) else {}
        prompt_key = meta.get("prompt_key")
        prompt_version = meta.get("prompt_version")
        cost_usd = extract_cost_usd(meta)

        # output.content 구조 안전 파싱
        out = rec.get("output", {}) if isinstance(rec.get("output"), dict) else {}
        content = out.get("content", {}) if isinstance(out.get("content"), dict) else {}

        rubric_item = content.get("rubric_item")
        score = content.get("score")

        corrections = content.get("corrections")
        if not isinstance(corrections, list):
            corrections = []

        # usage: prompt_tokens
        prompt_tokens = extract_prompt_tokens(rec)

        # correction이 없으면 빈 행으로라도 기록(점수/메타 유지)
        if not corrections:
            rows.append({
                "rubric_item": rubric_item,
                "score": score,
                "highlight": None,
                "issue": None,
                "correction": None,
                "prompt_tokens": prompt_tokens,
                "prompt_key": prompt_key,
                "prompt_version": prompt_version,
                "cost_usd": cost_usd,
                "latency": latency,
            })
        else:
            for c in corrections:
                rows.append({
                    "score": score,
                    "highlight": c.get("highlight") if isinstance(c, dict) else None,
                    "issue": c.get("issue") if isinstance(c, dict) else None,
                    "correction": c.get("correction") if isinstance(c, dict) else None,
                    "prompt_tokens": prompt_tokens,
                    "prompt_key": prompt_key,
                    "prompt_version": prompt_version,
                    "cost_usd": cost_usd,
                    "latency": latency,
                })

# ===== DataFrame =====
df = pd.DataFrame(rows)

# %%
part = df.sort_values(['prompt_key', 'latency', 'cost_usd'])
part = part[part['prompt_key'] == 'introduction'].groupby(['prompt_version', 'score']).agg(
    count=('score', 'count'),
    avg_latency_seconds=('latency', 'mean'),
    total_cost_usd=('cost_usd', 'sum'),
    avg_cost_usd=('cost_usd', 'mean'),
    total_prompt_tokens=('prompt_tokens', 'sum'),
    avg_prompt_tokens=('prompt_tokens', 'mean'),
).reset_index().sort_values(['total_cost_usd', 'avg_latency_seconds'])
part 
# %%
# grammar : 1.4.1
# intro :  1.2
# body : 1.1
# conclusion : 1.3

