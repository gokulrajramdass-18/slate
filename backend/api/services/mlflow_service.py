"""
MLFlow Observability Service

This module provides MLFlow integration for LLM/agent tracking and observability.
Mirrors the LangfuseService architecture with support for local and remote MLFlow tracking servers.

Usage:
    from api.services.mlflow_service import get_mlflow_service

    service = get_mlflow_service()
    run_id = service.create_run(run_name="agent_execution", tags={})

    # Use with LangChain
    callback = service.get_langchain_callback_handler(run_id)
"""

import os
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

# Singleton instance
_mlflow_service: Optional['MLFlowService'] = None


class MLFlowService:
    """
    Centralized service for MLFlow observability integration.

    Provides methods for:
    - Creating experiment runs (equivalent to Langfuse traces)
    - Creating spans for nested operations
    - Logging parameters, metrics, tags, artifacts
    - Getting LangChain callback handlers
    - Graceful degradation when MLFlow is disabled
    """

    def __init__(self):
        """Initialize MLFlow client from environment variables or database settings."""
        self.enabled = os.getenv("MLFLOW_ENABLED", "false").lower() == "true"
        self.verbose = os.getenv("MLFLOW_VERBOSE", "false").lower() == "true"

        self.mlflow_client = None
        self.tracking_uri = None
        self.experiment_name = None
        self.experiment_id = None
        self.active_run = None

        if self.enabled:
            try:
                import mlflow
                from mlflow.tracking import MlflowClient

                # Get configuration
                self.tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
                self.experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "slate-agents")
                username = os.getenv("MLFLOW_USERNAME", "")
                password = os.getenv("MLFLOW_PASSWORD", "")

                # Set tracking URI
                mlflow.set_tracking_uri(self.tracking_uri)

                # Set basic auth if provided
                if username and password:
                    os.environ["MLFLOW_TRACKING_USERNAME"] = username
                    os.environ["MLFLOW_TRACKING_PASSWORD"] = password

                # Create client
                self.mlflow_client = MlflowClient(tracking_uri=self.tracking_uri)

                # Set or create experiment
                try:
                    experiment = mlflow.set_experiment(self.experiment_name)
                    self.experiment_id = experiment.experiment_id

                    if self.verbose:
                        logger.info(
                            f"MLFlow observability initialized "
                            f"(uri={self.tracking_uri}, experiment={self.experiment_name})"
                        )
                except Exception as e:
                    logger.error(f"Failed to set MLFlow experiment: {e}")
                    self.enabled = False

            except ImportError:
                logger.warning("mlflow package not installed. MLFlow observability disabled.")
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize MLFlow: {e}")
                self.enabled = False
        else:
            if self.verbose:
                logger.info("MLFlow observability disabled via MLFLOW_ENABLED=false")

    def is_enabled(self) -> bool:
        """Check if MLFlow observability is enabled."""
        return self.enabled and self.mlflow_client is not None

    def create_run(
        self,
        run_name: str,
        tags: Optional[Dict[str, Any]] = None,
        nested: bool = False
    ) -> Optional[str]:
        """
        Create an MLFlow run (equivalent to Langfuse trace).

        Args:
            run_name: Name for the run
            tags: Additional tags (session_id, notebook_id, agent_type, etc.)
            nested: Whether this is a nested run

        Returns:
            run_id if successful, None if MLFlow is disabled or fails
        """
        if not self.is_enabled():
            return None

        try:
            import mlflow

            # Start run
            run = mlflow.start_run(
                run_name=run_name,
                experiment_id=self.experiment_id,
                nested=nested,
                tags=tags or {}
            )

            run_id = run.info.run_id

            # Store active run reference
            if not nested:
                self.active_run = run_id

            if self.verbose:
                logger.debug(f"Created MLFlow run: {run_id} (name={run_name})")

            return run_id

        except Exception as e:
            logger.error(f"Failed to create MLFlow run: {e}")
            return None

    def end_run(self, run_id: Optional[str] = None, status: str = "FINISHED") -> None:
        """
        End an MLFlow run.

        Args:
            run_id: Run ID to end (uses active run if None)
            status: Run status (FINISHED, FAILED, KILLED)
        """
        if not self.is_enabled():
            return

        try:
            import mlflow

            # End the run
            mlflow.end_run(status=status)

            if self.active_run == run_id:
                self.active_run = None

            if self.verbose:
                logger.debug(f"Ended MLFlow run: {run_id} (status={status})")

        except Exception as e:
            logger.error(f"Failed to end MLFlow run: {e}")

    def log_params(self, run_id: str, params: Dict[str, Any]) -> None:
        """
        Log parameters for a run.

        Args:
            run_id: Run ID
            params: Parameters to log (model, temperature, max_tokens, etc.)
        """
        if not self.is_enabled():
            return

        try:
            import mlflow

            with mlflow.start_run(run_id=run_id):
                for key, value in params.items():
                    # MLFlow params must be strings
                    mlflow.log_param(key, str(value))

            if self.verbose:
                logger.debug(f"Logged {len(params)} parameters to run {run_id}")

        except Exception as e:
            logger.error(f"Failed to log MLFlow parameters: {e}")

    def log_metrics(self, run_id: str, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """
        Log metrics for a run.

        Args:
            run_id: Run ID
            metrics: Metrics to log (tokens, duration, cost, etc.)
            step: Optional step number for time-series metrics
        """
        if not self.is_enabled():
            return

        try:
            import mlflow

            with mlflow.start_run(run_id=run_id):
                for key, value in metrics.items():
                    mlflow.log_metric(key, float(value), step=step)

            if self.verbose:
                logger.debug(f"Logged {len(metrics)} metrics to run {run_id}")

        except Exception as e:
            logger.error(f"Failed to log MLFlow metrics: {e}")

    def set_tags(self, run_id: str, tags: Dict[str, Any]) -> None:
        """
        Set tags for a run.

        Args:
            run_id: Run ID
            tags: Tags to set (status, agent_type, etc.)
        """
        if not self.is_enabled():
            return

        try:
            import mlflow

            with mlflow.start_run(run_id=run_id):
                for key, value in tags.items():
                    mlflow.set_tag(key, str(value))

            if self.verbose:
                logger.debug(f"Set {len(tags)} tags for run {run_id}")

        except Exception as e:
            logger.error(f"Failed to set MLFlow tags: {e}")

    def log_artifact(self, run_id: str, local_path: str, artifact_path: Optional[str] = None) -> None:
        """
        Log an artifact (file) for a run.

        Args:
            run_id: Run ID
            local_path: Path to local file
            artifact_path: Optional path within artifact store
        """
        if not self.is_enabled():
            return

        try:
            import mlflow

            with mlflow.start_run(run_id=run_id):
                mlflow.log_artifact(local_path, artifact_path)

            if self.verbose:
                logger.debug(f"Logged artifact {local_path} to run {run_id}")

        except Exception as e:
            logger.error(f"Failed to log MLFlow artifact: {e}")

    def get_langchain_callback_handler(self, run_id: Optional[str] = None):
        """
        Get a LangChain callback handler for automatic tracing.

        This handler automatically captures:
        - LLM calls with prompts, completions, and token counts
        - Tool executions with inputs and outputs
        - Chain runs with intermediate steps

        Args:
            run_id: Optional run ID to link callbacks to

        Returns:
            MLFlow LangChain callback handler, or None if MLFlow is disabled
        """
        if not self.is_enabled():
            return None

        try:
            import mlflow
            from mlflow.langchain import autolog

            # Enable auto-logging for LangChain
            autolog()

            if self.verbose:
                logger.debug(f"Created MLFlow LangChain callback handler for run: {run_id}")

            # Note: MLFlow autolog() handles callback creation automatically
            # Return a marker object that indicates MLFlow is active
            return {"mlflow_enabled": True, "run_id": run_id}

        except Exception as e:
            logger.error(f"Failed to create MLFlow LangChain callback handler: {e}")
            return None

    async def get_status(self) -> Dict[str, Any]:
        """
        Get MLFlow service status.

        Returns:
            Status dict with connection state, last run info, storage stats
        """
        if not self.is_enabled():
            return {
                "enabled": False,
                "connected": False,
                "error": "MLFlow is disabled"
            }

        try:
            # Test connection by fetching experiment
            experiment = self.mlflow_client.get_experiment(self.experiment_id)

            if not experiment:
                return {
                    "enabled": True,
                    "connected": False,
                    "error": f"Experiment '{self.experiment_name}' not found"
                }

            # Get recent runs
            runs = self.mlflow_client.search_runs(
                experiment_ids=[self.experiment_id],
                max_results=1,
                order_by=["start_time DESC"]
            )

            last_run_at = None
            total_runs = 0

            if runs:
                last_run_at = datetime.fromtimestamp(runs[0].info.start_time / 1000).isoformat()

            # Get total runs count
            all_runs = self.mlflow_client.search_runs(
                experiment_ids=[self.experiment_id],
                max_results=1000
            )
            total_runs = len(all_runs)

            return {
                "enabled": True,
                "connected": True,
                "tracking_uri": self.tracking_uri,
                "experiment_name": self.experiment_name,
                "experiment_id": self.experiment_id,
                "last_run_at": last_run_at,
                "total_runs": total_runs,
                "error": None
            }

        except Exception as e:
            logger.error(f"Failed to get MLFlow status: {e}")
            return {
                "enabled": True,
                "connected": False,
                "error": str(e)
            }

    def flush(self):
        """
        Flush pending events to MLFlow.

        MLFlow typically auto-flushes, but this can be called explicitly.
        """
        if not self.is_enabled():
            return

        try:
            # MLFlow auto-flushes on end_run, but we can manually end active run if needed
            if self.active_run:
                self.end_run(self.active_run)

            if self.verbose:
                logger.debug("Flushed MLFlow events")

        except Exception as e:
            logger.error(f"Failed to flush MLFlow events: {e}")

    def shutdown(self):
        """
        Shutdown MLFlow client and flush remaining events.

        Call this during application shutdown.
        """
        if not self.is_enabled():
            return

        try:
            self.flush()

            if self.verbose:
                logger.info("MLFlow observability shutdown complete")

        except Exception as e:
            logger.error(f"Error during MLFlow shutdown: {e}")


def get_mlflow_service() -> MLFlowService:
    """
    Get the singleton MLFlow service instance.

    Returns:
        Singleton MLFlowService instance
    """
    global _mlflow_service

    if _mlflow_service is None:
        _mlflow_service = MLFlowService()

    return _mlflow_service


def reset_mlflow_service():
    """
    Reset the singleton instance (useful for testing).
    """
    global _mlflow_service
    _mlflow_service = None
