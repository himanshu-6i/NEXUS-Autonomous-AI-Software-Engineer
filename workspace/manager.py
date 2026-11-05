import os
import shutil
import tempfile
import logging
import difflib
from typing import Dict, List, Optional
from services.github_service import github_service

logger = logging.getLogger(__name__)

class WorkspaceError(Exception):
    pass

class WorkspaceManager:
    """
    Manages isolated temporary workspaces for executing code changes safely.
    Provides a transactional file operation layer with path traversal and size protections.
    """
    
    def __init__(self, max_file_size: int = 1024 * 1024 * 5): # 5MB max
        self.max_file_size = max_file_size
        self.workspaces: Dict[str, str] = {} # mapping workspace_id to absolute path
        # Transactions: workspace_id -> Dict of relative_path -> original content
        # None original content means file didn't exist before transaction
        self._transactions: Dict[str, Dict[str, Optional[str]]] = {}

    def create_workspace(self, repo_url: str) -> str:
        """Downloads the repository and creates an isolated workspace."""
        workspace_dir = github_service.setup_temporary_workspace(repo_url)
        workspace_id = os.path.basename(workspace_dir)
        if not workspace_id.startswith("nexus_workspace_"):
            # Ensure we track the actual root if setup_temporary_workspace returned a subdir
            workspace_id = "nexus_workspace_" + os.urandom(8).hex()
            
        self.workspaces[workspace_id] = workspace_dir
        logger.info(f"Workspace {workspace_id} registered at {workspace_dir}")
        return workspace_id

    def get_workspace_path(self, workspace_id: str) -> str:
        if workspace_id not in self.workspaces:
            raise WorkspaceError(f"Workspace {workspace_id} not found")
        return self.workspaces[workspace_id]

    def _resolve_and_verify_path(self, workspace_id: str, file_path: str) -> str:
        """
        Safely resolves a relative file path against the workspace root.
        Prevents path traversal and symlink escapes.
        """
        workspace_root = self.get_workspace_path(workspace_id)
        
        # Prevent absolute paths
        if os.path.isabs(file_path):
            raise WorkspaceError("Absolute paths are not allowed.")
            
        # Resolve path
        resolved_path = os.path.abspath(os.path.join(workspace_root, file_path))
        
        # Verify it's within the workspace
        if not resolved_path.startswith(workspace_root + os.sep) and resolved_path != workspace_root:
            raise WorkspaceError("Path traversal attempt blocked.")
            
        return resolved_path

    def begin_transaction(self, workspace_id: str):
        """Starts a new transaction for tracking changes."""
        self.get_workspace_path(workspace_id) # ensure it exists
        self._transactions[workspace_id] = {}

    def commit_transaction(self, workspace_id: str):
        """Commits the current transaction (clears the rollback log)."""
        if workspace_id in self._transactions:
            del self._transactions[workspace_id]

    def rollback_transaction(self, workspace_id: str):
        """Rolls back the workspace to the state before the transaction started."""
        if workspace_id not in self._transactions:
            return
            
        changes = self._transactions[workspace_id]
        for rel_path, original_content in changes.items():
            abs_path = self._resolve_and_verify_path(workspace_id, rel_path)
            try:
                if original_content is None:
                    # File was created, so delete it
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                else:
                    # File was modified or deleted, restore content
                    with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(original_content)
            except Exception as e:
                logger.error(f"Rollback failed for {rel_path}: {e}")
                
        del self._transactions[workspace_id]
        logger.info(f"Workspace {workspace_id} rolled back successfully.")

    def _record_original_state(self, workspace_id: str, rel_path: str, abs_path: str):
        """Records the original state of a file in the active transaction."""
        if workspace_id in self._transactions and rel_path not in self._transactions[workspace_id]:
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    self._transactions[workspace_id][rel_path] = f.read()
            else:
                self._transactions[workspace_id][rel_path] = None

    def read_file(self, workspace_id: str, file_path: str) -> str:
        abs_path = self._resolve_and_verify_path(workspace_id, file_path)
        if not os.path.exists(abs_path):
            raise WorkspaceError(f"File {file_path} not found")
        with open(abs_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, workspace_id: str, file_path: str, content: str):
        if len(content) > self.max_file_size:
            raise WorkspaceError("Content exceeds maximum file size limit.")
            
        abs_path = self._resolve_and_verify_path(workspace_id, file_path)
        
        self._record_original_state(workspace_id, file_path, abs_path)
        
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def delete_file(self, workspace_id: str, file_path: str):
        abs_path = self._resolve_and_verify_path(workspace_id, file_path)
        if not os.path.exists(abs_path):
            raise WorkspaceError(f"File {file_path} not found")
            
        self._record_original_state(workspace_id, file_path, abs_path)
        os.remove(abs_path)

    def generate_diff(self, workspace_id: str) -> str:
        """
        Generates a unified diff of all changes made during the current transaction.
        Must be called before committing the transaction.
        """
        if workspace_id not in self._transactions:
            return ""
            
        diff_lines = []
        for rel_path, original_content in self._transactions[workspace_id].items():
            abs_path = self._resolve_and_verify_path(workspace_id, rel_path)
            
            if original_content is None:
                original_lines = []
            else:
                original_lines = original_content.splitlines(keepends=True)
                
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    new_lines = f.readlines()
            else:
                new_lines = []
                
            diff = list(difflib.unified_diff(
                original_lines, 
                new_lines, 
                fromfile=f"a/{rel_path}", 
                tofile=f"b/{rel_path}"
            ))
            diff_lines.extend(diff)
            
        return "".join(diff_lines)

    def cleanup_workspace(self, workspace_id: str):
        if workspace_id in self.workspaces:
            path = self.workspaces[workspace_id]
            
            # Find the actual temp root if nested
            base_dir = path
            while "nexus_workspace_" not in os.path.basename(base_dir) and base_dir != os.path.dirname(base_dir):
                base_dir = os.path.dirname(base_dir)
                
            if os.path.exists(base_dir) and "nexus_workspace_" in base_dir:
                try:
                    shutil.rmtree(base_dir)
                    logger.info(f"Cleaned up workspace {workspace_id}")
                except Exception as e:
                    logger.error(f"Failed to clean up workspace {workspace_id}: {e}")
                    
            del self.workspaces[workspace_id]
            if workspace_id in self._transactions:
                del self._transactions[workspace_id]

workspace_manager = WorkspaceManager()
