import re
from typing import Dict, Any

LEVEL_WORD_REQUIREMENTS = {
    "Basic": {"min_words": 50, "max_words": 100},
    "Intermediate": {"min_words": 100, "max_words": 150},
    "Advanced": {"min_words": 150, "max_words": 200},
    "Expert": {"min_words": 200, "max_words": float('inf')}
}


def define_english_check(text: str) -> bool:
    '''
    간단한 영어 텍스트 판별 함수: ASCII 문자 비율이 80% 이상인 경우 영어로 간주
    필요 시, 더 정교한 방식 or llm 활용 으로 확장 
    '''
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text) if text else 0
    return ascii_ratio > 0.8

def pre_process_essay(essay_text: str, topic_prompt: str, level_group: str):
    
    word_count = len(re.findall(r'\b\w+\b', essay_text))

    reqs = LEVEL_WORD_REQUIREMENTS.get(level_group, LEVEL_WORD_REQUIREMENTS["Basic"])
    meets_length_req = reqs["min_words"] <= word_count <= reqs["max_words"]

    
    is_english = define_english_check(essay_text)
    
    return {
        "word_count": word_count,
        "meets_length_req": meets_length_req,
        "is_english": is_english
    }
