#!/bin/bash

# Orchestra Test Runner
echo "🚀 Starting Orchestra Test Suite..."

# 1. Run Pytest with coverage
export PYTHONPATH=$PYTHONPATH:.
pytest tests/ backend/agents/test_librarian_agent.py --cov=backend --cov-report=term-missing

if [ $? -eq 0 ]; then
    echo "✅ All tests passed successfully!"
else
    echo "❌ Some tests failed. Please check the logs above."
    exit 1
fi