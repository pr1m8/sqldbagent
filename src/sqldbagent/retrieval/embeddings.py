"""Embedding provider helpers."""

from __future__ import annotations

from hashlib import blake2b
from math import sqrt
from pathlib import Path
from re import findall, sub
from typing import Any

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import ArtifactSettings, EmbeddingSettings, LLMSettings


class HashEmbeddings:
    """Deterministic local embeddings for offline tests and smoke flows."""

    def __init__(self, *, dimensions: int = 256) -> None:
        """Initialize the hash embeddings backend.

        Args:
            dimensions: Number of output dimensions.
        """

        self._dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents.

        Args:
            texts: Input texts to embed.

        Returns:
            list[list[float]]: Deterministic unit vectors.
        """

        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed one query.

        Args:
            text: Query text.

        Returns:
            list[float]: Deterministic unit vector.
        """

        return self._embed_text(text)

    def _embed_text(self, text: str) -> list[float]:
        """Hash one string into a normalized dense vector."""

        vector = [0.0] * self._dimensions
        tokens = findall(r"[A-Za-z0-9_]+", text.lower()) or [text.lower()]
        for token in tokens:
            digest = blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            magnitude = 0.5 + (int.from_bytes(digest[5:9], "big") / 2**32)
            vector[index] += sign * magnitude
        norm = sqrt(sum(component * component for component in vector))
        if norm == 0:
            return vector
        return [component / norm for component in vector]


def build_embeddings(
    *,
    embeddings_settings: EmbeddingSettings,
    llm_settings: LLMSettings,
    artifacts: ArtifactSettings,
) -> Any:
    """Build a cached embeddings backend.

    Args:
        embeddings_settings: Embedding backend settings.
        llm_settings: Provider API settings.
        artifacts: Artifact directory settings.

    Returns:
        Any: LangChain-compatible embeddings backend.
    """

    underlying = _build_underlying_embeddings(
        embeddings_settings=embeddings_settings,
        llm_settings=llm_settings,
    )
    storage_module = require_dependency(
        "langchain_classic.storage.file_system",
        "langchain",
    )
    embeddings_module = require_dependency(
        "langchain_classic.embeddings.cache",
        "langchain",
    )
    cache_dir = (
        Path(artifacts.root_dir)
        / artifacts.embeddings_cache_dir
        / embeddings_settings.provider
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    namespace_parts = [
        embeddings_settings.provider,
        embeddings_settings.model,
        str(embeddings_settings.dimensions or "default"),
    ]
    namespace = sub(r"[^a-zA-Z0-9_.\-/]+", "_", "__".join(namespace_parts))
    return embeddings_module.CacheBackedEmbeddings.from_bytes_store(
        underlying_embeddings=underlying,
        document_embedding_cache=storage_module.LocalFileStore(cache_dir),
        namespace=namespace,
        batch_size=embeddings_settings.batch_size,
        query_embedding_cache=embeddings_settings.cache_query_embeddings,
        key_encoder="sha256",
    )


def _build_underlying_embeddings(
    *,
    embeddings_settings: EmbeddingSettings,
    llm_settings: LLMSettings,
) -> Any:
    """Build the non-cached embedding implementation."""

    if embeddings_settings.provider == "hash":
        return HashEmbeddings(dimensions=embeddings_settings.dimensions or 256)

    openai_module = require_dependency("langchain_openai", "langchain-openai")
    return openai_module.OpenAIEmbeddings(
        model=embeddings_settings.model,
        dimensions=embeddings_settings.dimensions,
        api_key=llm_settings.openai_api_key,
        base_url=llm_settings.openai_base_url,
        chunk_size=embeddings_settings.batch_size,
    )
