import os
import logging
from typing import List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class CodeChunk(BaseModel):
    repository: str
    file_path: str
    start_line: int
    end_line: int
    content: str

class FileChunker:
    """
    Chunks source code files into smaller manageable pieces.
    Implements a line-based chunking strategy as requested.
    """
    
    def __init__(self, max_lines_per_chunk: int = 50, overlap_lines: int = 10):
        self.max_lines_per_chunk = max_lines_per_chunk
        self.overlap_lines = overlap_lines

    def chunk_file(self, repository: str, file_path: str, content: str) -> List[CodeChunk]:
        """Chunks a single file's content based on line limits with overlap."""
        lines = content.splitlines()
        chunks = []
        total_lines = len(lines)
        
        if total_lines == 0:
            return chunks

        start = 0
        while start < total_lines:
            end = min(start + self.max_lines_per_chunk, total_lines)
            
            chunk_content = "\n".join(lines[start:end])
            
            chunks.append(CodeChunk(
                repository=repository,
                file_path=file_path,
                start_line=start + 1,  # 1-indexed
                end_line=end,
                content=chunk_content
            ))
            
            if end == total_lines:
                break
                
            start += (self.max_lines_per_chunk - self.overlap_lines)
            
        return chunks

chunker = FileChunker()
