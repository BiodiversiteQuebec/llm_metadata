"""
Pytest configuration and shared fixtures for llm_metadata tests.

Replaces the former config.py helper that was explicitly imported
in each test file.
"""

from dotenv import load_dotenv


def pytest_configure(config):
    """Load .env before test collection begins."""
    load_dotenv()
