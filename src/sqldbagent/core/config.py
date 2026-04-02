"""Pydantic settings and datasource configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from sqldbagent.core.enums import Dialect
from sqldbagent.core.errors import ConfigurationError


class PoolSettings(BaseModel):
    """Database pool settings.

    Attributes:
        size: Base pool size for sync engine usage.
        max_overflow: Additional overflow connections allowed above `size`.
        timeout_seconds: Time to wait for a pooled connection.
    """

    model_config = ConfigDict(extra="forbid")

    size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=5, ge=0)
    timeout_seconds: float = Field(default=30.0, gt=0)


class SafetySettings(BaseModel):
    """Default SQL safety policy settings.

    Attributes:
        read_only: Whether execution paths should default to read-only behavior.
        statement_timeout_seconds: Default execution timeout.
        max_rows: Default maximum row count for user-facing query surfaces.
        allowed_schemas: Optional schema allowlist enforced by higher layers.
    """

    model_config = ConfigDict(extra="forbid")

    read_only: bool = True
    statement_timeout_seconds: float = Field(default=30.0, gt=0)
    max_rows: int = Field(default=500, ge=1)
    allowed_schemas: list[str] = Field(default_factory=list)


class ProfilingSettings(BaseModel):
    """Default profiling settings.

    Attributes:
        default_sample_size: Default number of sample rows.
        max_sample_size: Maximum sample rows allowed by default tooling.
        exact_unique_counts: Whether generic profilers should compute exact unique counts.
    """

    model_config = ConfigDict(extra="forbid")

    default_sample_size: int = Field(default=5, ge=1)
    max_sample_size: int = Field(default=50, ge=1)
    exact_unique_counts: bool = True


class ArtifactSettings(BaseModel):
    """Artifact persistence settings.

    Attributes:
        root_dir: Base directory for generated artifacts.
        snapshots_dir: Snapshot subdirectory under `root_dir`.
        documents_dir: Document-export subdirectory under `root_dir`.
        diagrams_dir: Diagram-export subdirectory under `root_dir`.
        prompts_dir: Prompt-export subdirectory under `root_dir`.
        prompt_enhancements_dir: Prompt-enhancement subdirectory under `root_dir`.
        embeddings_cache_dir: Embedding cache subdirectory under `root_dir`.
        vectorstores_dir: Retrieval/vectorstore manifest subdirectory under `root_dir`.
    """

    model_config = ConfigDict(extra="forbid")

    root_dir: str = "var/sqldbagent"
    snapshots_dir: str = "snapshots"
    documents_dir: str = "documents"
    diagrams_dir: str = "diagrams"
    prompts_dir: str = "prompts"
    prompt_enhancements_dir: str = "prompt-enhancements"
    embeddings_cache_dir: str = "embeddings-cache"
    vectorstores_dir: str = "vectorstores"


class EmbeddingSettings(BaseModel):
    """Embedding-provider settings.

    Attributes:
        provider: Embedding backend identifier.
        model: Provider-specific embedding model name.
        dimensions: Optional embedding dimensionality override.
        batch_size: Batch size used by embedding providers when supported.
        cache_query_embeddings: Whether query embeddings should also be cached.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    provider: Literal["openai", "hash"] = "openai"
    model: str = "text-embedding-3-large"
    dimensions: int | None = Field(default=None, ge=8)
    batch_size: int = Field(default=128, ge=1)
    cache_query_embeddings: bool = True


class RetrievalSettings(BaseModel):
    """Retrieval and vectorstore settings.

    Attributes:
        backend: Retrieval backend identifier.
        qdrant_url: Base Qdrant HTTP URL.
        qdrant_api_key: Optional Qdrant API key.
        qdrant_grpc_port: Qdrant gRPC port when gRPC transport is enabled.
        qdrant_prefer_grpc: Whether to prefer gRPC transport.
        collection_prefix: Prefix used when generating Qdrant collection names.
        default_top_k: Default number of documents returned from retrieval.
        default_fetch_k: Fetch pool size used by MMR retrieval.
        use_mmr: Whether retrievers should prefer MMR over plain similarity.
        score_threshold: Optional score threshold applied to retrieval.
        create_payload_indexes: Whether payload indexes should be created in Qdrant.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    backend: Literal["qdrant"] = "qdrant"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_QDRANT_API_KEY", "QDRANT_API_KEY"),
    )
    qdrant_grpc_port: int = Field(default=6334, ge=1)
    qdrant_prefer_grpc: bool = False
    collection_prefix: str = "sqldbagent"
    default_top_k: int = Field(default=6, ge=1)
    default_fetch_k: int = Field(default=24, ge=1)
    use_mmr: bool = True
    score_threshold: float | None = None
    create_payload_indexes: bool = True


class LLMSettings(BaseModel):
    """Optional model-provider settings.

    Attributes:
        default_provider: Default provider identifier for future LLM features.
        default_model: Default model name for future LLM features.
        reasoning_effort: Default reasoning effort for supported reasoning models.
        openai_api_key: Optional OpenAI API key loaded from the environment.
        openai_base_url: Optional OpenAI-compatible base URL.
        anthropic_api_key: Optional Anthropic API key loaded from the environment.
        anthropic_base_url: Optional Anthropic base URL override.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    default_provider: str | None = "openai"
    default_model: str | None = "gpt-5.2"
    reasoning_effort: str | None = "xhigh"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    openai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_OPENAI_BASE_URL", "OPENAI_BASE_URL"),
    )
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"
        ),
    )
    anthropic_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_ANTHROPIC_BASE_URL", "ANTHROPIC_BASE_URL"
        ),
    )


class LangSmithSettings(BaseModel):
    """LangSmith tracing and project settings.

    Attributes:
        tracing: Whether LangSmith tracing is enabled for supported surfaces.
        project: LangSmith project name used for traces.
        api_key: Optional LangSmith API key loaded from the environment.
        endpoint: Optional LangSmith API endpoint override.
        workspace_id: Optional LangSmith workspace identifier.
        tags: Default LangSmith trace tags applied across surfaces.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    tracing: bool = False
    project: str = "sqldbagent"
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_API_KEY",
            "LANGSMITH_API_KEY",
        ),
    )
    endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_ENDPOINT",
            "LANGSMITH_ENDPOINT",
        ),
    )
    workspace_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_WORKSPACE_ID",
            "LANGSMITH_WORKSPACE_ID",
        ),
    )
    tags: list[str] = Field(default_factory=lambda: ["sqldbagent"])

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, value: object) -> object:
        """Normalize tag values from env strings or iterables.

        Args:
            value: Raw LangSmith tags value.

        Returns:
            object: Normalized list value for Pydantic parsing.
        """

        if value is None:
            return ["sqldbagent"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class AgentCheckpointSettings(BaseModel):
    """Agent checkpoint persistence settings.

    Attributes:
        backend: Checkpoint backend to use for agent persistence.
        postgres_url: Optional Postgres connection string for LangGraph checkpointing.
        auto_setup: Whether Postgres checkpointer tables should be initialized automatically.
        pipeline: Whether the Postgres saver should use pipelining when supported.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    backend: Literal["memory", "postgres"] = "memory"
    postgres_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_CHECKPOINT_POSTGRES_URL",
            "AGENT_CHECKPOINT_POSTGRES_URL",
            "LANGGRAPH_CHECKPOINT_POSTGRES_URL",
        ),
    )
    auto_setup: bool = True
    pipeline: bool = False


class AgentSettings(BaseModel):
    """Agent orchestration settings.

    Attributes:
        name: Stable agent name for LangChain/LangGraph surfaces.
        include_latest_snapshot_context: Whether agents should inject latest snapshot summaries.
        max_model_calls_per_run: Optional cap for model calls in a single run.
        max_tool_calls_per_run: Optional cap for tool calls in a single run.
        enable_todo_middleware: Whether the LangChain todo middleware should be enabled.
        enable_human_in_the_loop: Whether `safe_query_sql` should require approval middleware.
        enable_summarization_middleware: Whether context summarization middleware is enabled.
        summarization_trigger_fraction: Fractional context threshold for summarization.
        summarization_keep_messages: Number of recent messages to preserve after summarization.
        summarization_model: Optional dedicated model identifier for summarization.
        tool_call_digest_limit: Maximum number of compressed tool-call summaries to retain.
        checkpoint: Agent checkpoint persistence settings.
        enable_prompt_enhancements: Whether dynamic prompts should merge saved
            prompt-enhancement artifacts.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = "sqldbagent"
    include_latest_snapshot_context: bool = True
    max_model_calls_per_run: int | None = Field(default=8, ge=1)
    max_tool_calls_per_run: int | None = Field(default=24, ge=1)
    enable_todo_middleware: bool = True
    enable_human_in_the_loop: bool = False
    enable_summarization_middleware: bool = False
    summarization_trigger_fraction: float = Field(default=0.9, gt=0, le=1)
    summarization_keep_messages: int = Field(default=20, ge=1)
    summarization_model: str | None = None
    tool_call_digest_limit: int = Field(default=10, ge=1)
    checkpoint: AgentCheckpointSettings = Field(default_factory=AgentCheckpointSettings)
    enable_prompt_enhancements: bool = True


class MCPSettings(BaseModel):
    """FastMCP server settings.

    Attributes:
        transport: Default MCP transport to serve.
        host: Default host for HTTP-based transports.
        port: Default port for HTTP-based transports.
        path: Default HTTP path for streamable transports.
        log_level: Default FastMCP/Uvicorn log level for HTTP transports.
        show_banner: Whether the FastMCP banner should be shown on startup.
        stateless_http: Whether streamable HTTP should run in stateless mode.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    transport: Literal["stdio", "http", "sse", "streamable-http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1)
    path: str = "/mcp"
    log_level: str = "info"
    show_banner: bool = True
    stateless_http: bool = False


class DatasourceSettings(BaseModel):
    """Single datasource definition.

    Attributes:
        name: Stable datasource identifier used by services and adapters.
        dialect: Database dialect used by the datasource.
        url: SQLAlchemy-compatible connection URL.
        echo: Whether SQLAlchemy should emit SQL logs.
        pool: Pool configuration for this datasource.
        safety: Default safety policy for this datasource.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    dialect: Dialect
    url: str
    echo: bool = False
    pool: PoolSettings = Field(default_factory=PoolSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate and normalize datasource names.

        Args:
            value: Raw datasource name.

        Returns:
            str: Normalized datasource name.
        """

        normalized = value.strip()
        if not normalized:
            raise ValueError("datasource name must not be empty")
        return normalized


class AppSettings(BaseSettings):
    """Top-level application settings.

    Attributes:
        env: Deployment environment label.
        log_level: Default application log level.
        datasources: Configured datasource definitions.
        datasource_aliases: Optional alias map from short names to datasource names.
        profiling: Default profiling settings.
        artifacts: Artifact persistence settings.
        llm: Optional model-provider settings.
        langsmith: LangSmith tracing settings.
        embeddings: Embedding-provider settings.
        retrieval: Retrieval/vectorstore settings.
        agent: Agent orchestration settings.
        mcp: FastMCP server settings.
    """

    model_config = SettingsConfigDict(
        env_prefix="SQLDBAGENT_",
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    env: str = "dev"
    log_level: str = "INFO"
    datasources: list[DatasourceSettings] = Field(default_factory=list)
    datasource_aliases: dict[str, str] = Field(default_factory=dict)
    profiling: ProfilingSettings = Field(default_factory=ProfilingSettings)
    artifacts: ArtifactSettings = Field(default_factory=ArtifactSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    langsmith: LangSmithSettings = Field(default_factory=LangSmithSettings)
    embeddings: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    default_datasource_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_DEFAULT_DATASOURCE", "DEFAULT_DATASOURCE"
        ),
    )
    default_schema_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_DEFAULT_SCHEMA", "DEFAULT_SCHEMA"),
    )
    llm_default_provider: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LLM_DEFAULT_PROVIDER", "LLM_DEFAULT_PROVIDER"
        ),
        exclude=True,
        repr=False,
    )
    llm_default_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LLM_DEFAULT_MODEL", "LLM_DEFAULT_MODEL"
        ),
        exclude=True,
        repr=False,
    )
    llm_reasoning_effort: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LLM_REASONING_EFFORT", "LLM_REASONING_EFFORT"
        ),
        exclude=True,
        repr=False,
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"),
        exclude=True,
        repr=False,
    )
    openai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_OPENAI_BASE_URL", "OPENAI_BASE_URL"),
        exclude=True,
        repr=False,
    )
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"
        ),
        exclude=True,
        repr=False,
    )
    anthropic_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_ANTHROPIC_BASE_URL", "ANTHROPIC_BASE_URL"
        ),
        exclude=True,
        repr=False,
    )
    langsmith_tracing: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_TRACING",
            "LANGSMITH_TRACING",
        ),
        exclude=True,
        repr=False,
    )
    langsmith_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_PROJECT",
            "LANGSMITH_PROJECT",
        ),
        exclude=True,
        repr=False,
    )
    langsmith_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_API_KEY",
            "LANGSMITH_API_KEY",
        ),
        exclude=True,
        repr=False,
    )
    langsmith_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_ENDPOINT",
            "LANGSMITH_ENDPOINT",
        ),
        exclude=True,
        repr=False,
    )
    langsmith_workspace_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_WORKSPACE_ID",
            "LANGSMITH_WORKSPACE_ID",
        ),
        exclude=True,
        repr=False,
    )
    langsmith_tags: list[str] | str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_LANGSMITH_TAGS",
            "LANGSMITH_TAGS",
        ),
        exclude=True,
        repr=False,
    )
    agent_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_AGENT_NAME", "AGENT_NAME"),
        exclude=True,
        repr=False,
    )
    agent_include_latest_snapshot_context: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_INCLUDE_LATEST_SNAPSHOT_CONTEXT",
            "AGENT_INCLUDE_LATEST_SNAPSHOT_CONTEXT",
        ),
        exclude=True,
        repr=False,
    )
    agent_max_model_calls_per_run: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_MAX_MODEL_CALLS_PER_RUN",
            "AGENT_MAX_MODEL_CALLS_PER_RUN",
        ),
        exclude=True,
        repr=False,
    )
    agent_max_tool_calls_per_run: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_MAX_TOOL_CALLS_PER_RUN",
            "AGENT_MAX_TOOL_CALLS_PER_RUN",
        ),
        exclude=True,
        repr=False,
    )
    agent_enable_todo_middleware: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_ENABLE_TODO_MIDDLEWARE",
            "AGENT_ENABLE_TODO_MIDDLEWARE",
        ),
        exclude=True,
        repr=False,
    )
    agent_enable_human_in_the_loop: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_ENABLE_HUMAN_IN_THE_LOOP",
            "AGENT_ENABLE_HUMAN_IN_THE_LOOP",
        ),
        exclude=True,
        repr=False,
    )
    agent_enable_summarization_middleware: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_ENABLE_SUMMARIZATION_MIDDLEWARE",
            "AGENT_ENABLE_SUMMARIZATION_MIDDLEWARE",
        ),
        exclude=True,
        repr=False,
    )
    agent_summarization_trigger_fraction: float | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_SUMMARIZATION_TRIGGER_FRACTION",
            "AGENT_SUMMARIZATION_TRIGGER_FRACTION",
        ),
        exclude=True,
        repr=False,
    )
    agent_summarization_keep_messages: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_SUMMARIZATION_KEEP_MESSAGES",
            "AGENT_SUMMARIZATION_KEEP_MESSAGES",
        ),
        exclude=True,
        repr=False,
    )
    agent_summarization_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_SUMMARIZATION_MODEL",
            "AGENT_SUMMARIZATION_MODEL",
        ),
        exclude=True,
        repr=False,
    )
    agent_tool_call_digest_limit: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_TOOL_CALL_DIGEST_LIMIT",
            "AGENT_TOOL_CALL_DIGEST_LIMIT",
        ),
        exclude=True,
        repr=False,
    )
    agent_checkpoint_backend: Literal["memory", "postgres"] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_CHECKPOINT_BACKEND",
            "AGENT_CHECKPOINT_BACKEND",
        ),
        exclude=True,
        repr=False,
    )
    agent_checkpoint_postgres_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_CHECKPOINT_POSTGRES_URL",
            "AGENT_CHECKPOINT_POSTGRES_URL",
            "LANGGRAPH_CHECKPOINT_POSTGRES_URL",
        ),
        exclude=True,
        repr=False,
    )
    agent_checkpoint_auto_setup: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_CHECKPOINT_AUTO_SETUP",
            "AGENT_CHECKPOINT_AUTO_SETUP",
        ),
        exclude=True,
        repr=False,
    )
    agent_checkpoint_pipeline: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_AGENT_CHECKPOINT_PIPELINE",
            "AGENT_CHECKPOINT_PIPELINE",
        ),
        exclude=True,
        repr=False,
    )
    qdrant_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_QDRANT_URL", "QDRANT_URL"),
        exclude=True,
        repr=False,
    )
    qdrant_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_QDRANT_API_KEY", "QDRANT_API_KEY"),
        exclude=True,
        repr=False,
    )
    qdrant_grpc_port: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_QDRANT_GRPC_PORT", "QDRANT_GRPC_PORT"
        ),
        exclude=True,
        repr=False,
    )
    qdrant_prefer_grpc: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_QDRANT_PREFER_GRPC", "QDRANT_PREFER_GRPC"
        ),
        exclude=True,
        repr=False,
    )
    embeddings_provider: Literal["openai", "hash"] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_EMBEDDINGS_PROVIDER", "EMBEDDINGS_PROVIDER"
        ),
        exclude=True,
        repr=False,
    )
    embeddings_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_EMBEDDINGS_MODEL", "EMBEDDINGS_MODEL"
        ),
        exclude=True,
        repr=False,
    )
    embeddings_dimensions: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_EMBEDDINGS_DIMENSIONS", "EMBEDDINGS_DIMENSIONS"
        ),
        exclude=True,
        repr=False,
    )
    embeddings_batch_size: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_EMBEDDINGS_BATCH_SIZE", "EMBEDDINGS_BATCH_SIZE"
        ),
        exclude=True,
        repr=False,
    )
    embeddings_cache_query_embeddings: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_EMBEDDINGS_CACHE_QUERY_EMBEDDINGS",
            "EMBEDDINGS_CACHE_QUERY_EMBEDDINGS",
        ),
        exclude=True,
        repr=False,
    )
    sqlite_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_SQLITE_PATH", "SQLITE_PATH"),
    )
    postgres_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_POSTGRES_HOST", "POSTGRES_HOST"),
    )
    postgres_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("SQLDBAGENT_POSTGRES_PORT", "POSTGRES_PORT"),
    )
    postgres_db: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_POSTGRES_DB", "POSTGRES_DB"),
    )
    postgres_user: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_POSTGRES_USER", "POSTGRES_USER"),
    )
    postgres_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_POSTGRES_PASSWORD", "POSTGRES_PASSWORD"
        ),
    )
    postgres_demo_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_POSTGRES_DEMO_HOST", "POSTGRES_DEMO_HOST"
        ),
    )
    postgres_demo_port: int = Field(
        default=5433,
        validation_alias=AliasChoices(
            "SQLDBAGENT_POSTGRES_DEMO_PORT", "POSTGRES_DEMO_PORT"
        ),
    )
    postgres_demo_db: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_POSTGRES_DEMO_DB", "POSTGRES_DEMO_DB"
        ),
    )
    postgres_demo_user: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_POSTGRES_DEMO_USER", "POSTGRES_DEMO_USER"
        ),
    )
    postgres_demo_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SQLDBAGENT_POSTGRES_DEMO_PASSWORD", "POSTGRES_DEMO_PASSWORD"
        ),
    )
    mssql_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_MSSQL_HOST", "MSSQL_HOST"),
    )
    mssql_port: int = Field(
        default=1433,
        validation_alias=AliasChoices("SQLDBAGENT_MSSQL_PORT", "MSSQL_PORT"),
    )
    mssql_database: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_MSSQL_DATABASE", "MSSQL_DATABASE"),
    )
    mssql_user: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_MSSQL_USER", "MSSQL_USER"),
    )
    mssql_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLDBAGENT_MSSQL_PASSWORD", "MSSQL_PASSWORD"),
    )
    mssql_driver: str = Field(
        default="ODBC Driver 18 for SQL Server",
        validation_alias=AliasChoices("SQLDBAGENT_MSSQL_DRIVER", "MSSQL_DRIVER"),
    )

    @field_validator("datasources")
    @classmethod
    def validate_unique_datasources(
        cls, value: list[DatasourceSettings]
    ) -> list[DatasourceSettings]:
        """Reject duplicate datasource names.

        Args:
            value: Configured datasource definitions.

        Returns:
            list[DatasourceSettings]: Validated datasource definitions.
        """

        seen: set[str] = set()
        duplicates: set[str] = set()

        for datasource in value:
            if datasource.name in seen:
                duplicates.add(datasource.name)
            seen.add(datasource.name)

        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate datasource names: {names}")

        return value

    @field_validator("datasource_aliases")
    @classmethod
    def validate_datasource_aliases(cls, value: dict[str, str]) -> dict[str, str]:
        """Validate datasource alias keys and targets.

        Args:
            value: Alias mapping loaded from settings.

        Returns:
            dict[str, str]: Normalized alias mapping.
        """

        normalized: dict[str, str] = {}
        for alias, target in value.items():
            normalized_alias = alias.strip()
            normalized_target = target.strip()
            if not normalized_alias:
                raise ValueError("datasource alias names must not be empty")
            if not normalized_target:
                raise ValueError("datasource alias targets must not be empty")
            normalized[normalized_alias] = normalized_target
        return normalized

    @model_validator(mode="after")
    def build_default_datasources(self) -> "AppSettings":
        """Build convenience datasource definitions from environment fields.

        Returns:
            AppSettings: Settings with synthesized datasources when needed.
        """

        self.llm = self.llm.model_copy(
            update={
                "default_provider": (
                    self.llm.default_provider
                    if self.llm_default_provider is None
                    else self.llm_default_provider
                ),
                "default_model": (
                    self.llm.default_model
                    if self.llm_default_model is None
                    else self.llm_default_model
                ),
                "reasoning_effort": (
                    self.llm.reasoning_effort
                    if self.llm_reasoning_effort is None
                    else self.llm_reasoning_effort
                ),
                "openai_api_key": self.llm.openai_api_key or self.openai_api_key,
                "openai_base_url": self.llm.openai_base_url or self.openai_base_url,
                "anthropic_api_key": self.llm.anthropic_api_key
                or self.anthropic_api_key,
                "anthropic_base_url": self.llm.anthropic_base_url
                or self.anthropic_base_url,
            }
        )
        self.langsmith = self.langsmith.model_copy(
            update={
                "tracing": (
                    self.langsmith.tracing
                    if self.langsmith_tracing is None
                    else self.langsmith_tracing
                ),
                "project": (
                    self.langsmith.project
                    if self.langsmith_project is None
                    else self.langsmith_project
                ),
                "api_key": self.langsmith.api_key or self.langsmith_api_key,
                "endpoint": self.langsmith.endpoint or self.langsmith_endpoint,
                "workspace_id": (
                    self.langsmith.workspace_id or self.langsmith_workspace_id
                ),
                "tags": (
                    self.langsmith.tags
                    if self.langsmith_tags is None
                    else (
                        [
                            item.strip()
                            for item in self.langsmith_tags.split(",")
                            if item.strip()
                        ]
                        if isinstance(self.langsmith_tags, str)
                        else list(self.langsmith_tags)
                    )
                ),
            }
        )
        self.embeddings = self.embeddings.model_copy(
            update={
                "provider": (
                    self.embeddings.provider
                    if self.embeddings_provider is None
                    else self.embeddings_provider
                ),
                "model": (
                    self.embeddings.model
                    if self.embeddings_model is None
                    else self.embeddings_model
                ),
                "dimensions": (
                    self.embeddings.dimensions
                    if self.embeddings_dimensions is None
                    else self.embeddings_dimensions
                ),
                "batch_size": (
                    self.embeddings.batch_size
                    if self.embeddings_batch_size is None
                    else self.embeddings_batch_size
                ),
                "cache_query_embeddings": (
                    self.embeddings.cache_query_embeddings
                    if self.embeddings_cache_query_embeddings is None
                    else self.embeddings_cache_query_embeddings
                ),
            }
        )
        self.retrieval = self.retrieval.model_copy(
            update={
                "qdrant_url": (
                    self.retrieval.qdrant_url
                    if self.qdrant_url is None
                    else self.qdrant_url
                ),
                "qdrant_grpc_port": (
                    self.retrieval.qdrant_grpc_port
                    if self.qdrant_grpc_port is None
                    else self.qdrant_grpc_port
                ),
                "qdrant_prefer_grpc": (
                    self.retrieval.qdrant_prefer_grpc
                    if self.qdrant_prefer_grpc is None
                    else self.qdrant_prefer_grpc
                ),
                "qdrant_api_key": (
                    self.retrieval.qdrant_api_key or self.qdrant_api_key
                ),
            }
        )
        self.agent = self.agent.model_copy(
            update={
                "name": self.agent.name if self.agent_name is None else self.agent_name,
                "include_latest_snapshot_context": (
                    self.agent.include_latest_snapshot_context
                    if self.agent_include_latest_snapshot_context is None
                    else self.agent_include_latest_snapshot_context
                ),
                "max_model_calls_per_run": (
                    self.agent.max_model_calls_per_run
                    if self.agent_max_model_calls_per_run is None
                    else self.agent_max_model_calls_per_run
                ),
                "max_tool_calls_per_run": (
                    self.agent.max_tool_calls_per_run
                    if self.agent_max_tool_calls_per_run is None
                    else self.agent_max_tool_calls_per_run
                ),
                "enable_todo_middleware": (
                    self.agent.enable_todo_middleware
                    if self.agent_enable_todo_middleware is None
                    else self.agent_enable_todo_middleware
                ),
                "enable_human_in_the_loop": (
                    self.agent.enable_human_in_the_loop
                    if self.agent_enable_human_in_the_loop is None
                    else self.agent_enable_human_in_the_loop
                ),
                "enable_summarization_middleware": (
                    self.agent.enable_summarization_middleware
                    if self.agent_enable_summarization_middleware is None
                    else self.agent_enable_summarization_middleware
                ),
                "summarization_trigger_fraction": (
                    self.agent.summarization_trigger_fraction
                    if self.agent_summarization_trigger_fraction is None
                    else self.agent_summarization_trigger_fraction
                ),
                "summarization_keep_messages": (
                    self.agent.summarization_keep_messages
                    if self.agent_summarization_keep_messages is None
                    else self.agent_summarization_keep_messages
                ),
                "summarization_model": (
                    self.agent.summarization_model or self.agent_summarization_model
                ),
                "tool_call_digest_limit": (
                    self.agent.tool_call_digest_limit
                    if self.agent_tool_call_digest_limit is None
                    else self.agent_tool_call_digest_limit
                ),
                "checkpoint": self.agent.checkpoint.model_copy(
                    update={
                        "backend": (
                            self.agent.checkpoint.backend
                            if self.agent_checkpoint_backend is None
                            else self.agent_checkpoint_backend
                        ),
                        "postgres_url": self.agent.checkpoint.postgres_url
                        or self.agent_checkpoint_postgres_url,
                        "auto_setup": (
                            self.agent.checkpoint.auto_setup
                            if self.agent_checkpoint_auto_setup is None
                            else self.agent_checkpoint_auto_setup
                        ),
                        "pipeline": (
                            self.agent.checkpoint.pipeline
                            if self.agent_checkpoint_pipeline is None
                            else self.agent_checkpoint_pipeline
                        ),
                    }
                ),
            }
        )
        if self.agent.checkpoint.postgres_url is None and all(
            (
                self.postgres_host,
                self.postgres_db,
                self.postgres_user,
                self.postgres_password,
            )
        ):
            self.agent = self.agent.model_copy(
                update={
                    "checkpoint": self.agent.checkpoint.model_copy(
                        update={
                            "postgres_url": URL.create(
                                "postgresql+psycopg",
                                username=self.postgres_user,
                                password=self.postgres_password,
                                host=self.postgres_host,
                                port=self.postgres_port,
                                database=self.postgres_db,
                            ).render_as_string(hide_password=False),
                        }
                    )
                }
            )

        if self.datasources:
            self._validate_datasource_alias_targets()
            return self

        datasources: list[DatasourceSettings] = []

        if self.sqlite_path:
            datasources.append(
                DatasourceSettings(
                    name="sqlite",
                    dialect=Dialect.SQLITE,
                    url=f"sqlite+pysqlite:///{self.sqlite_path}",
                )
            )

        if all(
            (
                self.postgres_host,
                self.postgres_db,
                self.postgres_user,
                self.postgres_password,
            )
        ):
            datasources.append(
                DatasourceSettings(
                    name="postgres",
                    dialect=Dialect.POSTGRES,
                    url=URL.create(
                        "postgresql+psycopg",
                        username=self.postgres_user,
                        password=self.postgres_password,
                        host=self.postgres_host,
                        port=self.postgres_port,
                        database=self.postgres_db,
                    ).render_as_string(hide_password=False),
                )
            )

        if all(
            (
                self.postgres_demo_host,
                self.postgres_demo_db,
                self.postgres_demo_user,
                self.postgres_demo_password,
            )
        ):
            datasources.append(
                DatasourceSettings(
                    name="postgres_demo",
                    dialect=Dialect.POSTGRES,
                    url=URL.create(
                        "postgresql+psycopg",
                        username=self.postgres_demo_user,
                        password=self.postgres_demo_password,
                        host=self.postgres_demo_host,
                        port=self.postgres_demo_port,
                        database=self.postgres_demo_db,
                    ).render_as_string(hide_password=False),
                )
            )

        if all(
            (
                self.mssql_host,
                self.mssql_database,
                self.mssql_user,
                self.mssql_password,
            )
        ):
            datasources.append(
                DatasourceSettings(
                    name="mssql",
                    dialect=Dialect.MSSQL,
                    url=URL.create(
                        "mssql+pyodbc",
                        username=self.mssql_user,
                        password=self.mssql_password,
                        host=self.mssql_host,
                        port=self.mssql_port,
                        database=self.mssql_database,
                        query={
                            "driver": self.mssql_driver,
                            "TrustServerCertificate": "yes",
                        },
                    ).render_as_string(hide_password=False),
                )
            )

        self.datasources = datasources
        self._validate_datasource_alias_targets()
        return self

    def _validate_datasource_alias_targets(self) -> None:
        """Ensure datasource aliases point at configured datasources."""

        known_names = {datasource.name for datasource in self.datasources}
        invalid_targets = {
            alias: target
            for alias, target in self.datasource_aliases.items()
            if target not in known_names
        }
        if invalid_targets:
            rendered = ", ".join(
                f"{alias}->{target}"
                for alias, target in sorted(invalid_targets.items())
            )
            raise ValueError(f"unknown datasource alias targets: {rendered}")

    def resolve_datasource_name(self, name: str) -> str:
        """Resolve a datasource name or alias to its canonical datasource name.

        Args:
            name: Datasource name or alias.

        Returns:
            str: Canonical datasource name.
        """

        normalized = name.strip()
        return self.datasource_aliases.get(normalized, normalized)

    def get_datasource(self, name: str) -> DatasourceSettings:
        """Return a datasource by name.

        Args:
            name: Datasource identifier.

        Returns:
            DatasourceSettings: Matching datasource configuration.

        Raises:
            ConfigurationError: If the datasource is unknown.
        """

        resolved_name = self.resolve_datasource_name(name)
        for datasource in self.datasources:
            if datasource.name == resolved_name:
                return datasource

        raise ConfigurationError(f"unknown datasource: {name}")

    def resolve_default_datasource_name(self) -> str:
        """Return the default datasource name for runtime surfaces.

        Returns:
            str: Preferred datasource name.

        Raises:
            ConfigurationError: If no datasources are configured.
        """

        if self.default_datasource_name is not None:
            resolved_name = self.resolve_datasource_name(self.default_datasource_name)
            self.get_datasource(resolved_name)
            return resolved_name

        if not self.datasources:
            raise ConfigurationError("no datasources are configured")

        return self.datasources[0].name


@lru_cache(maxsize=1)
def load_settings() -> AppSettings:
    """Load and cache application settings.

    Returns:
        AppSettings: Cached application settings.
    """

    return AppSettings()
