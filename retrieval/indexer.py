import re
import math
from typing import List, Dict, Any
from retrieval.chunker import CodeChunk

class RetrievalResult(CodeChunk):
    score: float

class KeywordIndexer:
    """
    Lightweight, in-memory keyword/lexical search index.
    Calculates simple BM25-like scores based on token frequency.
    """
    
    def __init__(self):
        self.chunks: List[CodeChunk] = []
        self.token_freq: Dict[str, int] = {}
        self.total_chunks = 0
        
    def _tokenize(self, text: str) -> List[str]:
        # Simple tokenization: lowercase and extract words/identifiers
        return re.findall(r'[a-zA-Z0-9_]+', text.lower())

    def index(self, chunks: List[CodeChunk]):
        self.chunks.extend(chunks)
        for chunk in chunks:
            self.total_chunks += 1
            # Index file path tokens as well as content tokens
            tokens = set(self._tokenize(chunk.file_path) + self._tokenize(chunk.content))
            for token in tokens:
                self.token_freq[token] = self.token_freq.get(token, 0) + 1

    def search(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        if not self.chunks:
            return []
            
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
            
        # Precompute IDF for query tokens
        idf = {}
        for token in set(query_tokens):
            df = self.token_freq.get(token, 0)
            if df > 0:
                # Basic IDF formula
                idf[token] = math.log(1 + (self.total_chunks - df + 0.5) / (df + 0.5))
            else:
                idf[token] = 0

        results = []
        for chunk in self.chunks:
            chunk_content_tokens = self._tokenize(chunk.content)
            chunk_path_tokens = self._tokenize(chunk.file_path)
            
            # Combine path and content, but give path tokens a higher weight
            chunk_tokens = chunk_content_tokens + chunk_path_tokens * 3
            
            score = 0
            for token in query_tokens:
                if idf.get(token, 0) > 0:
                    tf = chunk_tokens.count(token)
                    if tf > 0:
                        # Simple TF-IDF scoring
                        score += (tf / (tf + 1)) * idf[token]
            
            if score > 0:
                results.append(RetrievalResult(
                    repository=chunk.repository,
                    file_path=chunk.file_path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    score=round(score, 4)
                ))
                
        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
