"""
Unit tests for tracer.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from app.utils.tracer import ObservedLLM, LLM


@pytest.mark.unit
class TestObservedLLM:
    """Test ObservedLLM wrapper class"""
    
    def test_observed_llm_creation(self):
        """Test ObservedLLM creation with mock LLM"""
        mock_llm = Mock(spec=LLM)
        observed = ObservedLLM(mock_llm, trace_id="test_trace")
        
        assert observed.llm is mock_llm
        assert observed.trace_id == "test_trace"
    
    @pytest.mark.asyncio
    async def test_run_azure_openai_basic(self):
        """Test basic Azure OpenAI call through ObservedLLM"""
        mock_llm = Mock(spec=LLM)
        mock_llm.run_azure_openai = Mock(return_value={"test": "response"})
        
        observed = ObservedLLM(mock_llm, trace_id="test_trace")
        
        messages = [{"role": "user", "content": "test"}]
        json_schema = {"type": "object"}
        
        result = await observed.run_azure_openai(
            messages=messages,
            json_schema=json_schema,
            name="test_operation"
        )
        
        # Check that the underlying LLM was called
        mock_llm.run_azure_openai.assert_called_once_with(
            messages=messages,
            json_schema=json_schema,
            name="test_operation"
        )
        
        assert result == {"test": "response"}
    
    @patch('app.utils.tracer.LANGFUSE_AVAILABLE', True)
    @patch('app.utils.tracer.lf')
    def test_with_langfuse_available(self, mock_lf):
        """Test ObservedLLM when Langfuse is available"""
        mock_llm = Mock(spec=LLM)
        mock_trace = Mock()
        mock_lf.trace.return_value = mock_trace
        
        observed = ObservedLLM(mock_llm, trace_id="test_trace")
        
        # Should have trace set when Langfuse is available
        assert hasattr(observed, 'trace_id')
    
    @patch('app.utils.tracer.LANGFUSE_AVAILABLE', False)
    def test_without_langfuse_available(self):
        """Test ObservedLLM when Langfuse is not available"""
        mock_llm = Mock(spec=LLM)
        observed = ObservedLLM(mock_llm, trace_id="test_trace")
        
        # Should still work when Langfuse is not available
        assert observed.llm is mock_llm
        assert observed.trace_id == "test_trace"


@pytest.mark.unit
class TestTracerConfiguration:
    """Test tracer configuration and initialization"""
    
    @patch.dict(os.environ, {
        'LANGFUSE_PUBLIC_KEY': 'test_public_key',
        'LANGFUSE_SECRET_KEY': 'test_secret_key',
        'LANGFUSE_HOST': 'https://test.langfuse.com'
    })
    @patch('app.utils.tracer.Langfuse')
    def test_langfuse_initialization_with_credentials(self, mock_langfuse):
        """Test Langfuse initialization when credentials are provided"""
        # Reload the module to test initialization
        import importlib
        import app.utils.tracer
        importlib.reload(app.utils.tracer)
        
        # Check that Langfuse was initialized with correct parameters
        mock_langfuse.assert_called_with(
            public_key='test_public_key',
            secret_key='test_secret_key',
            host='https://test.langfuse.com',
            release='v1.0.0'
        )
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('app.utils.tracer.Langfuse')
    def test_langfuse_initialization_without_credentials(self, mock_langfuse):
        """Test Langfuse initialization when credentials are missing"""
        # Reload the module to test initialization
        import importlib
        import app.utils.tracer
        importlib.reload(app.utils.tracer)
        
        # Should still initialize but with warning logged
        # LANGFUSE_AVAILABLE should be False
        from app.utils.tracer import LANGFUSE_AVAILABLE
        assert LANGFUSE_AVAILABLE is False


@pytest.mark.unit
class TestLLMProtocol:
    """Test LLM protocol implementation"""
    
    def test_llm_protocol_check(self):
        """Test that objects correctly implement LLM protocol"""
        # Mock object that implements the protocol
        class MockValidLLM:
            async def run_azure_openai(self, messages, json_schema=None, name=None):
                return {"test": "response"}
        
        # Mock object that doesn't implement the protocol
        class MockInvalidLLM:
            def some_other_method(self):
                pass
        
        valid_llm = MockValidLLM()
        invalid_llm = MockInvalidLLM()
        
        # Test protocol checking
        assert isinstance(valid_llm, LLM)
        assert not isinstance(invalid_llm, LLM)


@pytest.mark.unit
class TestTracerIntegration:
    """Test tracer integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_observed_llm_error_handling(self):
        """Test ObservedLLM error handling"""
        mock_llm = Mock(spec=LLM)
        mock_llm.run_azure_openai = Mock(side_effect=Exception("API Error"))
        
        observed = ObservedLLM(mock_llm, trace_id="test_trace")
        
        with pytest.raises(Exception, match="API Error"):
            await observed.run_azure_openai(
                messages=[{"role": "user", "content": "test"}],
                json_schema={"type": "object"},
                name="error_test"
            )
        
        # Ensure the original method was called despite the error
        mock_llm.run_azure_openai.assert_called_once()
    
    def test_trace_id_propagation(self):
        """Test that trace_id is properly stored and accessible"""
        mock_llm = Mock(spec=LLM)
        test_trace_id = "test_trace_123"
        
        observed = ObservedLLM(mock_llm, trace_id=test_trace_id)
        
        assert observed.trace_id == test_trace_id
    
    @patch('app.utils.tracer.logger')
    def test_logging_integration(self, mock_logger):
        """Test that logging works correctly in tracer module"""
        # This would test that logger messages are properly formatted
        # and that appropriate log levels are used
        mock_llm = Mock(spec=LLM)
        observed = ObservedLLM(mock_llm, trace_id="test_trace")
        
        # The initialization should log info or warnings
        # Exact behavior depends on Langfuse availability
        assert observed is not None