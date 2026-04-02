"""Service container helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.core.errors import AdapterDependencyError
from sqldbagent.diagrams.service import SchemaDiagramService
from sqldbagent.docs.service import SnapshotDocumentService
from sqldbagent.engines.factory import DatasourceRegistry, EngineManager
from sqldbagent.introspect.base import InspectionService
from sqldbagent.introspect.service import SQLAlchemyInspectionService
from sqldbagent.profile.service import SQLAlchemyProfilingService
from sqldbagent.prompts.service import SnapshotPromptService
from sqldbagent.retrieval.service import SnapshotRetrievalService
from sqldbagent.safety.execution import SafeQueryService
from sqldbagent.safety.guard import QueryGuardService
from sqldbagent.snapshot.service import SnapshotService


@dataclass(slots=True)
class ServiceContainer:
    """Thin container passed into adapter surfaces.

    Attributes:
        inspector: Shared inspection service used by CLI and adapter layers.
        profiler: Shared profiling service used by profiling and snapshot layers.
        query_guard: Shared SQL safety service.
        query_service: Shared guarded query execution service.
        snapshotter: Shared snapshot persistence service.
        diagram_service: Shared schema diagram export service.
        document_service: Shared snapshot document-export service.
        prompt_service: Shared prompt-export service.
        retrieval_service: Shared retrieval service over stored snapshot documents.
        datasource_name: Canonical datasource name backing the container.
        settings: Application settings that built the container.
        engine: Optional SQLAlchemy engine owned by the container.
        async_engine: Optional async SQLAlchemy engine owned by the container.
    """

    inspector: InspectionService
    profiler: SQLAlchemyProfilingService | None = None
    query_guard: QueryGuardService | None = None
    query_service: SafeQueryService | None = None
    snapshotter: SnapshotService | None = None
    diagram_service: SchemaDiagramService | None = None
    document_service: SnapshotDocumentService | None = None
    prompt_service: SnapshotPromptService | None = None
    retrieval_service: SnapshotRetrievalService | None = None
    datasource_name: str | None = None
    settings: AppSettings | None = None
    engine: Engine | None = None
    async_engine: AsyncEngine | None = None

    def close(self) -> None:
        """Dispose owned sync resources.

        When an async engine is present, callers should prefer `aclose()` so the
        async SQLAlchemy engine can shut down cleanly.
        """

        if self.engine is not None:
            self.engine.dispose()

    async def aclose(self) -> None:
        """Dispose owned async resources."""

        if self.async_engine is not None:
            await self.async_engine.dispose()
        if self.engine is not None:
            self.engine.dispose()


def build_service_container(
    datasource_name: str,
    settings: AppSettings | None = None,
    *,
    include_async_engine: bool = False,
) -> ServiceContainer:
    """Build a service container for one datasource.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings. Loaded from environment when omitted.
        include_async_engine: Whether to initialize the async engine as well.

    Returns:
        ServiceContainer: Container with initialized shared services.
    """

    resolved_settings = settings or load_settings()
    canonical_datasource_name = resolved_settings.resolve_datasource_name(
        datasource_name
    )
    datasource = resolved_settings.get_datasource(canonical_datasource_name)
    registry = DatasourceRegistry.from_settings(resolved_settings)
    engine_manager = EngineManager(registry)
    engine = engine_manager.create_sync_engine(canonical_datasource_name)
    async_engine = None
    if include_async_engine:
        async_engine = engine_manager.create_async_engine(canonical_datasource_name)
    inspector = SQLAlchemyInspectionService(engine)
    profiler = SQLAlchemyProfilingService(
        engine=engine,
        inspector=inspector,
        settings=resolved_settings.profiling,
    )
    query_guard = QueryGuardService(
        policy=datasource.safety, dialect=datasource.dialect
    )
    query_service = SafeQueryService(
        engine=engine,
        guard=query_guard,
        async_engine=async_engine,
    )
    snapshotter = SnapshotService(
        datasource_name=canonical_datasource_name,
        inspector=inspector,
        profiler=profiler,
        artifacts=resolved_settings.artifacts,
    )
    diagram_service = SchemaDiagramService(artifacts=resolved_settings.artifacts)
    document_service = SnapshotDocumentService(artifacts=resolved_settings.artifacts)
    prompt_service = SnapshotPromptService(
        artifacts=resolved_settings.artifacts,
        settings=resolved_settings,
    )
    try:
        require_dependency("langchain_qdrant", "langchain-qdrant")
        require_dependency("qdrant_client", "qdrant-client")
        require_dependency("langchain_core.documents", "langchain")
        require_dependency("langchain_classic.embeddings.cache", "langchain")
    except AdapterDependencyError:
        retrieval_service = None
    else:
        retrieval_service = SnapshotRetrievalService(
            datasource_name=canonical_datasource_name,
            snapshotter=snapshotter,
            document_service=document_service,
            artifacts=resolved_settings.artifacts,
            embeddings_settings=resolved_settings.embeddings,
            llm_settings=resolved_settings.llm,
            retrieval_settings=resolved_settings.retrieval,
        )
    return ServiceContainer(
        inspector=inspector,
        profiler=profiler,
        query_guard=query_guard,
        query_service=query_service,
        snapshotter=snapshotter,
        diagram_service=diagram_service,
        document_service=document_service,
        prompt_service=prompt_service,
        retrieval_service=retrieval_service,
        datasource_name=canonical_datasource_name,
        settings=resolved_settings,
        engine=engine,
        async_engine=async_engine,
    )
