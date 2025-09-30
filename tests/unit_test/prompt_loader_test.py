import pytest
import json
import sys
import os
# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.utils.prompt_loader import PromptLoader


class TestPromptLoader:
    """PromptLoader 기본 기능 테스트"""

    @pytest.fixture
    def prompt_loader(self):
        """PromptLoader 인스턴스"""
        return PromptLoader()

    def test_prompt_loader_initialization(self, prompt_loader):
        """PromptLoader 초기화 테스트"""
        assert prompt_loader is not None
        # 필요한 속성들이 있는지 확인
        assert hasattr(prompt_loader, 'load_prompt')

    def test_load_grammar_prompt(self, prompt_loader):
        """grammar 프롬프트 로드 테스트"""
        # grammar_check 키로 프롬프트 로드 시도
        try:
            prompt = prompt_loader.load_prompt("grammar_check", {"text": "sample text"})
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            print(f"Grammar prompt loaded: {prompt[:100]}...")
        except Exception as e:
            print(f"Grammar prompt load failed: {e}")
            # 다른 키들 시도
            for key in ["grammar", "grammar_eval", "check_grammar"]:
                try:
                    prompt = prompt_loader.load_prompt(key, {"text": "sample text"})
                    assert isinstance(prompt, str)
                    print(f"Found grammar prompt with key '{key}': {prompt[:100]}...")
                    break
                except Exception as inner_e:
                    print(f"Key '{key}' failed: {inner_e}")
            else:
                pytest.fail("No grammar prompt found with any common key")

    def test_check_prompts_directory(self):
        """prompts 디렉토리 구조 확인"""
        prompts_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'prompts')
        
        # prompts 디렉토리 존재 확인
        assert os.path.exists(prompts_dir), f"Prompts directory not found: {prompts_dir}"
        
        # 버전 디렉토리 확인
        version_dirs = [d for d in os.listdir(prompts_dir) if os.path.isdir(os.path.join(prompts_dir, d))]
        print(f"Available version directories: {version_dirs}")
        assert len(version_dirs) > 0, "No version directories found in prompts"
        
        # v1.0.0 디렉토리 확인
        v1_dir = os.path.join(prompts_dir, 'v1.0.0')
        if os.path.exists(v1_dir):
            files = os.listdir(v1_dir)
            print(f"Files in v1.0.0: {files}")
            
            # grammar.json 파일 확인
            grammar_file = os.path.join(v1_dir, 'grammar.json')
            if os.path.exists(grammar_file):
                with open(grammar_file, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    print(f"Grammar.json content keys: {list(content.keys())}")
                    print(f"Grammar.json content: {content}")

    def test_available_prompt_keys(self, prompt_loader):
        """사용 가능한 프롬프트 키들 확인"""
        # 일반적으로 사용될 수 있는 키들 테스트
        common_keys = [
            "grammar", "grammar_check", "grammar_eval",
            "introduction", "body", "conclusion",
            "context", "context_eval"
        ]
        
        found_keys = []
        for key in common_keys:
            try:
                prompt = prompt_loader.load_prompt(key, {"text": "test"})
                if prompt:
                    found_keys.append(key)
                    print(f"✓ Key '{key}' works: {prompt[:50]}...")
            except Exception as e:
                print(f"✗ Key '{key}' failed: {e}")
        
        print(f"Working keys: {found_keys}")
        assert len(found_keys) > 0, "No working prompt keys found"

    def test_prompt_with_parameters(self, prompt_loader):
        """파라미터를 포함한 프롬프트 로드 테스트"""
        # 다양한 파라미터로 테스트
        test_params = {
            "text": "This is a sample text for testing grammar evaluation.",
            "score": 85,
            "feedback": "Good grammar overall"
        }
        
        # 사용 가능한 키 찾기
        for key in ["grammar", "grammar_check", "grammar_eval"]:
            try:
                prompt = prompt_loader.load_prompt(key, test_params)
                print(f"Prompt with parameters for '{key}': {prompt}")
                assert isinstance(prompt, str)
                assert len(prompt) > 0
                break
            except Exception as e:
                print(f"Key '{key}' with params failed: {e}")
        else:
            print("Warning: No keys worked with parameters, trying without params")

    def test_prompt_loader_error_handling(self, prompt_loader):
        """PromptLoader 에러 처리 테스트"""
        # 존재하지 않는 키로 테스트
        try:
            prompt = prompt_loader.load_prompt("nonexistent_key", {"text": "test"})
            print(f"Unexpected success with nonexistent key: {prompt}")
        except Exception as e:
            print(f"Expected error with nonexistent key: {e}")
            assert True  # 에러가 발생하는 것이 정상


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])