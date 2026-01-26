"""Document chunking service with semantic preservation"""

import re
import uuid
from typing import List, Dict, Optional, Tuple
import tiktoken

from backend.app.core.config import settings
from backend.app.utils.logger import setup_logger

logger = setup_logger(__name__)


class DocumentChunker:
    """Intelligent semantic document chunker"""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        self.section_markers = [
            r'^#\s+',
            r'^##\s+',
            r'^###\s+',
            r'^####\s+',
        ]
        
    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))
    
    def _is_section_boundary(self, line: str) -> bool:
        line_stripped = line.strip()
        for marker in self.section_markers:
            if re.match(marker, line_stripped):
                return True
        return False
    
    def _extract_section_hierarchy(self, lines: List[str], current_idx: int) -> Dict[str, str]:
        h1_title = "General Documentation"
        h2_title = ""
        h3_title = ""
        api_endpoint = ""
        
        for i in range(current_idx, max(0, current_idx - 50), -1):
            line = lines[i].strip()
            
            if line.startswith("# ") and not h1_title != "General Documentation":
                h1_title = line.lstrip("# ").strip()
            
            elif line.startswith("## ") and not h2_title:
                h2_title = line.lstrip("## ").strip()
                endpoint_match = re.search(r'\[(/[^\]]+)\]', h2_title)
                if endpoint_match:
                    api_endpoint = endpoint_match.group(1)
            
            elif line.startswith("### ") and not h3_title:
                h3_title = line.lstrip("### ").strip()
            
            elif line.startswith("+ [") and not api_endpoint:
                endpoint_match = re.search(r'\[([^\]]+)\]', line)
                if endpoint_match:
                    potential_endpoint = endpoint_match.group(1)
                    if potential_endpoint.startswith("/") or potential_endpoint.startswith("reference/"):
                        api_endpoint = potential_endpoint
        
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
        if not endpoint:
            return ""
        
        endpoint = re.sub(r'^reference/', '', endpoint)
        endpoint = endpoint.strip().lower()
        
        return endpoint
    
    def _detect_code_block(self, line: str) -> Tuple[bool, Optional[str]]:
        stripped = line.strip()
        
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or "text"
            return True, lang
        
        if stripped == "{" or stripped.startswith("{"):
            return True, "json"
        
        if stripped == "[" or stripped.startswith("[{"):
            return True, "json"
            
        return False, None
    
    def _find_code_block_end(self, lines: List[str], start_idx: int, code_type: str) -> int:
        if code_type and code_type != "json":
            for i in range(start_idx + 1, len(lines)):
                if lines[i].strip().startswith("```"):
                    return i
            return len(lines) - 1
        
        if code_type == "json":
            brace_count = 0
            bracket_count = 0
            in_block = False
            
            for i in range(start_idx, len(lines)):
                line = lines[i]
                
                brace_count += line.count('{') - line.count('}')
                bracket_count += line.count('[') - line.count(']')
                
                if brace_count > 0 or bracket_count > 0:
                    in_block = True
                
                if in_block and brace_count == 0 and bracket_count == 0:
                    return i
            
            return len(lines) - 1
        
        return start_idx
    
    def chunk_document(self, file_path: str) -> List[Dict]:
        """Chunk document into semantic segments with metadata"""
        logger.info(f"Starting semantic document chunking: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            logger.error(f"Documentation file not found: {file_path}")
            raise
        
        lines = content.split('\n')
        
        header_positions = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^#{1,4}\s+', stripped):
                header_positions.append(i)
        
        logger.info(f"Found {len(header_positions)} headers in document")
        
        if not header_positions:
            header_positions = [0]
        
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
        
        all_chunks = []
        for section in sections:
            section_tokens = self.count_tokens(section["text"])
            
            if section_tokens <= self.chunk_size:
                all_chunks.append({
                    "text": section["text"],
                    "hierarchy": section["hierarchy"],
                    "token_count": section_tokens
                })
            else:
                logger.info(f"Section '{section['hierarchy']['section_title']}' has {section_tokens} tokens, splitting...")
                sub_chunks = self._split_large_section(section)
                all_chunks.extend(sub_chunks)
        
        final_chunks = []
        for i, chunk in enumerate(all_chunks):
            if chunk["token_count"] < 20:
                continue
            
            hierarchy = chunk["hierarchy"]
            
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
        text = section["text"]
        hierarchy = section["hierarchy"]
        lines = text.split('\n')
        
        chunks = []
        current_chunk_lines = []
        current_tokens = 0
        
        header_lines = []
        for line in lines[:5]:
            if re.match(r'^#{1,4}\s+', line.strip()) or line.strip().startswith('##'):
                header_lines.append(line)
        
        if header_lines:
            current_chunk_lines.extend(header_lines)
            current_tokens = self.count_tokens('\n'.join(header_lines))
        
        i = len(header_lines)
        while i < len(lines):
            line = lines[i]
            line_tokens = self.count_tokens(line)
            
            if current_tokens + line_tokens > self.chunk_size and current_chunk_lines:
                chunk_text = '\n'.join(current_chunk_lines).strip()
                if chunk_text:
                    chunks.append({
                        "text": chunk_text,
                        "hierarchy": hierarchy,
                        "token_count": current_tokens
                    })
                
                overlap_lines = self._get_overlap_lines(current_chunk_lines)
                if header_lines and header_lines not in [overlap_lines[:len(header_lines)]]:
                    current_chunk_lines = header_lines.copy() + overlap_lines
                else:
                    current_chunk_lines = overlap_lines.copy()
                current_tokens = self.count_tokens('\n'.join(current_chunk_lines))
            
            current_chunk_lines.append(line)
            current_tokens += line_tokens
            i += 1
        
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
    
    def _get_overlap_lines(self, lines: List[str]) -> List[str]:
        overlap_text = '\n'.join(lines)
        overlap_tokens = self.count_tokens(overlap_text)
        
        result = []
        tokens = 0
        for line in reversed(lines):
            line_tokens = self.count_tokens(line)
            if tokens + line_tokens > self.chunk_overlap:
                break
            result.insert(0, line)
            tokens += line_tokens
        
        return result


def chunk_documentation(file_path: str = None) -> List[Dict]:
    if file_path is None:
        file_path = settings.documentation_path
    
    chunker = DocumentChunker()
    chunks = chunker.chunk_document(file_path)
    
    return chunks
