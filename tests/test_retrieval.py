import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

os.environ["GEMINI_API_KEY"] = "mock_api_key"

from api.main import app
from retrieval.chunker import chunker
from retrieval.indexer import KeywordIndexer, CodeChunk
from services.retrieval_service import retrieval_service

client = TestClient(app)

def test_chunker():
    content = "line 1\nline 2\nline 3\nline 4\nline 5\n"
    # Setting small chunk size for testing overlap
    chunker.max_lines_per_chunk = 3
    chunker.overlap_lines = 1
    
    chunks = chunker.chunk_file("repo", "test.py", content)
    
    assert len(chunks) == 2
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3
    assert "line 3" in chunks[0].content
    
    assert chunks[1].start_line == 3 # Overlaps line 3
    assert chunks[1].end_line == 5
    assert "line 3" in chunks[1].content
    
    # Restore defaults
    chunker.max_lines_per_chunk = 50
    chunker.overlap_lines = 10

def test_indexer():
    indexer = KeywordIndexer()
    chunks = [
        CodeChunk(repository="repo", file_path="auth.py", start_line=1, end_line=10, content="def login(user, password): pass"),
        CodeChunk(repository="repo", file_path="main.py", start_line=1, end_line=10, content="def start(): pass")
    ]
    indexer.index(chunks)
    
    results = indexer.search("login user auth", top_k=5)
    assert len(results) == 1
    assert results[0].file_path == "auth.py"
    assert results[0].score > 0
    
    results_empty = indexer.search("nothing", top_k=5)
    assert len(results_empty) == 0

@patch("services.retrieval_service.github_service.setup_temporary_workspace")
@patch("os.walk")
@patch("os.path.getsize")
@patch("builtins.open", new_callable=MagicMock)
def test_retrieval_service(mock_open, mock_getsize, mock_walk, mock_setup_ws):
    mock_setup_ws.return_value = "/tmp/mock_workspace"
    mock_walk.return_value = [
        ("/tmp/mock_workspace", [], ["auth.py", "bad.exe"]),
    ]
    mock_getsize.return_value = 100 # Small file
    
    # Mock file read
    mock_file = MagicMock()
    mock_file.__enter__.return_value.read.return_value = "def login(): pass"
    mock_open.return_value = mock_file
    
    # Needs to be re-initialized because the module already initialized retrieval_service singleton
    retrieval_service.indexes = {}
    
    # Build index
    indexer = retrieval_service.build_index_for_repo("facebook/react")
    
    assert len(indexer.chunks) == 1
    assert indexer.chunks[0].file_path == "auth.py" # bad.exe should be filtered
    
    # Search
    results = retrieval_service.retrieve("facebook/react", "login")
    assert len(results) == 1
    assert results[0].file_path == "auth.py"

@patch("services.retrieval_service.RetrievalService.retrieve")
def test_retrieve_api(mock_retrieve):
    from retrieval.indexer import RetrievalResult
    mock_retrieve.return_value = [
        RetrievalResult(
            repository="facebook/react",
            file_path="src/auth.js",
            start_line=10,
            end_line=20,
            content="function authenticate() {}",
            score=0.95
        )
    ]
    
    response = client.post("/api/repository/retrieve", json={
        "repository": "facebook/react",
        "query": "authenticate",
        "top_k": 5
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "authenticate"
    assert len(data["results"]) == 1
    assert data["results"][0]["file_path"] == "src/auth.js"
    assert data["results"][0]["score"] == 0.95
