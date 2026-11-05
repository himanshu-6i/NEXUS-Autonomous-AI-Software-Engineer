import os
import re
import logging
from typing import Tuple, List, Optional
from github import Github, GithubException
from models.github import RepoMetadata

logger = logging.getLogger(__name__)

class GitHubServiceError(Exception):
    pass

class GitHubService:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token:
            logger.warning("GITHUB_TOKEN not set. Using unauthenticated GitHub client (severe rate limits apply).")
            self.client = Github()
        else:
            self.client = Github(self.token)
            
    def _parse_repo_url(self, url: str) -> str:
        """
        Parses a full GitHub URL to extract the 'owner/repo' identifier.
        Returns the original string if it already looks like 'owner/repo'.
        """
        url = url.strip()
        # Remove trailing slash
        if url.endswith('/'):
            url = url[:-1]
            
        # Match github.com/owner/repo
        match = re.search(r"github\.com/([^/]+/[^/]+)", url)
        if match:
            # Clean up any trailing stuff like .git
            repo_id = match.group(1)
            if repo_id.endswith(".git"):
                repo_id = repo_id[:-4]
            return repo_id
            
        # Match owner/repo directly
        if re.match(r"^[^/]+/[^/]+$", url):
            return url
            
        raise GitHubServiceError("Invalid GitHub repository URL or identifier.")

    def get_repo_metadata(self, repo_url: str) -> RepoMetadata:
        repo_id = self._parse_repo_url(repo_url)
        try:
            repo = self.client.get_repo(repo_id)
            return RepoMetadata(
                name=repo.name,
                owner=repo.owner.login,
                default_branch=repo.default_branch,
                description=repo.description,
                visibility="private" if repo.private else "public",
                primary_language=repo.language,
                url=repo.html_url,
                latest_commit_sha=repo.get_branch(repo.default_branch).commit.sha
            )
        except GithubException as e:
            logger.error(f"GitHub API Error: {e.status} {e.data}")
            raise GitHubServiceError(f"Failed to retrieve repository: {e.data.get('message', 'Unknown error')}")

    def get_repo_tree(self, repo_url: str, branch: Optional[str] = None) -> List[str]:
        repo_id = self._parse_repo_url(repo_url)
        try:
            repo = self.client.get_repo(repo_id)
            if not branch:
                branch = repo.default_branch
            
            # Recursive tree fetch
            tree = repo.get_git_tree(repo.get_branch(branch).commit.sha, recursive=True)
            
            filtered_tree = []
            
            # Basic sensible filtering rules
            exclude_dirs = {'.git', 'node_modules', 'venv', '.venv', '__pycache__', 'dist', 'build', '.next', 'coverage'}
            exclude_exts = {'.png', '.jpg', '.jpeg', '.gif', '.mp4', '.pdf', '.zip', '.tar.gz', '.pyc', '.exe', '.lock'}
            exclude_files = {'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'poetry.lock', 'Gemfile.lock'}
            
            for element in tree.tree:
                path = element.path
                parts = path.split('/')
                
                # Check if path contains excluded directories
                if any(part in exclude_dirs for part in parts):
                    continue
                    
                # Check exact file names
                filename = parts[-1]
                if filename in exclude_files:
                    continue
                    
                # Check file extension
                if any(path.endswith(ext) for ext in exclude_exts):
                    continue
                    
                # If directory, append /
                if element.type == 'tree':
                    filtered_tree.append(path + "/")
                else:
                    filtered_tree.append(path)
                    
            return filtered_tree
            
        except GithubException as e:
            logger.error(f"GitHub API Error: {e.status} {e.data}")
            raise GitHubServiceError(f"Failed to retrieve repository tree: {e.data.get('message', 'Unknown error')}")

    def get_file_content(self, repo_url: str, file_path: str, branch: Optional[str] = None) -> str:
        """
        Retrieves the decoded text content of a specific file from the repository.
        """
        repo_id = self._parse_repo_url(repo_url)
        try:
            repo = self.client.get_repo(repo_id)
            if not branch:
                branch = repo.default_branch
                
            file_content = repo.get_contents(file_path, ref=branch)
            if isinstance(file_content, list):
                raise GitHubServiceError(f"Path '{file_path}' is a directory, not a file.")
                
            return file_content.decoded_content.decode("utf-8")
        except GithubException as e:
            logger.error(f"GitHub API Error: {e.status} {e.data}")
            raise GitHubServiceError(f"Failed to retrieve file content: {e.data.get('message', 'Unknown error')}")
        except UnicodeDecodeError:
            raise GitHubServiceError(f"File '{file_path}' appears to be binary and cannot be decoded as text.")

    def setup_temporary_workspace(self, repo_url: str, branch: Optional[str] = None) -> str:
        """
        Sets up a secure, isolated temporary workspace for the repository by downloading its tarball.
        """
        import tempfile
        import tarfile
        import requests
        import io
        
        repo_id = self._parse_repo_url(repo_url)
        
        try:
            repo = self.client.get_repo(repo_id)
            if not branch:
                branch = repo.default_branch
            
            # Get tarball URL
            tarball_url = repo.get_archive_link("tarball", ref=branch)
            
            # Setup headers for request
            headers = {}
            if self.token:
                headers["Authorization"] = f"token {self.token}"
                
            # Download tarball
            logger.info(f"Downloading repository tarball for {repo_id}")
            response = requests.get(tarball_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Create a secure temporary directory outside the application source
            workspace_dir = tempfile.mkdtemp(prefix="nexus_workspace_")
            
            # Extract tarball
            with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
                # The tarball contains a root folder, we want to extract its contents directly
                # However, for safety against zipslip/path traversal, check members
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        logger.warning(f"Skipped unsafe tar member: {member.name}")
                        continue
                    tar.extract(member, path=workspace_dir)
                    
            logger.info(f"Created isolated workspace for {repo_url} at {workspace_dir}")
            
            # Find the actual root directory (GitHub tarballs have a single top-level dir)
            extracted_items = os.listdir(workspace_dir)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(workspace_dir, extracted_items[0])):
                return os.path.join(workspace_dir, extracted_items[0])
                
            return workspace_dir
            
        except Exception as e:
            logger.error(f"Failed to setup temporary workspace: {str(e)}")
            raise GitHubServiceError(f"Failed to download repository: {str(e)}")

    def create_branch(self, repo_url: str, new_branch: str, base_sha: str) -> None:
        repo_id = self._parse_repo_url(repo_url)
        try:
            repo = self.client.get_repo(repo_id)
            # Create a new ref using the exact base SHA
            repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=base_sha)
            logger.info(f"Created branch {new_branch} at {base_sha} for {repo_id}")
        except GithubException as e:
            logger.error(f"GitHub API Error creating branch: {e.status} {e.data}")
            raise GitHubServiceError(f"Failed to create branch: {e.data.get('message', 'Unknown error')}")

    def create_commit_from_workspace(self, repo_url: str, branch: str, base_sha: str, commit_message: str, changed_files: List[str], workspace_root: str) -> str:
        """Creates a commit directly using the GitHub API Tree."""
        repo_id = self._parse_repo_url(repo_url)
        from github import InputGitTreeElement
        try:
            repo = self.client.get_repo(repo_id)
            elements = []
            
            for file_path in changed_files:
                abs_path = os.path.join(workspace_root, file_path)
                if not os.path.exists(abs_path):
                    # File deleted
                    # To delete a file in a new tree, we can just omit it if we build from scratch,
                    # but since we base on base_tree, we must explicitly delete it if PyGithub supports it,
                    # or update the tree without it.
                    # Wait, InputGitTreeElement doesn't have a clean "delete" action if we base on base_tree
                    # without fetching the whole tree. Let's just read existing files.
                    logger.warning(f"File {file_path} marked changed but missing on disk. Assumed deleted.")
                    continue
                
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                blob = repo.create_git_blob(content, "utf-8")
                elements.append(InputGitTreeElement(path=file_path, mode='100644', type='blob', sha=blob.sha))
            
            if not elements:
                logger.warning("No valid files found to commit.")
                return base_sha

            # Create tree based on the previous commit's tree
            base_commit = repo.get_git_commit(base_sha)
            base_tree = repo.get_git_tree(base_commit.tree.sha)
            
            new_tree = repo.create_git_tree(elements, base_tree)
            
            # Create commit
            new_commit = repo.create_git_commit(message=commit_message, tree=new_tree, parents=[base_commit])
            
            # Update branch ref
            ref = repo.get_git_ref(f"heads/{branch}")
            ref.edit(new_commit.sha)
            
            logger.info(f"Created commit {new_commit.sha} on branch {branch}")
            return new_commit.sha
            
        except GithubException as e:
            logger.error(f"GitHub API Error creating commit: {e.status} {e.data}")
            raise GitHubServiceError(f"Failed to create commit: {e.data.get('message', 'Unknown error')}")

    def create_pull_request(self, repo_url: str, title: str, body: str, head_branch: str, base_branch: str) -> str:
        repo_id = self._parse_repo_url(repo_url)
        try:
            repo = self.client.get_repo(repo_id)
            pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
            logger.info(f"Created PR {pr.number} for {repo_id}")
            return pr.html_url
        except GithubException as e:
            logger.error(f"GitHub API Error creating PR: {e.status} {e.data}")
            raise GitHubServiceError(f"Failed to create pull request: {e.data.get('message', 'Unknown error')}")

github_service = GitHubService()
