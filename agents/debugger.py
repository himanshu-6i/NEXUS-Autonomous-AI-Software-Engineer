import logging
import json
from models.debugger import DebuggerRequest, DebuggerResponse, DebuggerAttemptState
from models.tester import TesterRequest
from workspace.manager import workspace_manager, WorkspaceError
from services.prompt_orchestrator import PromptOrchestrator
from services.github_service import github_service
from agents.tester import tester_agent

logger = logging.getLogger(__name__)

MAX_DEBUG_RETRIES = 3

class DebuggerAgent:
    
    def run_debug_loop(self, request: DebuggerRequest) -> DebuggerResponse:
        repo_id = github_service._parse_repo_url(request.repository)
        workspace_id = request.workspace_id
        logger.info(f"Debugger Agent started for workspace={workspace_id}, repo={repo_id}")
        
        # Verify workspace exists
        workspace_manager.get_workspace_path(workspace_id)
        
        attempt_history = []
        warnings = []
        unknowns = []
        
        current_test_result = request.test_result
        attempt = request.retry_count
        
        final_diff = ""
        final_diagnosis = ""
        files_changed = []
        status = "debugging_failed"
        
        # We assume if the initial test result was 'passed', there's nothing to debug
        if current_test_result.status == 'passed':
            return DebuggerResponse(
                status="fixed",
                workspace_id=workspace_id,
                attempts=attempt,
                final_test_status="passed",
                diagnosis="Initial tests passed, no debugging required.",
                files_changed=[],
                attempt_history=[],
                final_diff="",
                warnings=[],
                unknowns=[]
            )
            
        while attempt < MAX_DEBUG_RETRIES:
            logger.info(f"Debugger Attempt {attempt + 1}/{MAX_DEBUG_RETRIES}")
            
            # 1. Gather context
            # Get failure details
            test_result_context = current_test_result.model_dump_json(indent=2)
            
            # Retrieve relevant files (we just fetch everything that failed tests touch, plus changed_files)
            files_to_read = set()
            for ts in current_test_result.tests_selected:
                # Add test files
                for arg in ts.command.arguments:
                    if not arg.startswith("-"):
                        files_to_read.add(arg)
                        
            for f in current_test_result.failures:
                if f.file: files_to_read.add(f.file)
                
            # If no files found from failures, fallback to reading some code or unknowns.
            # In a real system, we'd use retrieval_service. For prototype, we'll try to read test targets.
            
            context_parts = []
            for file_path in files_to_read:
                try:
                    content = workspace_manager.read_file(workspace_id, file_path)
                    context_parts.append(f"--- FILE: {file_path} ---\n{content}\n")
                except WorkspaceError:
                    pass
                    
            retrieved_context = "\n".join(context_parts) if context_parts else "No specific files retrieved."
            
            history_context = json.dumps([h.model_dump() for h in attempt_history], indent=2)
            
            # 2. Call PromptOrchestrator to get Fix
            fix_response = PromptOrchestrator.run_debugger(
                repo_name=repo_id,
                task=request.task,
                test_result_context=test_result_context,
                retrieved_context=retrieved_context,
                history_context=history_context
            )
            
            final_diagnosis = fix_response.diagnosis
            unknowns.extend(fix_response.unknowns)
            
            # Check for repeated failure states (same diagnosis/files changed)
            if attempt_history and fix_response.diagnosis == attempt_history[-1].diagnosis:
                status = "repeated_failure"
                warnings.append("Debugger is oscillating/repeating. Stopping early.")
                break
                
            # 3. Apply Fix safely
            workspace_manager.begin_transaction(workspace_id)
            attempt_files_changed = []
            apply_failed = False
            
            try:
                for change in fix_response.changes:
                    if change.operation == 'create' or change.operation == 'modify':
                        if change.new_content is None:
                            raise WorkspaceError(f"Missing new_content for {change.operation}")
                        workspace_manager.write_file(workspace_id, change.file_path, change.new_content)
                        attempt_files_changed.append(change.file_path)
                    elif change.operation == 'delete':
                        workspace_manager.delete_file(workspace_id, change.file_path)
                        attempt_files_changed.append(change.file_path)
                    else:
                        raise WorkspaceError(f"Unknown operation: {change.operation}")
                        
                final_diff = workspace_manager.generate_diff(workspace_id)
                
            except WorkspaceError as we:
                logger.error(f"Validation/Apply failed during debug: {we}. Rolling back.")
                workspace_manager.rollback_transaction(workspace_id)
                status = "unsafe_fix"
                warnings.append(str(we))
                apply_failed = True
                
            if apply_failed:
                break
                
            files_changed.extend(attempt_files_changed)
            
            # 4. Run Tests again
            tester_req = TesterRequest(
                workspace_id=workspace_id,
                repository=request.repository,
                task=request.task,
                changed_files=attempt_files_changed
            )
            
            try:
                new_test_result = tester_agent.run_tests(tester_req)
            except Exception as e:
                logger.error(f"Test Agent failed during debug loop: {e}")
                workspace_manager.rollback_transaction(workspace_id)
                break
                
            # 5. Evaluate Result
            attempt_state = DebuggerAttemptState(
                attempt=attempt + 1,
                failure_class=fix_response.failure_class,
                diagnosis=fix_response.diagnosis,
                files_changed=attempt_files_changed,
                test_status=new_test_result.status
            )
            attempt_history.append(attempt_state)
            
            if new_test_result.status == 'passed':
                workspace_manager.commit_transaction(workspace_id)
                status = "fixed"
                current_test_result = new_test_result
                attempt += 1
                break
                
            # If it failed again, check if it got worse (e.g., more failures)
            prev_fails = current_test_result.execution.tests_failed if current_test_result.execution and isinstance(current_test_result.execution.tests_failed, int) else 999
            new_fails = new_test_result.execution.tests_failed if new_test_result.execution and isinstance(new_test_result.execution.tests_failed, int) else 999
            
            if new_fails > prev_fails:
                logger.info("Fix made tests worse. Rolling back.")
                workspace_manager.rollback_transaction(workspace_id)
                warnings.append("Fix worsened test results. Rolled back attempt.")
                attempt += 1
                break
                
            workspace_manager.commit_transaction(workspace_id)
            current_test_result = new_test_result
            attempt += 1
            
        if attempt >= MAX_DEBUG_RETRIES and status not in ["fixed", "repeated_failure", "unsafe_fix"]:
            status = "max_retries_reached"
            
        return DebuggerResponse(
            status=status,
            workspace_id=workspace_id,
            attempts=attempt,
            final_test_status=current_test_result.status,
            diagnosis=final_diagnosis or "Failed to diagnose.",
            files_changed=list(set(files_changed)),
            attempt_history=attempt_history,
            final_diff=final_diff,
            warnings=warnings,
            unknowns=unknowns
        )

debugger_agent = DebuggerAgent()
