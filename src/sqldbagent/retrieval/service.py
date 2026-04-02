"""Snapshot retrieval service backed by Qdrant."""

from __future__ import annotations

from pathlib import Path
from re import sub
from typing import Any

import orjson

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import (
    ArtifactSettings,
    EmbeddingSettings,
    LLMSettings,
    RetrievalSettings,
)
from sqldbagent.docs.service import SnapshotDocumentService
from sqldbagent.retrieval.embeddings import build_embeddings
from sqldbagent.retrieval.models import (
    RetrievalIndexManifestModel,
    RetrievalResultModel,
    RetrievedDocumentModel,
)
from sqldbagent.snapshot.models import SnapshotBundleModel
from sqldbagent.snapshot.service import SnapshotService


class SnapshotRetrievalService:
    """Index and retrieve snapshot documents through Qdrant."""

    _PAYLOAD_INDEX_FIELDS = (
        "metadata.datasource_name",
        "metadata.schema_name",
        "metadata.snapshot_id",
        "metadata.artifact_type",
        "metadata.table_name",
        "metadata.view_name",
        "metadata.entity_kind",
        "metadata.source_table",
        "metadata.target_table",
    )

    def __init__(
        self,
        *,
        datasource_name: str,
        snapshotter: SnapshotService,
        document_service: SnapshotDocumentService,
        artifacts: ArtifactSettings,
        embeddings_settings: EmbeddingSettings,
        llm_settings: LLMSettings,
        retrieval_settings: RetrievalSettings,
        embeddings: Any | None = None,
        client: Any | None = None,
    ) -> None:
        """Initialize the retrieval service.

        Args:
            datasource_name: Datasource identifier.
            snapshotter: Snapshot service used to load latest snapshots.
            document_service: Service used to export snapshot documents.
            artifacts: Artifact directory settings.
            embeddings_settings: Embedding backend settings.
            llm_settings: Provider API settings.
            retrieval_settings: Vectorstore settings.
            embeddings: Optional explicit embeddings backend override.
            client: Optional explicit Qdrant client override.
        """

        self._datasource_name = datasource_name
        self._snapshotter = snapshotter
        self._document_service = document_service
        self._artifacts = artifacts
        self._embeddings_settings = embeddings_settings
        self._llm_settings = llm_settings
        self._retrieval_settings = retrieval_settings
        self._embeddings = embeddings
        self._client = client

    def index_snapshot_bundle(
        self,
        bundle: SnapshotBundleModel,
        *,
        recreate_collection: bool = False,
    ) -> RetrievalIndexManifestModel:
        """Index one snapshot bundle into Qdrant.

        Args:
            bundle: Snapshot bundle to index.
            recreate_collection: Whether to recreate the collection first.

        Returns:
            RetrievalIndexManifestModel: Persisted index manifest.
        """

        document_bundle = self._document_service.create_document_bundle(bundle)
        document_bundle_path = self._document_service.save_document_bundle(
            document_bundle
        )
        vector_store = self._ensure_vector_store(
            recreate_collection=recreate_collection
        )
        documents = self._document_service.export_langchain_documents(document_bundle)
        document_ids = [document.document_id for document in document_bundle.documents]
        vector_store.add_documents(documents=documents, ids=document_ids)

        manifest = RetrievalIndexManifestModel(
            datasource_name=self._datasource_name,
            schema_name=bundle.regenerate.schema_name,
            snapshot_id=bundle.snapshot_id,
            collection_name=self._collection_name,
            document_bundle_path=document_bundle_path.as_posix(),
            document_count=len(document_bundle.documents),
            embedding_provider=self._embeddings_settings.provider,
            embedding_model=self._embeddings_settings.model,
            summary=(
                f"Indexed {len(document_bundle.documents)} documents for datasource "
                f"'{self._datasource_name}' schema '{bundle.regenerate.schema_name}' "
                f"into collection '{self._collection_name}'."
            ),
        )
        self._save_manifest(manifest)
        return manifest

    def index_latest_schema_snapshot(
        self,
        schema_name: str,
        *,
        recreate_collection: bool = False,
    ) -> RetrievalIndexManifestModel:
        """Index the latest saved snapshot for one schema.

        Args:
            schema_name: Schema name to index.
            recreate_collection: Whether to recreate the collection first.

        Returns:
            RetrievalIndexManifestModel: Persisted index manifest.
        """

        bundle = SnapshotService.load_latest_snapshot(
            self._artifacts,
            datasource_name=self._datasource_name,
            schema_name=schema_name,
        )
        return self.index_snapshot_bundle(
            bundle,
            recreate_collection=recreate_collection,
        )

    def retrieve(
        self,
        query: str,
        *,
        schema_name: str | None = None,
        table_name: str | None = None,
        snapshot_id: str | None = None,
        artifact_types: list[str] | None = None,
        limit: int | None = None,
    ) -> RetrievalResultModel:
        """Retrieve relevant schema context from Qdrant.

        Args:
            query: Retrieval query.
            schema_name: Optional schema filter.
            table_name: Optional table filter.
            snapshot_id: Optional snapshot filter.
            artifact_types: Optional artifact-type filters.
            limit: Optional result limit override.

        Returns:
            RetrievalResultModel: Retrieval result payload.
        """

        vector_store = self._ensure_vector_store(recreate_collection=False)
        result_limit = limit or self._retrieval_settings.default_top_k
        qdrant_filter = self._build_filter(
            schema_name=schema_name,
            table_name=table_name,
            snapshot_id=snapshot_id,
            artifact_types=artifact_types,
        )
        if self._retrieval_settings.use_mmr:
            documents = vector_store.max_marginal_relevance_search(
                query,
                k=result_limit,
                fetch_k=max(result_limit, self._retrieval_settings.default_fetch_k),
                filter=qdrant_filter,
                score_threshold=self._retrieval_settings.score_threshold,
            )
            retrieved = [
                RetrievedDocumentModel(
                    document_id=getattr(document, "id", "") or "",
                    page_content=document.page_content,
                    metadata=document.metadata,
                    summary=self._summarize_document(document.page_content),
                )
                for document in documents
            ]
        else:
            documents = vector_store.similarity_search_with_score(
                query,
                k=result_limit,
                filter=qdrant_filter,
                score_threshold=self._retrieval_settings.score_threshold,
            )
            retrieved = [
                RetrievedDocumentModel(
                    document_id=getattr(document, "id", "") or "",
                    page_content=document.page_content,
                    metadata=document.metadata,
                    score=score,
                    summary=self._summarize_document(document.page_content),
                )
                for document, score in documents
            ]

        summary = (
            f"Retrieved {len(retrieved)} documents from collection "
            f"'{self._collection_name}' for datasource '{self._datasource_name}'."
        )
        return RetrievalResultModel(
            query=query,
            datasource_name=self._datasource_name,
            schema_name=schema_name,
            table_name=table_name,
            snapshot_id=snapshot_id,
            collection_name=self._collection_name,
            documents=retrieved,
            summary=summary,
        )

    @staticmethod
    def load_manifest(path: str | Path) -> RetrievalIndexManifestModel:
        """Load a saved retrieval manifest."""

        return RetrievalIndexManifestModel.model_validate(
            orjson.loads(Path(path).read_bytes())
        )

    @property
    def manifest_dir(self) -> Path:
        """Return the retrieval-manifest root directory."""

        return Path(self._artifacts.root_dir) / self._artifacts.vectorstores_dir

    @property
    def _collection_name(self) -> str:
        """Return the generated Qdrant collection name."""

        raw = (
            f"{self._retrieval_settings.collection_prefix}__"
            f"{self._datasource_name}__"
            f"{self._embeddings_settings.provider}__"
            f"{self._embeddings_settings.model}"
        )
        return sub(r"[^a-zA-Z0-9_]+", "_", raw).strip("_").lower()

    def _save_manifest(self, manifest: RetrievalIndexManifestModel) -> Path:
        """Persist one retrieval manifest to disk."""

        path = (
            self.manifest_dir
            / manifest.datasource_name
            / manifest.schema_name
            / f"{manifest.snapshot_id}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            orjson.dumps(
                manifest.model_dump(mode="json"),
                option=orjson.OPT_INDENT_2,
            )
        )
        return path

    def _ensure_vector_store(self, *, recreate_collection: bool) -> Any:
        """Return a ready-to-use LangChain Qdrant vector store."""

        qdrant_module = require_dependency("langchain_qdrant", "langchain-qdrant")
        client = self._get_client()
        embeddings = self._get_embeddings()
        if recreate_collection:
            self._create_collection(force_recreate=True)
        elif not client.collection_exists(self._collection_name):
            self._create_collection(force_recreate=False)

        return qdrant_module.QdrantVectorStore(
            client=client,
            collection_name=self._collection_name,
            embedding=embeddings,
        )

    def _create_collection(self, *, force_recreate: bool) -> None:
        """Create the Qdrant collection if it does not exist."""

        qdrant_models = require_dependency("qdrant_client", "qdrant-client").models
        vector_size = len(self._get_embeddings().embed_query("sqldbagent bootstrap"))
        vector_params = qdrant_models.VectorParams(
            size=vector_size,
            distance=qdrant_models.Distance.COSINE,
        )
        client = self._get_client()
        if force_recreate:
            if client.collection_exists(self._collection_name):
                client.delete_collection(self._collection_name)
            client.create_collection(
                self._collection_name,
                vectors_config=vector_params,
                on_disk_payload=True,
            )
        elif not client.collection_exists(self._collection_name):
            client.create_collection(
                self._collection_name,
                vectors_config=vector_params,
                on_disk_payload=True,
            )

        if self._retrieval_settings.create_payload_indexes:
            for field_name in self._PAYLOAD_INDEX_FIELDS:
                client.create_payload_index(
                    self._collection_name,
                    field_name,
                    qdrant_models.PayloadSchemaType.KEYWORD,
                )

    def _build_filter(
        self,
        *,
        schema_name: str | None,
        table_name: str | None,
        snapshot_id: str | None,
        artifact_types: list[str] | None,
    ) -> Any:
        """Build a Qdrant payload filter for retrieval."""

        qdrant_models = require_dependency("qdrant_client", "qdrant-client").models
        conditions: list[Any] = [
            qdrant_models.FieldCondition(
                key="metadata.datasource_name",
                match=qdrant_models.MatchValue(value=self._datasource_name),
            )
        ]
        if schema_name is not None:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="metadata.schema_name",
                    match=qdrant_models.MatchValue(value=schema_name),
                )
            )
        if table_name is not None:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="metadata.table_name",
                    match=qdrant_models.MatchValue(value=table_name),
                )
            )
        if snapshot_id is not None:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="metadata.snapshot_id",
                    match=qdrant_models.MatchValue(value=snapshot_id),
                )
            )
        if artifact_types:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="metadata.artifact_type",
                    match=qdrant_models.MatchAny(any=artifact_types),
                )
            )
        return qdrant_models.Filter(must=conditions)

    def _get_client(self) -> Any:
        """Return the configured Qdrant client."""

        if self._client is None:
            client_module = require_dependency("qdrant_client", "qdrant-client")
            self._client = client_module.QdrantClient(
                url=self._retrieval_settings.qdrant_url,
                api_key=self._retrieval_settings.qdrant_api_key,
                grpc_port=self._retrieval_settings.qdrant_grpc_port,
                prefer_grpc=self._retrieval_settings.qdrant_prefer_grpc,
                check_compatibility=False,
            )
        return self._client

    def _get_embeddings(self) -> Any:
        """Return the configured embeddings backend."""

        if self._embeddings is None:
            self._embeddings = build_embeddings(
                embeddings_settings=self._embeddings_settings,
                llm_settings=self._llm_settings,
                artifacts=self._artifacts,
            )
        return self._embeddings

    @staticmethod
    def _summarize_document(page_content: str) -> str:
        """Return a short preview for one retrieved document."""

        first_line = page_content.splitlines()[0] if page_content else ""
        return first_line[:160]
