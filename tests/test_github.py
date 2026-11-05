import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

os.environ["GEMINI_API_KEY"] = "mock_api_key"

from api.main import app
from services.github_service import GitHubServiceError

client = TestClient(app)

def test_parse_repo_url():
    from services.github_service import github_service
    assert github_service._parse_repo_url("https://github.com/facebook/react") == "facebook/react"
    assert github_service._parse_repo_url("facebook/react") == "facebook/react"
    assert github_service._parse_repo_url("https://github.com/owner/repo.git") == "owner/repo"
    
    with pytest.raises(GitHubServiceError):
        github_service._parse_repo_url("invalid_url")

@patch("services.github_service.Github")
@patch("services.prompt_orchestrator.PromptOrchestrator.run_repo_analysis")
def test_analyze_repo_success(mock_run_repo_analysis, mock_github_class):
    # Mock GitHub
    mock_github_instance = MagicMock()
    mock_github_class.return_value = mock_github_instance
    
    mock_repo = MagicMock()
    mock_repo.name = "react"
    mock_repo.owner.login = "facebook"
    mock_repo.default_branch = "main"
    mock_repo.description = "A declarative, efficient, and flexible JavaScript library for building user interfaces."
    mock_repo.private = False
    mock_repo.language = "JavaScript"
    mock_repo.html_url = "https://github.com/facebook/react"
    mock_repo.get_branch.return_value.commit.sha = "mock_sha"
    mock_github_instance.get_repo.return_value = mock_repo
    
    # Mock tree
    mock_tree_element1 = MagicMock()
    mock_tree_element1.path = "package.json"
    mock_tree_element1.type = "blob"
    
    mock_tree_element2 = MagicMock()
    mock_tree_element2.path = "node_modules/bad_file.js"
    mock_tree_element2.type = "blob"
    
    mock_tree_element3 = MagicMock()
    mock_tree_element3.path = "src"
    mock_tree_element3.type = "tree"
    
    mock_git_tree = MagicMock()
    mock_git_tree.tree = [mock_tree_element1, mock_tree_element2, mock_tree_element3]
    mock_repo.get_git_tree.return_value = mock_git_tree
    
    # Needs to be re-initialized because the module already initialized github_service singleton
    from services.github_service import github_service
    github_service.client = mock_github_instance
    
    # Mock Gemini Analysis
    from models.analysis import StructuredRepoAnalysisResponse
    mock_run_repo_analysis.return_value = StructuredRepoAnalysisResponse(
        repository="react",
        project_type="Library",
        languages=["JavaScript"],
        frameworks=["React"],
        structure=["src/"],
        entry_points=["src/index.js"],
        test_frameworks=["Jest"],
        package_managers=["npm"],
        important_files=["package.json"],
        architecture_summary="A UI library.",
        detected_commands=["npm install"],
        unknowns=[]
    )
    
    response = client.post("/api/github/analyze", json={"repository": "facebook/react"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["name"] == "react"
    assert "package.json" in data["structure"]
    assert "src/" in data["structure"]
    assert "node_modules/bad_file.js" not in data["structure"]  # Ensure filtering worked
    assert data["analysis"]["project_type"] == "Library"

@patch("services.github_service.Github")
def test_analyze_repo_not_found(mock_github_class):
    mock_github_instance = MagicMock()
    mock_github_class.return_value = mock_github_instance
    
    from github import GithubException
    mock_github_instance.get_repo.side_effect = GithubException(status=404, data={"message": "Not Found"})
    
    from services.github_service import github_service
    github_service.client = mock_github_instance
    
    response = client.post("/api/github/analyze", json={"repository": "invalid/repo"})
    
    assert response.status_code == 400
    assert "Not Found" in response.json()["detail"]
