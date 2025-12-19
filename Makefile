# Enhanced Document Converter v2.1.1 - Makefile
# Convenience commands for development and testing

.PHONY: help install install-dev test lint format type-check clean run

help:
	@echo "Enhanced Document Converter v2.1 - Development Commands"
	@echo ""
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make test         - Run test suite"
	@echo "  make lint         - Run linters (flake8, pylint)"
	@echo "  make format       - Format code with black and isort"
	@echo "  make type-check   - Run mypy type checker"
	@echo "  make clean        - Clean build artifacts and cache"
	@echo "  make run          - Run the converter"
	@echo "  make check        - Run all checks (lint + type + test)"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing

lint:
	flake8 *.py
	pylint *.py --disable=C0103,C0114,C0115,C0116

format:
	black *.py tests/
	isort *.py tests/

type-check:
	mypy *.py

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov .coverage
	rm -rf build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

run:
	python main.py

check: lint type-check test
	@echo "All checks passed!"

# Development workflow
dev-setup: install-dev
	@echo "Development environment ready!"
	@echo "Run 'make check' to verify everything works"
