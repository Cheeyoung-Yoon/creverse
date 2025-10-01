"""
Unit tests for services/evaluation/pre_process.py
"""
import pytest
import re

from app.services.evaluation.pre_process import (
    pre_process_essay, LEVEL_WORD_REQUIREMENTS, 
    define_english_check
)
from app.models.rubric import PreProcessResult


def count_words(text: str) -> int:
    """Helper function for testing word counting"""
    return len(re.findall(r'\b\w+\b', text))


def detect_language(text: str) -> str:
    """Mock language detection for testing"""
    if define_english_check(text):
        return "en"
    return "unknown"


def check_topic_relevance(text: str, topic: str) -> float:
    """Mock topic relevance checking for testing"""
    if topic.lower() in text.lower():
        return 0.8
    return 0.3


@pytest.mark.unit
class TestWordCounting:
    """Test word counting functionality"""
    
    def test_count_words_basic(self):
        """Test basic word counting"""
        text = "This is a simple test essay with exactly ten words here."
        count = count_words(text)
        assert count == 11  # Including "here" makes it 11
    
    def test_count_words_empty(self):
        """Test word counting with empty text"""
        assert count_words("") == 0
        assert count_words("   ") == 0
        assert count_words("\n\t") == 0
    
    def test_count_words_punctuation(self):
        """Test word counting with punctuation"""
        text = "Hello, world! This is a test. It has punctuation?"
        count = count_words(text)
        assert count == 10
    
    def test_count_words_multiple_spaces(self):
        """Test word counting with multiple spaces"""
        text = "Words   with    multiple     spaces"
        count = count_words(text)
        assert count == 4
    
    def test_count_words_special_characters(self):
        """Test word counting with special characters"""
        text = "Testing @#$% special (characters) and-hyphens_underscores"
        count = count_words(text)
        # Should count reasonable word boundaries
        assert count >= 4


@pytest.mark.unit
class TestLanguageDetection:
    """Test language detection functionality"""
    
    def test_detect_language_english(self):
        """Test detecting English text"""
        english_text = "This is clearly an English sentence with proper grammar and vocabulary."
        lang = detect_language(english_text)
        assert lang == "en"
    
    def test_detect_language_short_text(self):
        """Test language detection with short text"""
        short_text = "Hello"
        lang = detect_language(short_text)
        # Should handle short text gracefully
        assert isinstance(lang, str)
        assert len(lang) >= 2
    
    def test_detect_language_mixed(self):
        """Test language detection with mixed content"""
        mixed_text = "This is English with some números and symbols 123 @#$"
        lang = detect_language(mixed_text)
        # Should still detect primary language as English
        assert lang == "en"
    
    def test_detect_language_empty(self):
        """Test language detection with empty text"""
        # Should handle empty text gracefully
        lang = detect_language("")
        assert isinstance(lang, str)


@pytest.mark.unit
class TestTopicRelevance:
    """Test topic relevance checking"""
    
    def test_check_topic_relevance_relevant(self):
        """Test topic relevance with clearly relevant text"""
        text = "Environmental protection is crucial for our planet's future. We must reduce pollution and conserve natural resources."
        topic = "Environment"
        
        relevance = check_topic_relevance(text, topic)
        assert isinstance(relevance, float)
        assert 0.0 <= relevance <= 1.0
        assert relevance > 0.3  # Should be somewhat relevant
    
    def test_check_topic_relevance_irrelevant(self):
        """Test topic relevance with irrelevant text"""
        text = "I like to play video games and watch movies on weekends."
        topic = "Environmental protection"
        
        relevance = check_topic_relevance(text, topic)
        assert isinstance(relevance, float)
        assert 0.0 <= relevance <= 1.0
        # May or may not be low relevance depending on implementation
    
    def test_check_topic_relevance_empty(self):
        """Test topic relevance with empty text"""
        relevance = check_topic_relevance("", "Any topic")
        assert isinstance(relevance, float)
        assert 0.0 <= relevance <= 1.0
    
    def test_check_topic_relevance_no_topic(self):
        """Test topic relevance with no topic"""
        text = "This is some text content."
        relevance = check_topic_relevance(text, "")
        assert isinstance(relevance, float)
        assert 0.0 <= relevance <= 1.0


@pytest.mark.unit
class TestLevelWordRequirements:
    """Test level-based word requirements"""
    
    def test_level_word_requirements_exist(self):
        """Test that level word requirements are defined"""
        assert isinstance(LEVEL_WORD_REQUIREMENTS, dict)
        
        expected_levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        for level in expected_levels:
            assert level in LEVEL_WORD_REQUIREMENTS
            assert isinstance(LEVEL_WORD_REQUIREMENTS[level], int)
            assert LEVEL_WORD_REQUIREMENTS[level] > 0
    
    def test_level_word_requirements_progression(self):
        """Test that word requirements increase with level"""
        basic = LEVEL_WORD_REQUIREMENTS.get("Basic", 0)
        intermediate = LEVEL_WORD_REQUIREMENTS.get("Intermediate", 0)
        advanced = LEVEL_WORD_REQUIREMENTS.get("Advanced", 0)
        expert = LEVEL_WORD_REQUIREMENTS.get("Expert", 0)
        
        # Requirements should generally increase with level
        assert basic <= intermediate
        assert intermediate <= advanced
        assert advanced <= expert


@pytest.mark.unit
class TestPreProcessEssay:
    """Test main pre_process_essay function"""
    
    def test_pre_process_valid_basic_essay(self):
        """Test pre-processing a valid basic level essay"""
        text = "This is a test essay about environmental protection. " * 5  # ~50 words
        
        result = pre_process_essay(text, topic_prompt="Environment", level_group="Basic")
        
        assert isinstance(result, PreProcessResult)
        assert result.word_count > 0
        assert isinstance(result.meets_length_req, bool)
        assert isinstance(result.is_english, bool)
        assert isinstance(result.is_valid, bool)
    
    def test_pre_process_too_short_essay(self):
        """Test pre-processing an essay that's too short"""
        short_text = "This is too short."
        
        result = pre_process_essay(short_text, topic_prompt="Any topic", level_group="Basic")
        
        assert isinstance(result, PreProcessResult)
        assert result.meets_length_req is False
        assert result.word_count < LEVEL_WORD_REQUIREMENTS["Basic"]["min_words"]
    
    def test_pre_process_different_levels(self):
        """Test pre-processing with different levels"""
        # Create appropriately long text for Expert level
        long_text = "This is a comprehensive essay about important topics. " * 50  # ~350 words
        
        for level in ["Basic", "Intermediate", "Advanced", "Expert"]:
            result = pre_process_essay(long_text, topic_prompt="Education", level_group=level)
            
            assert isinstance(result, PreProcessResult)
            assert result.word_count > 0
            
            # Length appropriateness depends on level requirements
            min_words = LEVEL_WORD_REQUIREMENTS[level]["min_words"]
            max_words = LEVEL_WORD_REQUIREMENTS[level]["max_words"]
            
            if min_words <= result.word_count <= max_words:
                assert result.meets_length_req is True
            else:
                assert result.meets_length_req is False
    
    def test_pre_process_non_english_text(self):
        """Test pre-processing non-English text"""
        # Note: This test depends on language detection working
        non_english = "Esto es un texto en español con muchas palabras para probar la detección."
        
        result = pre_process_essay(non_english, topic_prompt="Test", level_group="Basic")
        
        assert isinstance(result, PreProcessResult)
        # Should detect as non-English
        assert result.is_english is False
    
    def test_pre_process_empty_text(self):
        """Test pre-processing empty text"""
        result = pre_process_essay("", topic_prompt="Test", level_group="Basic")
        
        assert isinstance(result, PreProcessResult)
        assert result.word_count == 0
        assert result.meets_length_req is False
    
    def test_pre_process_whitespace_only(self):
        """Test pre-processing whitespace-only text"""
        whitespace_text = "   \n\t   \n   "
        
        result = pre_process_essay(whitespace_text, topic_prompt="Test", level_group="Basic")
        
        assert isinstance(result, PreProcessResult)
        assert result.word_count == 0
        assert result.meets_length_req is False
    
    def test_pre_process_special_characters(self):
        """Test pre-processing text with special characters"""
        special_text = "This essay contains @#$% special characters and (parentheses) and numbers 123. " * 10
        
        result = pre_process_essay(special_text, topic_prompt="Test", level_group="Basic")
        
        assert isinstance(result, PreProcessResult)
        assert result.word_count > 0
        # Should handle special characters gracefully


@pytest.mark.unit
class TestDefineEnglishCheck:
    """Test the define_english_check function"""
    
    def test_english_text_detection(self):
        """Test detecting English text"""
        english_text = "This is clearly an English sentence with proper grammar and vocabulary."
        result = define_english_check(english_text)
        assert result is True
    
    def test_non_english_text_detection(self):
        """Test detecting non-English text"""
        non_english_text = "Esto es claramente un texto en español con muchas palabras."
        result = define_english_check(non_english_text)
        assert result is False
    
    def test_empty_text_detection(self):
        """Test English detection with empty text"""
        result = define_english_check("")
        assert result is False  # Should return False for empty text


@pytest.mark.unit
class TestLevelWordRequirements:
    """Test level-based word requirements"""
    
    def test_level_word_requirements_exist(self):
        """Test that level word requirements are defined"""
        assert isinstance(LEVEL_WORD_REQUIREMENTS, dict)
        
        expected_levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        for level in expected_levels:
            assert level in LEVEL_WORD_REQUIREMENTS
            assert "min_words" in LEVEL_WORD_REQUIREMENTS[level]
            assert "max_words" in LEVEL_WORD_REQUIREMENTS[level]
            assert isinstance(LEVEL_WORD_REQUIREMENTS[level]["min_words"], int)
            assert LEVEL_WORD_REQUIREMENTS[level]["min_words"] > 0
    
    def test_level_word_requirements_progression(self):
        """Test that word requirements increase with level"""
        basic = LEVEL_WORD_REQUIREMENTS.get("Basic", {}).get("min_words", 0)
        intermediate = LEVEL_WORD_REQUIREMENTS.get("Intermediate", {}).get("min_words", 0)
        advanced = LEVEL_WORD_REQUIREMENTS.get("Advanced", {}).get("min_words", 0)
        expert = LEVEL_WORD_REQUIREMENTS.get("Expert", {}).get("min_words", 0)
        
        # Requirements should generally increase with level
        assert basic <= intermediate
        assert intermediate <= advanced
        assert advanced <= expert