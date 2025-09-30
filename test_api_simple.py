#!/usr/bin/env python3
"""
간단한 API 테스트 스크립트
"""

import requests
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_api_connection():
    """API 서버 연결 테스트"""
    try:
        # 간단한 테스트 에세이
        test_payload = {
            "level_group": "Basic",
            "topic_prompt": "Write about your favorite fruit.",
            "submit_text": "I like apples. They are red and sweet. I eat them every day."
        }
        
        logger.info("🔍 Testing API connection...")
        response = requests.post(
            "http://localhost:8000/v1/essay-eval",
            json=test_payload,
            timeout=120  # 2분으로 늘림
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info("✅ API connection successful!")
            logger.info(f"📊 Response type: {type(result)}")
            logger.info(f"📄 Full response: {result}")
            
            return True
        else:
            logger.error(f"❌ API returned status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error("🔌 Connection error - API server is not running")
        logger.info("💡 Start the server with: python main.py")
        return False
    except Exception as e:
        logger.error(f"💥 Test failed: {e}")
        return False

def test_with_real_data():
    """실제 엑셀 데이터로 테스트"""
    try:
        # 엑셀 파일에서 첫 번째 에세이 로드
        df = pd.read_excel("/home/ycy/work_dir/creverse/data/essay_writing_40_sample.xlsx")
        df = df.dropna(subset=['submit_text'])
        
        if len(df) == 0:
            logger.error("❌ No valid essays found in Excel file")
            return False
            
        # 첫 번째 에세이 테스트
        first_essay = df.iloc[0]
        essay_text = first_essay['submit_text']
        
        logger.info(f"🧪 Testing with real essay data...")
        logger.info(f"📝 Essay ID: {first_essay['essay_id']}")
        logger.info(f"📋 Original level: {first_essay['rubric_level']}")
        logger.info(f"📏 Essay length: {len(essay_text)} characters")
        logger.info(f"📄 Preview: {essay_text[:100]}...")
        
        test_payload = {
            "level_group": "Basic",
            "topic_prompt": first_essay['topic_prompt'],
            "submit_text": essay_text
        }
        
        response = requests.post(
            "http://localhost:8000/v1/essay-eval",
            json=test_payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info("✅ Real data test successful!")
            
            for section in result:
                section_name = section.get("rubric_item", "unknown")
                score = section.get("score", 0)
                feedback = section.get("feedback", "")[:100]
                corrections = len(section.get("corrections", []))
                logger.info(f"   {section_name}: score={score}, corrections={corrections}")
                logger.debug(f"      feedback: {feedback}...")
            
            return True
        else:
            logger.error(f"❌ Real data test failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"💥 Real data test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting API tests...")
    
    # 기본 연결 테스트
    if test_api_connection():
        # 실제 데이터 테스트
        test_with_real_data()
    else:
        logger.error("❌ API connection failed - cannot proceed with data test")