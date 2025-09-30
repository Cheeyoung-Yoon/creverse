#!/usr/bin/env python3
"""
전체 40개 에세이 배치 처리 실행
"""

from excel_creation import EssayBatchEvaluator
import pandas as pd
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_full_batch():
    """전체 40개 에세이 배치 처리"""
    try:
        logger.info("🚀 Starting FULL batch evaluation: 40 essays × 4 levels = 160 API calls")
        logger.info("⏱️  Estimated time: ~3-4 hours (assuming 1 min per call)")
        
        # 평가기 초기화
        evaluator = EssayBatchEvaluator()
        
        # 엑셀 데이터 로드
        df = evaluator.load_sample_data("/home/ycy/work_dir/creverse/data/essay_writing_40_sample.xlsx")
        
        # 모든 레벨로 평가
        results = evaluator.process_all_essays(df)
        
        # 결과를 엑셀로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"essay_evaluation_results_{timestamp}.xlsx"
        
        logger.info(f"💾 Saving results to {output_file}")
        evaluator.save_to_excel(results, output_file)
        
        # 통계 요약
        logger.info("📊 Evaluation Summary:")
        for level, level_results in results.items():
            successful = len([r for r in level_results if 'error' not in r])
            failed = len([r for r in level_results if 'error' in r])
            logger.info(f"   {level}: {successful} successful, {failed} failed")
        
        logger.info("✅ Full batch evaluation completed successfully!")
        logger.info(f"📁 Results saved to: {output_file}")
        
        return output_file
        
    except KeyboardInterrupt:
        logger.warning("⚠️ Batch evaluation interrupted by user")
        return None
    except Exception as e:
        logger.error(f"💥 Full batch evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def run_partial_batch(max_essays=5):
    """부분적 배치 처리 (테스트용)"""
    try:
        logger.info(f"🧪 Starting PARTIAL batch evaluation: {max_essays} essays × 4 levels = {max_essays * 4} API calls")
        
        # 평가기 초기화
        evaluator = EssayBatchEvaluator()
        
        # 엑셀 데이터 로드 (일부만)
        df = evaluator.load_sample_data("/home/ycy/work_dir/creverse/data/essay_writing_40_sample.xlsx")
        test_df = df.head(max_essays)
        
        # 모든 레벨로 평가
        results = evaluator.process_all_essays(test_df)
        
        # 결과를 엑셀로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"essay_evaluation_partial_{max_essays}essays_{timestamp}.xlsx"
        
        logger.info(f"💾 Saving partial results to {output_file}")
        evaluator.save_to_excel(results, output_file)
        
        logger.info("✅ Partial batch evaluation completed!")
        logger.info(f"📁 Results saved to: {output_file}")
        
        return output_file
        
    except Exception as e:
        logger.error(f"💥 Partial batch evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "full":
        # 전체 실행
        result_file = run_full_batch()
    elif len(sys.argv) > 1 and sys.argv[1].startswith("partial"):
        # 부분 실행
        max_essays = 5
        if "=" in sys.argv[1]:
            max_essays = int(sys.argv[1].split("=")[1])
        result_file = run_partial_batch(max_essays)
    else:
        # 기본: 5개 에세이만 테스트
        logger.info("📋 Usage:")
        logger.info("   python run_batch.py full          # All 40 essays (160 API calls)")
        logger.info("   python run_batch.py partial=10    # First 10 essays (40 API calls)")
        logger.info("   python run_batch.py               # Default: 5 essays (20 API calls)")
        logger.info("")
        logger.info("🧪 Running default partial batch (5 essays)...")
        result_file = run_partial_batch(5)
    
    if result_file:
        logger.info(f"🎉 Batch processing completed! Output: {result_file}")
    else:
        logger.error("❌ Batch processing failed!")