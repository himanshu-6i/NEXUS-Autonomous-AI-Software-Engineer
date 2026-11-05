import logging
from models.reviewer import ReviewerRequest, ReviewerResponse
from workspace.manager import workspace_manager, WorkspaceError
from services.prompt_orchestrator import PromptOrchestrator
from services.github_service import github_service

logger = logging.getLogger(__name__)

class ReviewerAgent:
    def run_review(self, request: ReviewerRequest) -> ReviewerResponse:
        repo_id = github_service._parse_repo_url(request.repository)
        workspace_id = request.workspace_id
        logger.info(f"Reviewer Agent started for workspace={workspace_id}, repo={repo_id}")
        
        # Verify workspace exists
        workspace_manager.get_workspace_path(workspace_id)
        
        # Gather Context
        planner_context = request.planner_result.model_dump_json(indent=2)
        diff_context = request.diff
        
        test_context = "No test results provided."
        if request.final_test_result:
            test_context = request.final_test_result.model_dump_json(indent=2)
            
        # Retrieve relevant files for context
        # We read the changed files from the workspace so the LLM sees the final code state.
        context_parts = []
        for file_path in request.changed_files:
            try:
                content = workspace_manager.read_file(workspace_id, file_path)
                context_parts.append(f"--- FILE (Modified): {file_path} ---\n{content}\n")
            except WorkspaceError:
                pass
                
        retrieved_context = "\n".join(context_parts) if context_parts else "No specific files retrieved."
        
        # Generate Review via LLM
        review_report = PromptOrchestrator.run_reviewer(
            repo_name=repo_id,
            task=request.task,
            planner_context=planner_context,
            diff_context=diff_context,
            test_context=test_context,
            retrieved_context=retrieved_context
        )
        
        # Implement deterministic backend verdict rules.
        # DO NOT blindly trust the LLM. 
        verdict = review_report.verdict
        
        # Rule 1: If tests failed or timed out, it cannot be APPROVED.
        if request.final_test_result and request.final_test_result.status in ["failed", "error", "timeout", "dependencies_unavailable"]:
            if verdict == "approve":
                logger.warning("LLM tried to approve but tests failed. Forcing BLOCK.")
                verdict = "block"
                review_report.summary += "\n\n[SYSTEM INJECTED]: Tests are failing. Approval blocked."
                
        # Rule 2: If there are critical security findings, it must be BLOCK.
        has_critical = any(f.severity == 'critical' for f in review_report.findings)
        if has_critical and verdict != "block":
            logger.warning("Critical finding detected. Forcing BLOCK.")
            verdict = "block"
            review_report.summary += "\n\n[SYSTEM INJECTED]: Critical security findings detected. Approval blocked."
            
        # Repackage response
        return ReviewerResponse(
            workspace_id=workspace_id,
            verdict=verdict,
            overall_score=review_report.overall_score,
            correctness_score=review_report.correctness_score,
            test_score=review_report.test_score,
            maintainability_score=review_report.maintainability_score,
            security_score=review_report.security_score,
            scope_score=review_report.scope_score,
            findings=review_report.findings,
            summary=review_report.summary,
            recommendations=review_report.recommendations,
            unknowns=review_report.unknowns
        )

reviewer_agent = ReviewerAgent()
