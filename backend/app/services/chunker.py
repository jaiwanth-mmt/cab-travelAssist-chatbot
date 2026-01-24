"""Document chunking service with semantic preservation and metadata extraction"""

import re
import uuid
from typing import List, Dict, Optional, Tuple
import tiktoken

from backend.app.core.config import settings
from backend.app.utils.logger import setup_logger

logger = setup_logger(__name__)


class DocumentChunker:
    """Intelligent semantic document chunker for API documentation"""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Section boundaries - these indicate new major sections
        self.section_markers = [
            r'^#\s+',           # H1 headers
            r'^##\s+',          # H2 headers  
            r'^###\s+',         # H3 headers
            r'^####\s+',        # H4 headers
        ]
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))
    
    def _is_section_boundary(self, line: str) -> bool:
        """Check if line is a section boundary"""
        line_stripped = line.strip()
        for marker in self.section_markers:
            if re.match(marker, line_stripped):
                return True
        return False
    
    def _extract_section_hierarchy(self, lines: List[str], current_idx: int) -> Dict[str, str]:
        """Extract hierarchical section context by looking backwards"""
        h1_title = "General Documentation"
        h2_title = ""
        h3_title = ""
        api_endpoint = ""
        
        # Look backwards to find all header levels
        for i in range(current_idx, max(0, current_idx - 50), -1):
            line = lines[i].strip()
            
            # H1 header
            if line.startswith("# ") and not h1_title != "General Documentation":
                h1_title = line.lstrip("# ").strip()
            
            # H2 header
            elif line.startswith("## ") and not h2_title:
                h2_title = line.lstrip("## ").strip()
                # Extract API endpoint from H2 if present
                endpoint_match = re.search(r'\[(/[^\]]+)\]', h2_title)
                if endpoint_match:
                    api_endpoint = endpoint_match.group(1)
            
            # H3 header
            elif line.startswith("### ") and not h3_title:
                h3_title = line.lstrip("### ").strip()
            
            # List items with endpoints
            elif line.startswith("+ [") and not api_endpoint:
                endpoint_match = re.search(r'\[([^\]]+)\]', line)
                if endpoint_match:
                    potential_endpoint = endpoint_match.group(1)
                    if potential_endpoint.startswith("/") or potential_endpoint.startswith("reference/"):
                        api_endpoint = potential_endpoint
        
        # Build hierarchical section title
        section_parts = []
        if h1_title != "General Documentation":
            section_parts.append(h1_title)
        if h2_title:
            section_parts.append(h2_title)
        if h3_title:
            section_parts.append(h3_title)
        
        section_title = " > ".join(section_parts) if section_parts else h1_title
        
        return {
            "section_title": section_title,
            "api_endpoint": self._clean_api_endpoint(api_endpoint),
            "h1": h1_title,
            "h2": h2_title,
            "h3": h3_title
        }
    
    def _clean_api_endpoint(self, endpoint: str) -> str:
        """Clean and normalize API endpoint"""
        if not endpoint:
            return ""
        
        # Remove 'reference/' prefix if present
        endpoint = re.sub(r'^reference/', '', endpoint)
        
        # Clean and normalize
        endpoint = endpoint.strip().lower()
        
        return endpoint
    
    def _detect_code_block(self, line: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if line starts a code block
        Returns (is_code_block, language)
        """
        stripped = line.strip()
        
        # Markdown code fence
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or "text"
            return True, lang
        
        # JSON object start
        if stripped == "{" or stripped.startswith("{"):
            return True, "json"
        
        # JSON array start  
        if stripped == "[" or stripped.startswith("[{"):
            return True, "json"
            
        return False, None
    
    def _find_code_block_end(self, lines: List[str], start_idx: int, code_type: str) -> int:
        """Find the end index of a code block"""
        
        # Markdown code fence
        if code_type and code_type != "json":
            for i in range(start_idx + 1, len(lines)):
                if lines[i].strip().startswith("```"):
                    return i
            return len(lines) - 1
        
        # JSON block - count braces/brackets
        if code_type == "json":
            brace_count = 0
            bracket_count = 0
            in_block = False
            
            for i in range(start_idx, len(lines)):
                line = lines[i]
                
                # Count opening/closing characters
                brace_count += line.count('{') - line.count('}')
                bracket_count += line.count('[') - line.count(']')
                
                if brace_count > 0 or bracket_count > 0:
                    in_block = True
                
                # Block is complete when counts return to zero
                if in_block and brace_count == 0 and bracket_count == 0:
                    return i
            
            return len(lines) - 1
        
        return start_idx
    
    def _extract_semantic_blocks(self, content: str) -> List[Dict]:
        """
        Extract semantic blocks from documentation with aggressive splitting
        Each block represents a logical unit but respects max chunk size
        """
        lines = content.split('\n')
        blocks = []
        current_block_lines = []
        current_block_start_idx = 0
        current_block_tokens = 0
        
        # Maximum tokens for a semantic block (before further chunking)
        # Set to 1.5x chunk_size to allow some flexibility
        max_block_tokens = int(self.chunk_size * 1.5)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            line_tokens = self.count_tokens(line)
            
            # Check if this is a section boundary (new H1, H2, H3, or H4)
            is_boundary = self._is_section_boundary(line)
            
            # Force split if:
            # 1. New section boundary AND we have content
            # 2. Current block would exceed max_block_tokens
            should_split = (is_boundary and current_block_lines) or \
                          (current_block_tokens + line_tokens > max_block_tokens and current_block_lines)
            
            if should_split:
                # Save current block
                block_text = '\n'.join(current_block_lines).strip()
                if block_text:
                    hierarchy = self._extract_section_hierarchy(lines, current_block_start_idx)
                    blocks.append({
                        "text": block_text,
                        "start_idx": current_block_start_idx,
                        "hierarchy": hierarchy
                    })
                
                # Start new block
                current_block_lines = [line]
                current_block_start_idx = i
                current_block_tokens = line_tokens
                i += 1
                continue
            
            # Check for code blocks - keep intact but may trigger split
            is_code, code_type = self._detect_code_block(line)
            if is_code:
                code_end_idx = self._find_code_block_end(lines, i, code_type)
                code_block = '\n'.join(lines[i:code_end_idx + 1])
                code_tokens = self.count_tokens(code_block)
                
                # If adding code block would exceed limit and we have content, split first
                if current_block_tokens + code_tokens > max_block_tokens and current_block_lines:
                    block_text = '\n'.join(current_block_lines).strip()
                    if block_text:
                        hierarchy = self._extract_section_hierarchy(lines, current_block_start_idx)
                        blocks.append({
                            "text": block_text,
                            "start_idx": current_block_start_idx,
                            "hierarchy": hierarchy
                        })
                    
                    # Start new block with code
                    current_block_lines = [code_block]
                    current_block_start_idx = i
                    current_block_tokens = code_tokens
                else:
                    # Add code block to current
                    current_block_lines.append(code_block)
                    current_block_tokens += code_tokens
                
                i = code_end_idx + 1
                continue
            
            # Regular line
            current_block_lines.append(line)
            current_block_tokens += line_tokens
            i += 1
        
        # Add final block
        if current_block_lines:
            block_text = '\n'.join(current_block_lines).strip()
            if block_text and current_block_tokens > 20:
                hierarchy = self._extract_section_hierarchy(lines, current_block_start_idx)
                blocks.append({
                    "text": block_text,
                    "start_idx": current_block_start_idx,
                    "hierarchy": hierarchy
                })
        
        logger.info(f"Extracted {len(blocks)} semantic blocks from document")
        return blocks
    
    def _chunk_large_block(self, block: Dict) -> List[Dict]:
        """
        Split a large semantic block into smaller chunks while preserving structure
        """
        text = block["text"]
        hierarchy = block["hierarchy"]
        
        # If block fits in chunk size, return as-is
        token_count = self.count_tokens(text)
        if token_count <= self.chunk_size:
            return [{
                "text": text,
                "hierarchy": hierarchy,
                "token_count": token_count
            }]
        
        # Block is too large, need to split intelligently
        lines = text.split('\n')
        chunks = []
        current_chunk_lines = []
        current_tokens = 0
        
        # Always include the section header in first chunk
        header_lines = []
        for line in lines[:10]:  # Check first 10 lines for headers
            if line.strip().startswith('#') or line.strip().startswith('##'):
                header_lines.append(line)
            else:
                break
        
        if header_lines:
            current_chunk_lines.extend(header_lines)
            current_tokens = self.count_tokens('\n'.join(header_lines))
        
        i = len(header_lines)
        while i < len(lines):
            line = lines[i]
            
            # Check for code block
            is_code, code_type = self._detect_code_block(line)
            if is_code:
                code_end_idx = self._find_code_block_end(lines, i, code_type)
                code_block = '\n'.join(lines[i:code_end_idx + 1])
                code_tokens = self.count_tokens(code_block)
                
                # If code block alone exceeds chunk size, keep it in its own chunk
                if code_tokens > self.chunk_size:
                    # Save current chunk if it has content
                    if current_chunk_lines:
                        chunk_text = '\n'.join(current_chunk_lines).strip()
                        chunks.append({
                            "text": chunk_text,
                            "hierarchy": hierarchy,
                            "token_count": current_tokens
                        })
                    
                    # Add code block as its own chunk
                    chunks.append({
                        "text": code_block,
                        "hierarchy": hierarchy,
                        "token_count": code_tokens
                    })
                    
                    # Reset for next chunk
                    current_chunk_lines = []
                    current_tokens = 0
                    i = code_end_idx + 1
                    continue
                
                # If adding code block exceeds chunk size, start new chunk
                if current_tokens + code_tokens > self.chunk_size and current_chunk_lines:
                    chunk_text = '\n'.join(current_chunk_lines).strip()
                    chunks.append({
                        "text": chunk_text,
                        "hierarchy": hierarchy,
                        "token_count": current_tokens
                    })
                    
                    # Start new chunk with header context + code block
                    current_chunk_lines = header_lines.copy() if header_lines else []
                    current_chunk_lines.append(code_block)
                    current_tokens = self.count_tokens('\n'.join(current_chunk_lines))
                else:
                    # Add code block to current chunk
                    current_chunk_lines.append(code_block)
                    current_tokens += code_tokens
                
                i = code_end_idx + 1
                continue
            
            # Regular line processing
            line_tokens = self.count_tokens(line)
            
            # If adding line exceeds chunk size, start new chunk
            if current_tokens + line_tokens > self.chunk_size and current_chunk_lines:
                chunk_text = '\n'.join(current_chunk_lines).strip()
                chunks.append({
                    "text": chunk_text,
                    "hierarchy": hierarchy,
                    "token_count": current_tokens
                })
                
                # Start new chunk with overlap
                overlap_lines = self._get_overlap_lines(current_chunk_lines)
                current_chunk_lines = overlap_lines
                current_tokens = self.count_tokens('\n'.join(current_chunk_lines))
            
            current_chunk_lines.append(line)
            current_tokens += line_tokens
            i += 1
        
        # Add final chunk
        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines).strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "hierarchy": hierarchy,
                    "token_count": current_tokens
                })
        
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
    
    def chunk_document(self, file_path: str) -> List[Dict]:
        """
        Chunk document into semantic segments with metadata
        
        This implements a more aggressive chunking strategy:
        1. Read the entire document
        2. Split by headers (H1-H4)
        3. For each section, if it's too large, split it further
        4. Maintain section hierarchy in metadata
        
        Args:
            file_path: Path to documentation file
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        logger.info(f"Starting semantic document chunking: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            logger.error(f"Documentation file not found: {file_path}")
            raise
        
        lines = content.split('\n')
        
        # Find all header positions
        header_positions = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Check for markdown headers (# to ####)
            if re.match(r'^#{1,4}\s+', stripped):
                header_positions.append(i)
        
        logger.info(f"Found {len(header_positions)} headers in document")
        
        # If no headers found, treat entire document as one section
        if not header_positions:
            header_positions = [0]
        
        # Split document into sections
        sections = []
        for i, start_idx in enumerate(header_positions):
            end_idx = header_positions[i + 1] if i + 1 < len(header_positions) else len(lines)
            section_lines = lines[start_idx:end_idx]
            section_text = '\n'.join(section_lines).strip()
            
            if section_text:
                hierarchy = self._extract_section_hierarchy(lines, start_idx)
                sections.append({
                    "text": section_text,
                    "start_idx": start_idx,
                    "hierarchy": hierarchy
                })
        
        logger.info(f"Split document into {len(sections)} sections")
        
        # Now chunk each section
        all_chunks = []
        for section in sections:
            section_tokens = self.count_tokens(section["text"])
            
            # If section fits in chunk size, use as-is
            if section_tokens <= self.chunk_size:
                all_chunks.append({
                    "text": section["text"],
                    "hierarchy": section["hierarchy"],
                    "token_count": section_tokens
                })
            else:
                # Section is too large, split it further
                logger.info(f"Section '{section['hierarchy']['section_title']}' has {section_tokens} tokens, splitting...")
                sub_chunks = self._split_large_section(section)
                all_chunks.extend(sub_chunks)
        
        # Create final chunk objects with metadata
        final_chunks = []
        for i, chunk in enumerate(all_chunks):
            # Skip very small chunks (likely empty sections)
            if chunk["token_count"] < 20:
                continue
            
            hierarchy = chunk["hierarchy"]
            
            # Create chunk metadata
            chunk_obj = {
                "text": chunk["text"],
                "metadata": {
                    "chunk_id": str(uuid.uuid4()),
                    "section_title": hierarchy["section_title"],
                    "api_endpoint": hierarchy["api_endpoint"],
                    "h1": hierarchy["h1"],
                    "h2": hierarchy["h2"],
                    "h3": hierarchy["h3"],
                    "source": "documentation.txt",
                    "chunk_index": i,
                    "token_count": chunk["token_count"]
                }
            }
            
            final_chunks.append(chunk_obj)
        
        logger.info(f"Document chunked into {len(final_chunks)} semantic segments")
        return final_chunks
    
    def _split_large_section(self, section: Dict) -> List[Dict]:
        """
        Split a large section into smaller chunks while preserving context
        
        This uses a sliding window approach with overlap
        """
        text = section["text"]
        hierarchy = section["hierarchy"]
        lines = text.split('\n')
        
        chunks = []
        current_chunk_lines = []
        current_tokens = 0
        
        # Extract header lines (first few lines that contain headers)
        header_lines = []
        for line in lines[:5]:
            if re.match(r'^#{1,4}\s+', line.strip()) or line.strip().startswith('##'):
                header_lines.append(line)
        
        # Always start with headers
        if header_lines:
            current_chunk_lines.extend(header_lines)
            current_tokens = self.count_tokens('\n'.join(header_lines))
        
        i = len(header_lines)
        while i < len(lines):
            line = lines[i]
            line_tokens = self.count_tokens(line)
            
            # Check if adding this line would exceed chunk size
            if current_tokens + line_tokens > self.chunk_size and current_chunk_lines:
                # Save current chunk
                chunk_text = '\n'.join(current_chunk_lines).strip()
                if chunk_text:
                    chunks.append({
                        "text": chunk_text,
                        "hierarchy": hierarchy,
                        "token_count": current_tokens
                    })
                
                # Start new chunk with overlap
                overlap_lines = self._get_overlap_lines(current_chunk_lines)
                # Also include headers
                if header_lines and header_lines not in [overlap_lines[:len(header_lines)]]:
                    current_chunk_lines = header_lines.copy() + overlap_lines
                else:
                    current_chunk_lines = overlap_lines.copy()
                current_tokens = self.count_tokens('\n'.join(current_chunk_lines))
            
            # Add line to current chunk
            current_chunk_lines.append(line)
            current_tokens += line_tokens
            i += 1
        
        # Add final chunk
        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines).strip()
            if chunk_text and current_tokens > 20:
                chunks.append({
                    "text": chunk_text,
                    "hierarchy": hierarchy,
                    "token_count": current_tokens
                })
        
        logger.info(f"Split large section into {len(chunks)} chunks")
        return chunks


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
    
    return chunks
