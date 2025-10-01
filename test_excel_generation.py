#!/usr/bin/env python3
"""Excel 생성 기능만 테스트하는 스크립트"""

import pandas as pd
from eval.excel_creation import EssayBatchEvaluator
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_excel_generation():
    """Excel 생성 기능 테스트"""
    
    # 테스트용 결과 딕셔너리 생성
    test_results = {
        'Basic_v1.5.0': [
            {
                'essay_id': 1,
                'level': 'Basic',
                'version': 'v1.5.0',
                'introduction_score': 85,
                'body_score': 78,
                'conclusion_score': 80,
                'grammar_score': 82,
                'total_score': 81.25
            },
            {
                'essay_id': 2,
                'level': 'Basic',
                'version': 'v1.5.0',
                'introduction_score': 90,
                'body_score': 85,
                'conclusion_score': 88,
                'grammar_score': 87,
                'total_score': 87.5
            }
        ],
        'Intermediate_v1.5.0': [
            {
                'essay_id': 1,
                'level': 'Intermediate',
                'version': 'v1.5.0',
                'introduction_score': 75,
                'body_score': 72,
                'conclusion_score': 78,
                'grammar_score': 76,
                'total_score': 75.25
            }
        ]
    }
    
    # EssayBatchEvaluator 인스턴스 생성 (올바른 버전으로)
    evaluator = EssayBatchEvaluator(['v1.5.0'])
    
    # evaluator의 levels와 prompt_versions를 테스트 데이터와 맞춰줌
    evaluator.levels = ['Basic', 'Intermediate']
    evaluator.prompt_versions = ['v1.5.0']
    
    # Excel 파일 생성 테스트
    output_path = 'test_excel_output.xlsx'
    logger.info(f"🧪 Testing Excel generation with output: {output_path}")
    
    try:
        evaluator.create_excel_report(test_results, output_path)
        logger.info("✅ Excel generation test completed successfully!")
    except Exception as e:
        logger.error(f"❌ Excel generation test failed: {e}")
        raise

if __name__ == "__main__":
    test_excel_generation()