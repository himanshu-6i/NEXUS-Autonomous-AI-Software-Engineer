import logging
from models.planner import PlannerRequest, StructuredPlanResponse, RetrievedSource
from services.retrieval_service import retrieval_service
from services.prompt_orchestrator import PromptOrchestrator
from services.github_service import github_service

logger = logging.getLogger(__name__)

class PlannerAgent:
    """
    Coordinates repository retrieval and the Gemini service to produce a structured implementation plan.
    """
    
    def plan_task(self, request: PlannerRequest) -> StructuredPlanResponse:
        logger.info(f"Planner Agent started for repo={request.repository} task_length={len(request.task)}")
        
        # 1. Input Validation is partially handled by Pydantic models.
        # But we verify repo exists by parsing it.
        repo_id = github_service._parse_repo_url(request.repository)
        
        # 2. Retrieve Repository Context
        # A smart planner could do multiple queries. For this prototype, we'll use the task string.
        # We limit the task length for the query or extract keywords.
        query = request.task[:200]
        
        logger.info(f"Retrieving context for query: {query}")
        retrieved_chunks = retrieval_service.retrieve(request.repository, query, top_k=10)
        logger.info(f"Retrieved {len(retrieved_chunks)} chunks for context.")
        
        # 3. Call Prompt Orchestrator -> Gemini
        plan = PromptOrchestrator.run_planner(
            repo_name=repo_id,
            task=request.task,
            retrieved_chunks=retrieved_chunks
        )
        
        # 4. Attach Retrieval Sources
        # To maintain source grounding, we map the retrieved chunks to the schema's RetrievedSource type
        sources = []
        for chunk in retrieved_chunks:
            sources.append(
                RetrievedSource(
                    file_path=chunk.file_path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line
                )
            )
        plan.retrieved_sources = sources
        
        logger.info("Planner Agent successfully generated plan.")
        return plan

planner_agent = PlannerAgent()
