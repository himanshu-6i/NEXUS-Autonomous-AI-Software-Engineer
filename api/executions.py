import logging
import uuid
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.execution import ExecutionState, ExecutionEvent
from services.firestore_service import firestore_service, FirestoreServiceError

router = APIRouter(prefix="/api/executions", tags=["executions"])
logger = logging.getLogger(__name__)

class CreateExecutionRequest(BaseModel):
    repository: str
    task: str

@router.post("", response_model=ExecutionState)
async def create_execution(request: CreateExecutionRequest):
    execution_id = f"exec_{uuid.uuid4().hex[:12]}"
    # Usually workspace_id matches execution_id for simplicity
    workspace_id = f"nexus_workspace_{execution_id}"
    
    execution = ExecutionState(
        execution_id=execution_id,
        workspace_id=workspace_id,
        repository=request.repository,
        task=request.task,
        status="created",
        current_stage="created"
    )
    
    try:
        firestore_service.create_execution(execution)
        firestore_service.append_event(ExecutionEvent(
            event_type="execution_created",
            execution_id=execution_id,
            stage="created",
            metadata={"repository": request.repository}
        ))
        return execution
    except FirestoreServiceError as e:
        logger.error(f"Failed to create execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[ExecutionState])
async def list_executions(limit: int = 50):
    try:
        return firestore_service.list_executions(limit=limit)
    except FirestoreServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{execution_id}", response_model=ExecutionState)
async def get_execution(execution_id: str):
    try:
        execution = firestore_service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        return execution
    except FirestoreServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{execution_id}/events", response_model=List[ExecutionEvent])
async def get_execution_events(execution_id: str):
    try:
        return firestore_service.get_execution_events(execution_id)
    except FirestoreServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
