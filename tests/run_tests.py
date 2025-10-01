"""
Test runner script and comprehensive test execution utilities
"""
import pytest
import sys
import os
from pathlib import Path


def run_unit_tests():
    """Run all unit tests"""
    print("🧪 Running Unit Tests...")
    return pytest.main([
        "tests/unit_test/",
        "-v",
        "-m", "unit",
        "--tb=short"
    ])


def run_integration_tests():
    """Run integration tests"""
    print("🔗 Running Integration Tests...")
    return pytest.main([
        "tests/integration/",
        "-v", 
        "-m", "integration",
        "--tb=short"
    ])


def run_system_tests():
    """Run system/end-to-end tests"""
    print("🎯 Running System Tests...")
    return pytest.main([
        "tests/system/",
        "-v",
        "-m", "system", 
        "--tb=short"
    ])


def run_azure_tests():
    """Run tests that require Azure OpenAI"""
    print("☁️  Running Azure Integration Tests...")
    return pytest.main([
        "tests/",
        "-v",
        "-m", "azure",
        "--tb=short"
    ])


def run_all_tests():
    """Run all tests in sequence"""
    print("🚀 Running Complete Test Suite...")
    return pytest.main([
        "tests/",
        "-v",
        "--tb=short"
    ])


def run_fast_tests():
    """Run only fast tests (no Azure, no slow tests)"""
    print("⚡ Running Fast Tests Only...")
    return pytest.main([
        "tests/",
        "-v",
        "-m", "not azure and not slow",
        "--tb=short"
    ])


def run_coverage_report():
    """Run tests with coverage reporting"""
    print("📊 Running Tests with Coverage Report...")
    return pytest.main([
        "tests/",
        "--cov=app",
        "--cov-report=html",
        "--cov-report=term-missing",
        "-v"
    ])


if __name__ == "__main__":
    # Add project root to Python path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "unit":
            exit_code = run_unit_tests()
        elif command == "integration":
            exit_code = run_integration_tests()
        elif command == "system":
            exit_code = run_system_tests()
        elif command == "azure":
            exit_code = run_azure_tests()
        elif command == "fast":
            exit_code = run_fast_tests()
        elif command == "coverage":
            exit_code = run_coverage_report()
        elif command == "all":
            exit_code = run_all_tests()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: unit, integration, system, azure, fast, coverage, all")
            exit_code = 1
    else:
        # Default: run fast tests
        exit_code = run_fast_tests()
    
    sys.exit(exit_code)