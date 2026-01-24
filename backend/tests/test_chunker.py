"""Tests for document chunker"""

import pytest
from backend.app.services.chunker import DocumentChunker


def test_chunker_initialization():
    """Test chunker can be initialized"""
    chunker = DocumentChunker(chunk_size=600, chunk_overlap=75)
    assert chunker.chunk_size == 600
    assert chunker.chunk_overlap == 75


def test_count_tokens():
    """Test token counting"""
    chunker = DocumentChunker()
    text = "This is a test sentence."
    token_count = chunker.count_tokens(text)
    assert token_count > 0
    assert isinstance(token_count, int)


def test_extract_api_name():
    """Test API name extraction"""
    chunker = DocumentChunker()
    
    # Test various endpoint formats
    assert chunker._extract_api_name("/partnersearchendpoint") == "search"
    assert chunker._extract_api_name("/search") == "search"
    assert chunker._extract_api_name("/partnerblockendpoint") == "block"


def test_section_info_extraction():
    """Test section title extraction"""
    chunker = DocumentChunker()
    
    lines = [
        "# Main Title",
        "## Search API",
        "This is the search API content",
        "More content here"
    ]
    
    section_title, api_name = chunker.extract_section_info(lines, 3)
    assert "Search API" in section_title or "Main Title" in section_title


def test_code_block_detection():
    """Test code block detection"""
    chunker = DocumentChunker()
    
    assert chunker.is_code_block_start("```python")
    assert chunker.is_code_block_start("```json")
    assert chunker.is_code_block_start("{")
    assert not chunker.is_code_block_start("Regular text")


def test_create_chunk():
    """Test chunk creation"""
    chunker = DocumentChunker()
    
    chunk = chunker._create_chunk(
        text="This is test content",
        index=0,
        section_title="Test Section",
        api_name="test_api"
    )
    
    assert chunk is not None
    assert chunk["text"] == "This is test content"
    assert chunk["metadata"]["section_title"] == "Test Section"
    assert chunk["metadata"]["api_name"] == "test_api"
    assert chunk["metadata"]["chunk_index"] == 0
    assert "chunk_id" in chunk["metadata"]


def test_empty_chunk_filtering():
    """Test that empty chunks are not created"""
    chunker = DocumentChunker()
    
    chunk = chunker._create_chunk(
        text="",
        index=0,
        section_title="Test",
        api_name=None
    )
    
    assert chunk is None


def test_overlap_lines():
    """Test overlap line extraction"""
    chunker = DocumentChunker(chunk_overlap=50)
    
    lines = ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"]
    overlap = chunker._get_overlap_lines(lines)
    
    assert isinstance(overlap, list)
    assert len(overlap) <= len(lines)


@pytest.mark.skip(reason="Requires documentation.txt file")
def test_chunk_documentation():
    """Test full document chunking"""
    chunker = DocumentChunker()
    chunks = chunker.chunk_document("documentation.txt")
    
    assert len(chunks) > 0
    assert all("text" in chunk for chunk in chunks)
    assert all("metadata" in chunk for chunk in chunks)
