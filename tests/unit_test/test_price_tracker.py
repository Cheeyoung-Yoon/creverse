"""
Unit tests for price_tracker.py
"""
import pytest
from datetime import datetime
from unittest.mock import patch

from app.utils.price_tracker import (
    TokenUsage, PriceTracker, get_price_tracker, 
    track_api_usage, get_usage_summary
)


@pytest.mark.unit
class TestTokenUsage:
    """Test TokenUsage dataclass"""
    
    def test_token_usage_creation(self):
        """Test TokenUsage creation with default values"""
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0
    
    def test_token_usage_with_values(self):
        """Test TokenUsage creation with specific values"""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
    
    def test_token_usage_addition(self):
        """Test TokenUsage addition operator"""
        usage1 = TokenUsage(100, 50, 150)
        usage2 = TokenUsage(200, 75, 275)
        
        result = usage1 + usage2
        assert result.prompt_tokens == 300
        assert result.completion_tokens == 125
        assert result.total_tokens == 425


@pytest.mark.unit
class TestPriceTracker:
    """Test PriceTracker class"""
    
    def test_price_tracker_creation(self):
        """Test PriceTracker creation with default values"""
        tracker = PriceTracker()
        assert tracker.input_cost_per_1m == 0.250
        assert tracker.output_cost_per_1m == 2.0
        assert tracker.session_calls == 0
        assert isinstance(tracker.total_usage, TokenUsage)
        assert len(tracker.call_history) == 0
    
    def test_track_usage_basic(self, sample_token_usage):
        """Test basic usage tracking"""
        tracker = PriceTracker()
        result = tracker.track_usage(sample_token_usage, "test_operation")
        
        assert tracker.session_calls == 1
        assert tracker.total_usage.prompt_tokens == 100
        assert tracker.total_usage.completion_tokens == 50
        assert tracker.total_usage.total_tokens == 150
        
        # Check cost calculation
        expected_input_cost = (100 / 1_000_000) * 0.250
        expected_output_cost = (50 / 1_000_000) * 2.0
        expected_total_cost = expected_input_cost + expected_output_cost
        
        assert result["input_cost"] == expected_input_cost
        assert result["output_cost"] == expected_output_cost
        assert result["total_cost"] == expected_total_cost
        assert result["operation"] == "test_operation"
    
    def test_track_usage_multiple_calls(self, sample_token_usage):
        """Test tracking multiple API calls"""
        tracker = PriceTracker()
        
        # First call
        tracker.track_usage(sample_token_usage, "call_1")
        # Second call
        tracker.track_usage(sample_token_usage, "call_2")
        
        assert tracker.session_calls == 2
        assert tracker.total_usage.prompt_tokens == 200
        assert tracker.total_usage.completion_tokens == 100
        assert tracker.total_usage.total_tokens == 300
        assert len(tracker.call_history) == 2
    
    def test_get_session_summary(self, sample_token_usage):
        """Test session summary generation"""
        tracker = PriceTracker()
        tracker.track_usage(sample_token_usage, "test")
        
        summary = tracker.get_session_summary()
        
        assert "total_calls" in summary
        assert "total_tokens" in summary
        assert "total_cost" in summary
        assert "cost_breakdown" in summary
        assert "session_duration" in summary
        
        assert summary["total_calls"] == 1
        assert summary["total_tokens"] == 150
        assert summary["cost_breakdown"]["input_cost"] > 0
        assert summary["cost_breakdown"]["output_cost"] > 0
    
    @patch('builtins.open')
    @patch('json.dump')
    def test_export_history(self, mock_json_dump, mock_open, sample_token_usage):
        """Test exporting call history to JSON"""
        tracker = PriceTracker()
        tracker.track_usage(sample_token_usage, "test")
        
        tracker.export_history("test_export.json")
        
        mock_open.assert_called_once_with("test_export.json", 'w')
        mock_json_dump.assert_called_once()
        
        # Check the exported data structure
        call_args = mock_json_dump.call_args[0][0]
        assert "session_summary" in call_args
        assert "call_history" in call_args
        assert "export_timestamp" in call_args


@pytest.mark.unit
class TestGlobalPriceTracker:
    """Test global price tracker functions"""
    
    def test_get_price_tracker(self):
        """Test getting global price tracker instance"""
        tracker = get_price_tracker()
        assert isinstance(tracker, PriceTracker)
        
        # Should return the same instance
        tracker2 = get_price_tracker()
        assert tracker is tracker2
    
    def test_track_api_usage_convenience(self, sample_token_usage):
        """Test convenience function for tracking API usage"""
        result = track_api_usage(sample_token_usage, "convenience_test")
        
        assert "total_cost" in result
        assert "operation" in result
        assert result["operation"] == "convenience_test"
    
    def test_get_usage_summary_convenience(self, sample_token_usage):
        """Test convenience function for getting usage summary"""
        # Track some usage first
        track_api_usage(sample_token_usage, "test")
        
        summary = get_usage_summary()
        assert "total_calls" in summary
        assert "total_cost" in summary
        assert summary["total_calls"] >= 1


@pytest.mark.unit
class TestPriceTrackerEdgeCases:
    """Test edge cases and error handling"""
    
    def test_track_usage_missing_tokens(self):
        """Test tracking usage with missing token fields"""
        tracker = PriceTracker()
        
        # Test with partial data
        partial_usage = {"prompt_tokens": 100}
        result = tracker.track_usage(partial_usage, "partial_test")
        
        assert result["input_cost"] > 0
        assert result["output_cost"] == 0  # No completion tokens
    
    def test_track_usage_zero_tokens(self):
        """Test tracking usage with zero tokens"""
        tracker = PriceTracker()
        zero_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        result = tracker.track_usage(zero_usage, "zero_test")
        
        assert result["total_cost"] == 0.0
        assert tracker.session_calls == 1  # Call should still be tracked
    
    def test_track_usage_invalid_data(self):
        """Test tracking usage with invalid data"""
        tracker = PriceTracker()
        
        # Test with string values
        invalid_usage = {
            "prompt_tokens": "100",
            "completion_tokens": "50"
        }
        
        # Should handle gracefully (convert to int or default to 0)
        result = tracker.track_usage(invalid_usage, "invalid_test")
        assert "total_cost" in result
        assert tracker.session_calls == 1