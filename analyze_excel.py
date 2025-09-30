#!/usr/bin/env python3
"""
엑셀 파일 구조 확인 스크립트
"""

import pandas as pd
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_excel_structure(excel_path: str):
    """엑셀 파일의 구조를 분석합니다."""
    try:
        logger.info(f"📊 Analyzing Excel file: {excel_path}")
        
        # 엑셀 파일 읽기
        df = pd.read_excel(excel_path)
        
        logger.info(f"📈 Total rows: {len(df)}")
        logger.info(f"📊 Total columns: {len(df.columns)}")
        logger.info(f"🏷️  Columns: {list(df.columns)}")
        
        # 각 컬럼의 데이터 타입과 샘플 값 확인
        for col in df.columns:
            logger.info(f"\n🔍 Column: {col}")
            logger.info(f"   Data type: {df[col].dtype}")
            logger.info(f"   Non-null values: {df[col].count()}/{len(df)}")
            
            # 첫 3개 값 샘플 표시
            sample_values = df[col].dropna().head(3).tolist()
            logger.info(f"   Sample values: {sample_values}")
            
            # 문자열 컬럼의 경우 평균 길이 확인
            if df[col].dtype == 'object' and df[col].count() > 0:
                avg_length = df[col].dropna().astype(str).str.len().mean()
                logger.info(f"   Average text length: {avg_length:.1f} characters")
        
        # 데이터 미리보기
        logger.info(f"\n📋 Data preview (first 2 rows):")
        for i, row in df.head(2).iterrows():
            logger.info(f"\nRow {i+1}:")
            for col in df.columns:
                value = str(row[col])[:100] + "..." if len(str(row[col])) > 100 else str(row[col])
                logger.info(f"   {col}: {value}")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Error analyzing Excel file: {e}")
        raise

if __name__ == "__main__":
    excel_path = "/home/ycy/work_dir/creverse/data/essay_writing_40_sample.xlsx"
    df = analyze_excel_structure(excel_path)