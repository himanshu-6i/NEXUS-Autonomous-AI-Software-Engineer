import logging
import re
from typing import Optional
from models.pr import PRRequest, PRResponse
from workspace.manager import workspace_manager
from services.github_service import github_service
from utils.secret_scanner import SecretScanner, SecretScannerError

logger = logging.getLogger(__name__)

class PRAgentError(Exception):
    pass

class PRAgent:
    def run_pr_workflow(self, request: PRRequest) -> PRResponse:
        logger.info(f"PR Agent started for workspace={request.workspace_id}, repo={request.repository}")
        
        if not request.confirm:
            raise PRAgentError("User confirmation is required to create a PR.")
        
        # 1. Authoritative Backend Approval Gates
        if request.final_test_result.status != "passed":
            raise PRAgentError("PR blocked: Final tests must pass before creating a PR.")
            
        if request.review_result.verdict != "approve":
            raise PRAgentError("PR blocked: Reviewer verdict must be 'approve' before creating a PR.")
            
        if not request.changed_files:
            raise PRAgentError("PR blocked: No files were changed.")
            
        # 2. Get Workspace
        workspace_root = workspace_manager.get_workspace_path(request.workspace_id)
        
        # 3. Secret Scanning
        try:
            SecretScanner.scan_files(workspace_root, request.changed_files)
        except SecretScannerError as e:
            logger.error(f"Secret Scanner blocked PR: {str(e)}")
            raise PRAgentError(f"Security check failed: {str(e)}")
            
        # 4. Determine Repo Metadata
        repo_metadata = github_service.get_repo_metadata(request.repository)
        base_branch = repo_metadata.default_branch
        base_sha = repo_metadata.latest_commit_sha
        
        # 5. Sanitize Branch Name
        raw_branch = f"nexus/{request.workspace_id}"
        branch_name = re.sub(r'[^a-zA-Z0-9_\-\/]', '_', raw_branch)
        if ".." in branch_name or "//" in branch_name:
            raise PRAgentError("Invalid branch name generated.")
            
        # 6. Generate Commit Message safely (using the task title)
        # Prevent prompt injection in the commit message by strictly formatting it
        safe_task_title = request.task.split("\n")[0][:60]
        safe_task_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', safe_task_title)
        commit_message = f"feat(nexus): {safe_task_title}\n\nAutomated commit by NEXUS."
        
        # 7. Create Branch
        github_service.create_branch(
            repo_url=request.repository,
            new_branch=branch_name,
            base_sha=base_sha
        )
        
        # 8. Create Commit
        commit_sha = github_service.create_commit_from_workspace(
            repo_url=request.repository,
            branch=branch_name,
            base_sha=base_sha,
            commit_message=commit_message,
            changed_files=request.changed_files,
            workspace_root=workspace_root
        )
        
        # 9. Format PR Body
        pr_body = f"## Summary\nNEXUS Automated Implementation for: {safe_task_title}\n\n"
        pr_body += f"## Tests\nTest Status: PASSED\n"
        pr_body += f"## Review\nReview Verdict: APPROVE (Score: {request.review_result.overall_score}/100)\n\n"
        pr_body += f"## Changed Files\n"
        for f in request.changed_files:
            pr_body += f"- `{f}`\n"
            
        # 10. Create PR
        pr_url = github_service.create_pull_request(
            repo_url=request.repository,
            title=f"NEXUS Implementation: {safe_task_title}",
            body=pr_body,
            head_branch=branch_name,
            base_branch=base_branch
        )
        
        return PRResponse(
            workspace_id=request.workspace_id,
            repository=request.repository,
            branch_name=branch_name,
            commit_sha=commit_sha,
            pr_url=pr_url,
            status="created"
        )

pr_agent = PRAgent()
