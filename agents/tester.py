import logging
import re
from typing import List, Tuple
from models.tester import TesterRequest, StructuredTestReport, TestExecutionResult, TestFailure
from workspace.manager import workspace_manager, WorkspaceError
from workspace.runner import test_runner, RunnerError
from services.prompt_orchestrator import PromptOrchestrator
from services.github_service import github_service

logger = logging.getLogger(__name__)

class TestAgent:
    
    def _parse_test_output(self, framework: str, output: str, exit_code: int, duration_ms: int) -> Tuple[TestExecutionResult, List[TestFailure]]:
        """Parses common test output into structured metrics."""
        result = TestExecutionResult(
            exit_code=exit_code,
            duration_ms=duration_ms,
            tests_run="unknown",
            tests_passed="unknown",
            tests_failed="unknown",
            tests_skipped="unknown"
        )
        failures = []
        
        # Very basic regex parsing for prototype
        if "pytest" in framework.lower() or "python" in framework.lower():
            # Example pytest output: "== 2 failed, 1 passed, 1 warnings in 0.12s =="
            # Or short: "1 passed in 0.01s"
            passed = 0
            failed = 0
            skipped = 0
            
            passed_match = re.search(r'(\d+)\s+passed', output)
            if passed_match: passed = int(passed_match.group(1))
            
            failed_match = re.search(r'(\d+)\s+failed', output)
            if failed_match: failed = int(failed_match.group(1))
                
            skipped_match = re.search(r'(\d+)\s+skipped', output)
            if skipped_match: skipped = int(skipped_match.group(1))
                
            if passed_match or failed_match:
                result.tests_passed = passed
                result.tests_failed = failed
                result.tests_skipped = skipped
                result.tests_run = passed + failed + skipped
                
            if exit_code != 0 and result.tests_failed == "unknown" and result.tests_passed == "unknown":
                # Fallback
                result.tests_failed = 1
                result.tests_run = 1
                failures.append(TestFailure(test="unknown", message="Process failed or timed out"))
                
            # Naive failure extraction
            if failed > 0:
                failures.append(TestFailure(
                    test="pytest_failure",
                    message="See output for detailed traceback."
                ))
                
        # Default fallback
        if result.tests_run == "unknown":
            if exit_code == 0:
                result.tests_passed = 1
                result.tests_failed = 0
                result.tests_run = 1
            else:
                result.tests_failed = 1
                result.tests_passed = 0
                result.tests_run = 1
                failures.append(TestFailure(test="unknown", message="Process exited with non-zero code"))
                
        return result, failures

    def run_tests(self, request: TesterRequest) -> StructuredTestReport:
        logger.info(f"Test Agent started for workspace={request.workspace_id}")
        
        warnings = []
        unknowns = []
        
        try:
            # 1. Validate Workspace
            workspace_root = workspace_manager.get_workspace_path(request.workspace_id)
            
            # 2. Inspect Repository / Detect Framework via LLM
            # We fetch a quick file tree of the workspace to let Gemini decide the framework
            import os
            tree = []
            for root, dirs, files in os.walk(workspace_root):
                for f in files:
                    rel_path = os.path.relpath(os.path.join(root, f), workspace_root)
                    if ".git" not in rel_path and "node_modules" not in rel_path and "__pycache__" not in rel_path:
                        tree.append(rel_path)
                        
            # 3. Ask Prompt Orchestrator for Selection
            selection_response = PromptOrchestrator.run_test_selection(
                changed_files=request.changed_files,
                repo_tree=tree
            )
            
            unknowns.extend(selection_response.unknowns)
            
            # 4. Execute Tests
            if not selection_response.selections:
                return StructuredTestReport(
                    workspace_id=request.workspace_id,
                    status="error",
                    framework=selection_response.framework,
                    tests_selected=[],
                    output="No tests selected by the agent."
                )
                
            # We'll run the first selection for this prototype
            selection = selection_response.selections[0]
            
            try:
                import time
                start = time.time()
                exit_code, output = test_runner.execute(request.workspace_id, selection.command)
                duration_ms = int((time.time() - start) * 1000)
                
                # 5. Parse Results
                exec_result, failures = self._parse_test_output(
                    framework=selection_response.framework,
                    output=output,
                    exit_code=exit_code,
                    duration_ms=duration_ms
                )
                
                if exit_code == 124:
                    status = "timeout"
                elif exit_code == 0:
                    status = "passed"
                else:
                    status = "failed"
                    
                return StructuredTestReport(
                    workspace_id=request.workspace_id,
                    status=status,
                    framework=selection_response.framework,
                    tests_selected=[selection],
                    execution=exec_result,
                    failures=failures,
                    warnings=warnings,
                    unknowns=unknowns,
                    output=output
                )
                
            except RunnerError as e:
                warnings.append(str(e))
                return StructuredTestReport(
                    workspace_id=request.workspace_id,
                    status="error",
                    framework=selection_response.framework,
                    tests_selected=[selection],
                    warnings=warnings,
                    unknowns=unknowns,
                    output=f"Runner Error: {e}"
                )
                
        except WorkspaceError as e:
            logger.error(f"Workspace error in Test Agent: {e}")
            raise e
        except Exception as e:
            logger.exception("Unexpected error in Test Agent")
            raise e

tester_agent = TestAgent()
