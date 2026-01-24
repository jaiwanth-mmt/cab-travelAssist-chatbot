"""Pytest configuration and fixtures"""

import pytest
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


@pytest.fixture
def sample_chunks():
    """Sample chunks for testing"""
    return [
        {
            "text": "The Search API allows partners to search for available cabs.",
            "metadata": {
                "chunk_id": "chunk-1",
                "section_title": "Search API",
                "api_name": "search",
                "source": "documentation.txt",
                "chunk_index": 0,
                "token_count": 50
            }
        },
        {
            "text": "The Block API is used to reserve a cab for a customer.",
            "metadata": {
                "chunk_id": "chunk-2",
                "section_title": "Block API",
                "api_name": "block",
                "source": "documentation.txt",
                "chunk_index": 1,
                "token_count": 45
            }
        }
    ]


@pytest.fixture
def sample_session_id():
    """Sample session ID for testing"""
    return "test-session-12345"
