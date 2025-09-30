#!/usr/bin/env python3
"""
단일 에세이 배치 처리 테스트
"""

from excel_creation import EssayBatchEvaluator
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_single_essay():
    """단일 에세이로 배치 처리 테스트"""
    try:
        # 평가기 초기화
        evaluator = EssayBatchEvaluator()
        
        # 엑셀 데이터 로드
        df = evaluator.load_sample_data("/home/ycy/work_dir/creverse/data/essay_writing_40_sample.xlsx")
        
        # 첫 번째 에세이만 테스트
        test_df = df.head(1)
        logger.info(f"🧪 Testing with 1 essay for all 4 levels")
        
        # 모든 레벨로 평가
        results = evaluator.process_all_essays(test_df)
        
        # 결과 확인
        for level, level_results in results.items():
            logger.info(f"\n📊 Level: {level}")
            if level_results:
                result = level_results[0]
                logger.info(f"   Essay ID: {result['essay_id']}")
                logger.info(f"   Total Score: {result.get('total_score', 'N/A')}")
                logger.info(f"   Grammar Score: {result.get('grammar_score', 'N/A')}")
                logger.info(f"   Introduction Score: {result.get('introduction_score', 'N/A')}")
                logger.info(f"   Body Score: {result.get('body_score', 'N/A')}")
                logger.info(f"   Conclusion Score: {result.get('conclusion_score', 'N/A')}")
                logger.info(f"   Processing Time: {result.get('total_processing_time', 'N/A')}s")
                if 'error' in result:
                    logger.error(f"   Error: {result['error']}")
            else:
                logger.warning(f"   No results for {level}")
        
        # 간단한 CSV 저장
        if any(results.values()):
            logger.info("💾 Saving test results to CSV...")
            for level, level_results in results.items():
                if level_results:
                    df_result = pd.DataFrame(level_results)
                    df_result.to_csv(f"test_result_{level.lower()}.csv", index=False)
                    logger.info(f"   Saved: test_result_{level.lower()}.csv")
        
        return True
        
    except Exception as e:
        logger.error(f"💥 Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_single_essay()