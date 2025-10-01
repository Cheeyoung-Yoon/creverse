# Test Suite Documentation

## Overview

This comprehensive test suite covers all aspects of the essay evaluation system, from individual unit tests to complete end-to-end system validation. The test suite is organized into three main categories following testing best practices.

## Test Structure

```
tests/
├── conftest.py                 # Shared pytest configuration and fixtures
├── pytest.ini                 # Pytest configuration
├── run_tests.py               # Test runner utility
├── unit_test/                 # Unit tests for individual components
│   ├── test_price_tracker.py
│   ├── test_tracer.py
│   ├── test_prompt_loader_enhanced.py
│   ├── test_models_rubric.py
│   ├── test_models_request_response.py
│   ├── test_pre_process_enhanced.py
│   └── test_post_process.py
├── integration/               # Integration tests for component interactions
│   ├── test_essay_evaluation_integration.py
│   └── test_api_integration_enhanced.py
└── system/                    # End-to-end system tests
    └── test_complete_pipeline.py
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
- **Purpose**: Test individual components in isolation
- **Scope**: Functions, classes, and modules
- **Dependencies**: Minimal external dependencies, heavily mocked
- **Speed**: Fast execution (< 1 second per test)

**Components Covered**:
- `app.utils.price_tracker`: Token usage tracking and cost calculation
- `app.utils.tracer`: LLM tracing and observation wrapper
- `app.utils.prompt_loader`: Prompt loading and version management
- `app.models.*`: Pydantic models for requests, responses, and rubric items
- `app.services.evaluation.pre_process`: Essay preprocessing and validation
- `app.services.evaluation.post_process`: Score aggregation and finalization

### Integration Tests (`@pytest.mark.integration`)
- **Purpose**: Test component interactions and workflows
- **Scope**: Multiple components working together
- **Dependencies**: Mocked external services (Azure OpenAI)
- **Speed**: Medium execution (1-5 seconds per test)

**Scenarios Covered**:
- Complete essay evaluation pipeline with mocked LLM
- API endpoint testing with FastAPI TestClient
- Parallel execution of grammar and structure evaluation chains
- Error handling and resilience testing
- CORS and middleware functionality

### System Tests (`@pytest.mark.system`)
- **Purpose**: End-to-end validation of complete system
- **Scope**: Full application workflow from API request to response
- **Dependencies**: Comprehensive mocking or real services
- **Speed**: Slower execution (5-30 seconds per test)

**Scenarios Covered**:
- Complete evaluation pipeline with different essay types and levels
- Performance characteristics and resource usage
- Edge case handling (empty text, very long essays, special characters)
- Batch processing simulation
- System health and monitoring

## Test Markers

The test suite uses pytest markers to categorize and filter tests:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests  
- `@pytest.mark.system`: System/end-to-end tests
- `@pytest.mark.azure`: Tests requiring Azure OpenAI credentials
- `@pytest.mark.slow`: Long-running tests

## Running Tests

### Using the Test Runner

```bash
# Run all fast tests (recommended for development)
python tests/run_tests.py fast

# Run specific test categories
python tests/run_tests.py unit
python tests/run_tests.py integration
python tests/run_tests.py system

# Run all tests
python tests/run_tests.py all

# Run tests requiring Azure OpenAI credentials
python tests/run_tests.py azure

# Run with coverage report
python tests/run_tests.py coverage
```

### Using pytest directly

```bash
# Run all tests
pytest tests/

# Run only unit tests
pytest tests/ -m unit

# Run tests excluding Azure and slow tests
pytest tests/ -m "not azure and not slow"

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/unit_test/test_price_tracker.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Environment Setup

### Required Dependencies

Install test dependencies:
```bash
pip install pytest pytest-asyncio pytest-cov
```

### Environment Variables

For Azure OpenAI tests (optional):
```bash
export AZURE_OPENAI_ENDPOINT="your-endpoint"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment"
```

## Test Configuration

### pytest.ini
- Configures test discovery patterns
- Sets up test markers
- Defines default pytest options

### conftest.py
- Shared fixtures for all tests
- Mock objects and sample data
- Environment setup utilities

## Key Testing Features

### Comprehensive Mocking
- **LLM Responses**: Sophisticated mock responses that vary based on text length and complexity
- **Azure OpenAI**: Complete mocking of Azure OpenAI API calls
- **File Operations**: Mocked file I/O for prompt loading tests

### Realistic Test Data
- **Sample Essays**: Essays at different complexity levels (Basic, Intermediate, Advanced)
- **Edge Cases**: Empty text, very long text, special characters, Unicode
- **Error Scenarios**: API failures, malformed responses, network timeouts

### Performance Testing
- **Response Times**: Validation of acceptable processing times
- **Parallel Execution**: Testing of concurrent grammar and structure evaluation
- **Resource Usage**: Memory and CPU usage patterns

### Error Resilience
- **API Failures**: Testing system behavior when LLM calls fail
- **Malformed Data**: Handling of invalid JSON responses
- **Edge Cases**: Empty inputs, oversized payloads, unicode handling

## Test Coverage Goals

The test suite aims for comprehensive coverage:

- **Unit Tests**: 90%+ coverage of individual functions and methods
- **Integration Tests**: 80%+ coverage of component interactions
- **System Tests**: 100% coverage of main user workflows
- **Edge Cases**: Comprehensive coverage of error conditions and edge cases

## Best Practices

### Writing New Tests
1. **Choose the Right Level**: Unit for isolated logic, integration for component interaction, system for end-to-end
2. **Use Appropriate Fixtures**: Leverage shared fixtures from `conftest.py`
3. **Mock External Dependencies**: Use mocks for Azure OpenAI, file system, network calls
4. **Test Edge Cases**: Include tests for empty inputs, error conditions, boundary values
5. **Add Markers**: Use appropriate pytest markers for categorization

### Test Naming
- Descriptive test names: `test_price_tracker_calculates_cost_correctly`
- Group related tests in classes: `TestPriceTrackerEdgeCases`
- Use docstrings to explain complex test scenarios

### Assertions
- Use specific assertions: `assert response.status_code == 200`
- Include meaningful error messages: `assert len(results) == 5, "Expected 5 evaluation results"`
- Test both positive and negative cases

## Continuous Integration

The test suite is designed to work in CI/CD environments:

- **Fast Feedback**: Unit and integration tests run quickly for rapid feedback
- **Environment Flexibility**: Tests work with or without Azure OpenAI credentials
- **Comprehensive Coverage**: System tests validate complete functionality
- **Parallel Execution**: Tests can run in parallel for faster CI builds

## Debugging Tests

### Common Issues
1. **Import Errors**: Ensure project root is in Python path
2. **Missing Fixtures**: Check that fixtures are properly imported from `conftest.py`
3. **Async Issues**: Use `@pytest.mark.asyncio` for async test functions
4. **Mock Configuration**: Verify mock setup matches actual API interfaces

### Debugging Commands
```bash
# Run single test with full output
pytest tests/unit_test/test_price_tracker.py::TestPriceTracker::test_track_usage_basic -v -s

# Run with debugger on failure
pytest tests/ --pdb

# Run with detailed traceback
pytest tests/ --tb=long
```

## Contributing to Tests

When adding new features to the application:

1. **Add Unit Tests**: Test new functions and methods in isolation
2. **Update Integration Tests**: Test interactions with existing components
3. **Extend System Tests**: Add end-to-end scenarios if needed
4. **Update Documentation**: Keep this README current with changes
5. **Run Full Suite**: Verify all tests pass before submitting changes

The test suite is a critical part of the application's quality assurance and should be maintained alongside code changes.