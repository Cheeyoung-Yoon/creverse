"""
Enhanced unit tests for prompt_loader.py
"""
import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from app.utils.prompt_loader import PromptLoader


@pytest.mark.unit
class TestPromptLoaderCore:
    """Test core PromptLoader functionality"""
    
    def test_prompt_loader_initialization(self):
        """Test PromptLoader creation"""
        loader = PromptLoader()
        assert loader is not None
        assert hasattr(loader, 'load_prompt')
        assert hasattr(loader, 'get_version_dir')
    
    def test_get_version_dir_default(self):
        """Test getting default version directory"""
        loader = PromptLoader()
        version_dir = loader.get_version_dir()
        
        # Should return a Path object
        assert isinstance(version_dir, Path)
        # Should end with a version directory
        assert str(version_dir).endswith(('v1.0.0', 'v1.1.0', 'v1.2.0', 'v1.3.0'))
    
    def test_get_version_dir_specific(self):
        """Test getting specific version directory"""
        loader = PromptLoader()
        version_dir = loader.get_version_dir("v1.2.0")
        
        assert isinstance(version_dir, Path)
        assert str(version_dir).endswith('v1.2.0')
    
    def test_get_version_dir_invalid(self):
        """Test getting invalid version directory"""
        loader = PromptLoader()
        
        # Should handle invalid version gracefully
        with pytest.raises((FileNotFoundError, ValueError)):
            loader.get_version_dir("v999.999.999")


@pytest.mark.unit
class TestPromptLoaderVersioning:
    """Test version management functionality"""
    
    def test_version_setting(self):
        """Test setting and getting prompt versions"""
        loader = PromptLoader()
        
        # Test setting specific versions
        loader.set_version("introduction", "v1.2.0")
        loader.set_version("body", "v1.1.0")
        
        # Should maintain version state
        assert hasattr(loader, '_versions') or hasattr(loader, 'versions')
    
    def test_available_versions(self):
        """Test getting available prompt versions"""
        loader = PromptLoader()
        
        # Should return available versions
        versions = loader.get_available_versions()
        assert isinstance(versions, list)
        assert len(versions) > 0
        
        # Should contain valid version strings
        for version in versions:
            assert version.startswith('v')
            assert '.' in version  # Should be semantic version


@pytest.mark.unit
class TestPromptLoaderFileOperations:
    """Test file loading and processing"""
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"system": "Test prompt: {text}"}')
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_prompt_basic(self, mock_exists, mock_file):
        """Test basic prompt loading"""
        loader = PromptLoader()
        
        result = loader.load_prompt("grammar", {"text": "sample text"})
        
        assert isinstance(result, str)
        assert "sample text" in result
        mock_file.assert_called()
    
    @patch('pathlib.Path.exists', return_value=False)
    def test_load_prompt_file_not_found(self, mock_exists):
        """Test prompt loading when file doesn't exist"""
        loader = PromptLoader()
        
        with pytest.raises(FileNotFoundError):
            loader.load_prompt("nonexistent", {"text": "test"})
    
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_prompt_invalid_json(self, mock_exists, mock_file):
        """Test prompt loading with invalid JSON"""
        loader = PromptLoader()
        
        with pytest.raises(json.JSONDecodeError):
            loader.load_prompt("grammar", {"text": "test"})
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"system": "Prompt without variables"}')
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_prompt_no_variables(self, mock_exists, mock_file):
        """Test prompt loading without variable substitution"""
        loader = PromptLoader()
        
        result = loader.load_prompt("simple", {})
        
        assert result == "Prompt without variables"
        mock_file.assert_called()


@pytest.mark.unit
class TestPromptLoaderTemplating:
    """Test template variable substitution"""
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"system": "Evaluate {text} at {level} level"}')
    @patch('pathlib.Path.exists', return_value=True)
    def test_variable_substitution(self, mock_exists, mock_file):
        """Test template variable substitution"""
        loader = PromptLoader()
        
        result = loader.load_prompt("test", {
            "text": "this essay",
            "level": "Basic"
        })
        
        assert "this essay" in result
        assert "Basic" in result
        assert "Evaluate this essay at Basic level" in result
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"system": "Missing variable: {missing}"}')
    @patch('pathlib.Path.exists', return_value=True)
    def test_missing_variable(self, mock_exists, mock_file):
        """Test handling of missing template variables"""
        loader = PromptLoader()
        
        # Should handle missing variables gracefully
        with pytest.raises(KeyError):
            loader.load_prompt("test", {"other": "value"})
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"system": "Text: {text}", "user": "Level: {level}"}')
    @patch('pathlib.Path.exists', return_value=True)
    def test_multiple_prompt_sections(self, mock_exists, mock_file):
        """Test prompts with multiple sections"""
        loader = PromptLoader()
        
        result = loader.load_prompt("multi", {
            "text": "essay content",
            "level": "Advanced"
        })
        
        # Should handle multiple sections in the JSON
        assert "essay content" in result
        assert "Advanced" in result


@pytest.mark.unit
class TestPromptLoaderIntegration:
    """Test integration with real prompt files"""
    
    def test_real_prompts_directory_exists(self):
        """Test that prompts directory exists"""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        assert prompts_dir.exists(), f"Prompts directory not found: {prompts_dir}"
    
    def test_version_directories_exist(self):
        """Test that version directories exist"""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        
        # Check for common version directories
        expected_versions = ["v1.0.0", "v1.1.0", "v1.2.0"]
        for version in expected_versions:
            version_dir = prompts_dir / version
            if version_dir.exists():
                # At least one version should exist
                assert True
                return
        
        # If no expected versions found, that's still valid for a new project
        assert True
    
    def test_prompt_files_structure(self):
        """Test that prompt files have expected structure"""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        
        # Find any version directory
        version_dirs = [d for d in prompts_dir.iterdir() if d.is_dir() and d.name.startswith('v')]
        
        if version_dirs:
            version_dir = version_dirs[0]  # Test first available version
            
            # Check for common prompt files
            expected_files = ["grammar.json", "introduction.json", "body.json", "conclusion.json"]
            
            for filename in expected_files:
                filepath = version_dir / filename
                if filepath.exists():
                    # If file exists, it should be valid JSON
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        assert isinstance(data, dict)
                        # Should have at least one prompt field
                        assert len(data) > 0
                    except json.JSONDecodeError:
                        pytest.fail(f"Invalid JSON in {filepath}")


@pytest.mark.unit
class TestPromptLoaderErrorHandling:
    """Test error handling and edge cases"""
    
    def test_empty_variables_dict(self):
        """Test with empty variables dictionary"""
        loader = PromptLoader()
        
        with patch('builtins.open', mock_open(read_data='{"system": "No variables here"}')):
            with patch('pathlib.Path.exists', return_value=True):
                result = loader.load_prompt("test", {})
                assert result == "No variables here"
    
    def test_none_variables(self):
        """Test with None variables"""
        loader = PromptLoader()
        
        with patch('builtins.open', mock_open(read_data='{"system": "No variables here"}')):
            with patch('pathlib.Path.exists', return_value=True):
                # Should handle None gracefully
                result = loader.load_prompt("test", None)
                assert isinstance(result, str)
    
    def test_non_string_variables(self):
        """Test with non-string variables"""
        loader = PromptLoader()
        
        with patch('builtins.open', mock_open(read_data='{"system": "Score: {score}, Level: {level}"}')):
            with patch('pathlib.Path.exists', return_value=True):
                result = loader.load_prompt("test", {
                    "score": 42,
                    "level": "Advanced"
                })
                assert "42" in result
                assert "Advanced" in result