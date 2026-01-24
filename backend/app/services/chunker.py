"""Document chunking service with metadata extraction"""

import re
import uuid
from typing import List, Dict, Optional, Tuple
import tiktoken

from backend.app.core.config import settings
from backend.app.utils.logger import setup_logger

logger = setup_logger(__name__)


class DocumentChunker:
    """Intelligent document chunker for API documentation"""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))
    
    def extract_section_info(self, lines: List[str], start_idx: int) -> Tuple[str, str]:
        """Extract section title and API name from surrounding context"""
        section_title = "General Documentation"
        api_name = ''
        
        # Look backwards for section headers
        for i in range(start_idx, max(0, start_idx - 20), -1):
            line = lines[i].strip()
            
            # Check for markdown headers
            if line.startswith("# "):
                section_title = line.lstrip("# ").strip()
                break
            elif line.startswith("## "):
                section_title = line.lstrip("## ").strip()
                break
            elif line.startswith("### "):
                section_title = line.lstrip("### ").strip()
                break
            
            # Check for API endpoint patterns
            api_match = re.match(r'^##\s+(.+?)\s+\[([^\]]+)\]', line)
            if api_match:
                section_title = api_match.group(1).strip()
                api_name = self._extract_api_name(api_match.group(2))
                break
        
        # Try to extract API name from content
        if not api_name:
            for i in range(start_idx, min(len(lines), start_idx + 10)):
                line = lines[i]
                # Look for endpoint patterns like [/partnersearchendpoint]
                endpoint_match = re.search(r'\[(/[a-z]+)\]', line, re.IGNORECASE)
                if endpoint_match:
                    api_name = self._extract_api_name(endpoint_match.group(1))
                    break
        
        return section_title, api_name
    
    def _extract_api_name(self, endpoint: str) -> str:
        """Extract clean API name from endpoint"""
        # Remove leading slash and common prefixes
        name = endpoint.lstrip('/')
        name = name.replace('partner', '').replace('endpoint', '')
        # Convert to lowercase and clean
        name = re.sub(r'[^a-z0-9_]', '', name.lower())
        return name if name else ''
    
    def is_code_block_start(self, line: str) -> bool:
        """Check if line starts a code block"""
        return line.strip().startswith('```') or line.strip().startswith('{')
    
    def find_code_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of a code block"""
        if lines[start_idx].strip().startswith('```'):
            # Markdown code block
            for i in range(start_idx + 1, len(lines)):
                if lines[i].strip().startswith('```'):
                    return i
        else:
            # JSON block - find matching brace
            brace_count = 0
            for i in range(start_idx, len(lines)):
                brace_count += lines[i].count('{') - lines[i].count('}')
                if brace_count == 0 and i > start_idx:
                    return i
        
        return start_idx
    
    def chunk_document(self, file_path: str) -> List[Dict]:
        """
        Chunk document into semantic segments with metadata
        
        Args:
            file_path: Path to documentation file
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        logger.info(f"Starting document chunking: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            logger.error(f"Documentation file not found: {file_path}")
            raise
        
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_start_idx = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check if we're starting a code block
            if self.is_code_block_start(line):
                code_block_end = self.find_code_block_end(lines, i)
                code_block = '\n'.join(lines[i:code_block_end + 1])
                code_tokens = self.count_tokens(code_block)
                
                # If adding code block exceeds chunk size and we have content, save current chunk
                if current_tokens + code_tokens > self.chunk_size and current_chunk:
                    section_title, api_name = self.extract_section_info(lines, chunk_start_idx)
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk),
                        len(chunks),
                        section_title,
                        api_name
                    ))
                    
                    # Start new chunk with overlap
                    overlap_lines = self._get_overlap_lines(current_chunk)
                    current_chunk = overlap_lines
                    current_tokens = self.count_tokens('\n'.join(current_chunk))
                    chunk_start_idx = i
                
                # Add code block to current chunk
                current_chunk.append(code_block)
                current_tokens += code_tokens
                i = code_block_end + 1
                continue
            
            # Regular line processing
            line_tokens = self.count_tokens(line)
            
            # If adding this line exceeds chunk size
            if current_tokens + line_tokens > self.chunk_size and current_chunk:
                section_title, api_name = self.extract_section_info(lines, chunk_start_idx)
                chunks.append(self._create_chunk(
                    '\n'.join(current_chunk),
                    len(chunks),
                    section_title,
                    api_name
                ))
                
                # Start new chunk with overlap
                overlap_lines = self._get_overlap_lines(current_chunk)
                current_chunk = overlap_lines
                current_tokens = self.count_tokens('\n'.join(current_chunk))
                chunk_start_idx = i
            
            current_chunk.append(line)
            current_tokens += line_tokens
            i += 1
        
        # Add final chunk if it has content
        if current_chunk:
            section_title, api_name = self.extract_section_info(lines, chunk_start_idx)
            chunks.append(self._create_chunk(
                '\n'.join(current_chunk),
                len(chunks),
                section_title,
                api_name
            ))
        
        logger.info(f"Document chunked into {len(chunks)} segments")
        return chunks
    
    def _get_overlap_lines(self, lines: List[str]) -> List[str]:
        """Get overlap lines from end of current chunk"""
        overlap_text = '\n'.join(lines)
        overlap_tokens = self.count_tokens(overlap_text)
        
        # Take lines from the end until we reach overlap size
        result = []
        tokens = 0
        for line in reversed(lines):
            line_tokens = self.count_tokens(line)
            if tokens + line_tokens > self.chunk_overlap:
                break
            result.insert(0, line)
            tokens += line_tokens
        
        return result
    
    def _create_chunk(
        self,
        text: str,
        index: int,
        section_title: str,
        api_name: str
    ) -> Dict:
        """Create a chunk dictionary with metadata"""
        # Clean up text
        text = text.strip()
        
        # Skip empty chunks
        if not text or self.count_tokens(text) < 10:
            return None
        
        chunk = {
            "text": text,
            "metadata": {
                "chunk_id": str(uuid.uuid4()),
                "section_title": section_title,
                "api_name": api_name,
                "source": "documentation.txt",
                "chunk_index": index,
                "token_count": self.count_tokens(text)
            }
        }
        
        return chunk


def chunk_documentation(file_path: str = None) -> List[Dict]:
    """
    Convenience function to chunk documentation
    
    Args:
        file_path: Path to documentation file (defaults to settings)
        
    Returns:
        List of chunks with metadata
    """
    if file_path is None:
        file_path = settings.documentation_path
    
    chunker = DocumentChunker()
    chunks = chunker.chunk_document(file_path)
    
    # Filter out None chunks
    chunks = [c for c in chunks if c is not None]
    
    return chunks
