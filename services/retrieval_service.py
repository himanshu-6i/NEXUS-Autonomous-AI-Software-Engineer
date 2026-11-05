import os
import shutil
import logging
from typing import Dict, List
from services.github_service import github_service
from retrieval.chunker import chunker
from retrieval.indexer import KeywordIndexer, RetrievalResult

logger = logging.getLogger(__name__)

class RetrievalService:
    def __init__(self):
        # Very simple in-memory cache mapping repository to its index
        # For a production system this would be a persistent store or proper cache
        self.indexes: Dict[str, KeywordIndexer] = {}
        
    def _is_supported_file(self, filepath: str) -> bool:
        supported_exts = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs', 
            '.cpp', '.c', '.h', '.hpp', '.json', '.yaml', '.yml', '.toml', 
            '.md', '.txt', '.sql', '.html', '.css'
        }
        # Ignore common bad directories
        parts = filepath.split(os.sep)
        ignore_dirs = {'.git', 'node_modules', 'dist', 'build', '.next', '__pycache__', 'venv', '.venv', 'coverage'}
        if any(part in ignore_dirs for part in parts):
            return False
            
        ext = os.path.splitext(filepath)[1].lower()
        if not ext: # Files like Dockerfile, Makefile
            return True
            
        return ext in supported_exts

    def build_index_for_repo(self, repo_url: str) -> KeywordIndexer:
        repo_id = github_service._parse_repo_url(repo_url)
        
        if repo_id in self.indexes:
            logger.info(f"Using cached index for {repo_id}")
            return self.indexes[repo_id]
            
        logger.info(f"Building new index for {repo_id}")
        workspace_dir = github_service.setup_temporary_workspace(repo_url)
        
        indexer = KeywordIndexer()
        all_chunks = []
        
        try:
            for root, _, files in os.walk(workspace_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, workspace_dir)
                    
                    if not self._is_supported_file(rel_path):
                        continue
                        
                    # Enforce file size limit (e.g., skip > 1MB)
                    if os.path.getsize(full_path) > 1024 * 1024:
                        continue
                        
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        chunks = chunker.chunk_file(repo_id, rel_path, content)
                        all_chunks.extend(chunks)
                    except UnicodeDecodeError:
                        # Skip binary or non-utf8 files
                        pass
                    except Exception as e:
                        logger.warning(f"Error reading file {rel_path}: {e}")
            
            indexer.index(all_chunks)
            self.indexes[repo_id] = indexer
            return indexer
        finally:
            # Clean up the temporary workspace to prevent storage leaks
            # Note: the tarball extractor returns a subdir if there's only one, 
            # so we might need to delete its parent. Let's just delete the workspace_dir.
            # wait, if it returned a subdir, the temp dir is the parent of workspace_dir.
            # Let's cleanly remove it.
            try:
                base_dir = workspace_dir
                while "nexus_workspace_" not in os.path.basename(base_dir) and base_dir != os.path.dirname(base_dir):
                    base_dir = os.path.dirname(base_dir)
                if os.path.exists(base_dir) and "nexus_workspace_" in base_dir:
                    shutil.rmtree(base_dir)
                    logger.info(f"Cleaned up workspace {base_dir}")
            except Exception as e:
                logger.error(f"Failed to cleanup workspace {workspace_dir}: {e}")

    def retrieve(self, repo_url: str, query: str, top_k: int = 5) -> List[RetrievalResult]:
        indexer = self.build_index_for_repo(repo_url)
        return indexer.search(query, top_k=top_k)

retrieval_service = RetrievalService()
