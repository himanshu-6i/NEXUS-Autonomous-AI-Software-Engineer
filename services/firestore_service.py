import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from models.execution import ExecutionState, ExecutionEvent

logger = logging.getLogger(__name__)

class FirestoreServiceError(Exception):
    pass

class FirestoreService:
    def __init__(self):
        self.use_mock = os.getenv("USE_MOCK_FIRESTORE", "false").lower() == "true"
        self._mock_db: Dict[str, ExecutionState] = {}
        self._mock_events: List[ExecutionEvent] = []
        
        if not self.use_mock:
            try:
                from google.cloud import firestore
                project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
                # Firestore client will auto-detect credentials if deployed on GCP or if GOOGLE_APPLICATION_CREDENTIALS is set
                self.client = firestore.Client(project=project_id) if project_id else firestore.Client()
                logger.info("Initialized real Firestore client.")
            except ImportError:
                logger.warning("google-cloud-firestore not installed. Falling back to in-memory mock.")
                self.use_mock = True
            except Exception as e:
                logger.warning(f"Failed to initialize Firestore ({e}). Falling back to in-memory mock.")
                self.use_mock = True

    def create_execution(self, execution: ExecutionState) -> None:
        execution.updated_at = datetime.now(timezone.utc)
        if self.use_mock:
            self._mock_db[execution.execution_id] = execution
            return

        try:
            doc_ref = self.client.collection("executions").document(execution.execution_id)
            # Exclude None to keep DB clean
            data = execution.model_dump(exclude_none=True)
            doc_ref.set(data)
        except Exception as e:
            logger.error(f"Firestore create_execution failed: {e}")
            raise FirestoreServiceError("Failed to persist execution state.")

    def get_execution(self, execution_id: str) -> Optional[ExecutionState]:
        if self.use_mock:
            return self._mock_db.get(execution_id)

        try:
            doc_ref = self.client.collection("executions").document(execution_id)
            doc = doc_ref.get()
            if doc.exists:
                return ExecutionState(**doc.to_dict())
            return None
        except Exception as e:
            logger.error(f"Firestore get_execution failed: {e}")
            raise FirestoreServiceError("Failed to retrieve execution state.")

    def update_execution(self, execution_id: str, updates: Dict[str, Any]) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        if self.use_mock:
            if execution_id in self._mock_db:
                current_state = self._mock_db[execution_id].model_dump()
                current_state.update(updates)
                self._mock_db[execution_id] = ExecutionState(**current_state)
            return

        try:
            doc_ref = self.client.collection("executions").document(execution_id)
            # Firestore update requires dict
            doc_ref.update(updates)
        except Exception as e:
            logger.error(f"Firestore update_execution failed: {e}")
            raise FirestoreServiceError("Failed to update execution state.")

    def list_executions(self, limit: int = 50) -> List[ExecutionState]:
        if self.use_mock:
            # return sorted by updated_at desc
            results = list(self._mock_db.values())
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[:limit]

        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            docs = self.client.collection("executions").order_by(
                "updated_at", direction="DESCENDING"
            ).limit(limit).stream()
            
            return [ExecutionState(**doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Firestore list_executions failed: {e}")
            raise FirestoreServiceError("Failed to list executions.")

    def append_event(self, event: ExecutionEvent) -> None:
        event.timestamp = datetime.now(timezone.utc)
        if self.use_mock:
            self._mock_events.append(event)
            return

        try:
            # We can store events in a subcollection or a root collection
            doc_ref = self.client.collection("executions").document(event.execution_id).collection("events").document()
            doc_ref.set(event.model_dump(exclude_none=True))
        except Exception as e:
            logger.error(f"Firestore append_event failed: {e}")
            # we don't necessarily raise an error to block the workflow for an event log, but we can log it.
            
    def get_execution_events(self, execution_id: str, limit: int = 100) -> List[ExecutionEvent]:
        if self.use_mock:
            events = [e for e in self._mock_events if e.execution_id == execution_id]
            events.sort(key=lambda x: x.timestamp)
            return events[:limit]

        try:
            docs = self.client.collection("executions").document(execution_id).collection("events").order_by(
                "timestamp", direction="ASCENDING"
            ).limit(limit).stream()
            
            return [ExecutionEvent(**doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Firestore get_execution_events failed: {e}")
            raise FirestoreServiceError("Failed to retrieve execution events.")

firestore_service = FirestoreService()
