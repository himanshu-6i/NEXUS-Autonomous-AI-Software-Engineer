import logging
import json
from models.coder import CodingRequest, CodingResponse
from workspace.manager import workspace_manager, WorkspaceError
from services.retrieval_service import retrieval_service
from services.prompt_orchestrator import PromptOrchestrator
from services.github_service import github_service

logger = logging.getLogger(__name__)

class CodingAgent:
    
    def run_task(self, request: CodingRequest) -> CodingResponse:
        repo_id = github_service._parse_repo_url(request.repository)
        logger.info(f"Coding Agent started for {repo_id}")
        
        # 1. Create temporary workspace
        workspace_id = workspace_manager.create_workspace(request.repository)
        
        warnings = []
        unknowns = []
        diff = ""
        files_changed = []
        
        try:
            # 2. Retrieve relevant context for the implementation plan
            # Here, we can retrieve specific files mentioned in the plan
            files_to_read = set()
            for mod in request.plan.files_to_modify:
                files_to_read.add(mod.path)
            for step in request.plan.implementation_steps:
                files_to_read.update(step.files)
                
            context_parts = []
            for file_path in files_to_read:
                try:
                    content = workspace_manager.read_file(workspace_id, file_path)
                    context_parts.append(f"--- FILE: {file_path} ---\n{content}\n")
                except WorkspaceError as e:
                    warnings.append(f"Could not read {file_path}: {e}")
                    
            retrieved_context = "\n".join(context_parts)
            plan_context = request.plan.model_dump_json(indent=2)
            
            # 3. Generate Code Changes via PromptOrchestrator
            change_response = PromptOrchestrator.run_coder(
                repo_name=repo_id,
                task=request.task,
                plan_context=plan_context,
                retrieved_context=retrieved_context
            )
            
            unknowns.extend(change_response.unknowns)
            
            # 4. Safe Change Application with Rollback
            workspace_manager.begin_transaction(workspace_id)
            
            try:
                for change in change_response.changes:
                    if change.operation == 'create' or change.operation == 'modify':
                        if change.new_content is None:
                            raise WorkspaceError(f"Missing new_content for {change.operation} on {change.file_path}")
                        workspace_manager.write_file(workspace_id, change.file_path, change.new_content)
                        files_changed.append(change.file_path)
                    elif change.operation == 'delete':
                        workspace_manager.delete_file(workspace_id, change.file_path)
                        files_changed.append(change.file_path)
                    else:
                        raise WorkspaceError(f"Unknown operation: {change.operation}")
                        
                # 5. Generate Diff
                diff = workspace_manager.generate_diff(workspace_id)
                workspace_manager.commit_transaction(workspace_id)
                status = "completed"
                
            except WorkspaceError as we:
                logger.error(f"Validation/Apply failed: {we}. Rolling back.")
                workspace_manager.rollback_transaction(workspace_id)
                status = "rolled_back"
                warnings.append(str(we))
                files_changed = []
                diff = ""
                
        except Exception as e:
            logger.exception("Unexpected error in Coding Agent")
            workspace_manager.cleanup_workspace(workspace_id)
            raise e
            
        return CodingResponse(
            workspace_id=workspace_id,
            status=status,
            files_changed=files_changed,
            diff=diff,
            warnings=warnings,
            unknowns=unknowns
        )

coding_agent = CodingAgent()
