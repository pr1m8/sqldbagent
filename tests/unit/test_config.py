"""Configuration tests."""

from pytest import raises

from sqldbagent.core.config import AppSettings, DatasourceSettings
from sqldbagent.core.enums import Dialect
from sqldbagent.core.errors import ConfigurationError


def test_get_datasource_returns_named_datasource() -> None:
    """Return the configured datasource by name."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="warehouse",
                dialect=Dialect.POSTGRES,
                url="postgresql+psycopg://user:pass@localhost/db",
            )
        ]
    )

    datasource = settings.get_datasource("warehouse")

    if datasource.dialect is not Dialect.POSTGRES:
        raise AssertionError(datasource.dialect)


def test_get_datasource_raises_for_unknown_name() -> None:
    """Raise a package error for an unknown datasource."""

    settings = AppSettings(datasources=[])

    with raises(ConfigurationError) as exc_info:
        settings.get_datasource("missing")

    if str(exc_info.value) != "unknown datasource: missing":
        raise AssertionError(str(exc_info.value))


def test_settings_build_convenience_sqlite_datasource() -> None:
    """Synthesize a SQLite datasource from the convenience settings."""

    settings = AppSettings(sqlite_path="var/test/sqldbagent.db")
    datasource = settings.get_datasource("sqlite")

    if datasource.url != "sqlite+pysqlite:///var/test/sqldbagent.db":
        raise AssertionError(datasource.url)


def test_settings_build_convenience_postgres_datasource() -> None:
    """Synthesize a Postgres datasource from convenience settings."""

    password = "-".join(["sqldbagent", "test", "password"])
    settings = AppSettings(
        postgres_host="127.0.0.1",
        postgres_db="sqldbagent",
        postgres_user="sqldbagent",
        postgres_password=password,  # noqa: S106
    )
    datasource = settings.get_datasource("postgres")

    if not datasource.url.startswith(
        "postgresql+psycopg://sqldbagent:sqldbagent-test-password@127.0.0.1:5432/sqldbagent"
    ):
        raise AssertionError(datasource.url)


def test_settings_build_convenience_postgres_demo_datasource() -> None:
    """Synthesize a Postgres demo datasource from convenience settings."""

    settings = AppSettings(
        postgres_demo_host="127.0.0.1",
        postgres_demo_db="sqldbagent_demo",
        postgres_demo_user="sqldbagent",
        postgres_demo_password="sqldbagent",  # noqa: S106  # nosec B106
    )
    datasource = settings.get_datasource("postgres_demo")

    if not datasource.url.startswith(
        "postgresql+psycopg://sqldbagent:sqldbagent@127.0.0.1:5433/sqldbagent_demo"
    ):
        raise AssertionError(datasource.url)


def test_settings_load_optional_llm_provider_keys(monkeypatch) -> None:
    """Load optional provider keys into nested LLM settings."""

    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test-key")

    settings = AppSettings()

    if settings.llm.openai_api_key != "openai-test-key":
        raise AssertionError(settings.llm.openai_api_key)
    if settings.llm.anthropic_api_key != "anthropic-test-key":
        raise AssertionError(settings.llm.anthropic_api_key)


def test_settings_synthesize_agent_checkpoint_postgres_url() -> None:
    """Build the agent checkpoint URL from standard Postgres env-style fields."""

    password = "".join(["sqldbagent", "-", "checkpoint", "-", "password"])
    settings = AppSettings(
        postgres_host="127.0.0.1",
        postgres_db="sqldbagent",
        postgres_user="sqldbagent",
        postgres_password=password,  # noqa: S106
    )

    checkpoint_url = settings.agent.checkpoint.postgres_url
    if checkpoint_url is None:
        raise AssertionError(checkpoint_url)
    if not checkpoint_url.startswith(
        "postgresql+psycopg://sqldbagent:sqldbagent-checkpoint-password@127.0.0.1:5432/sqldbagent"
    ):
        raise AssertionError(checkpoint_url)


def test_settings_allow_env_override_for_embedding_and_retrieval_values() -> None:
    """Apply top-level environment-style overrides to nested retrieval settings."""

    settings = AppSettings(
        qdrant_url="http://127.0.0.1:7000",
        embeddings_provider="hash",
        embeddings_dimensions=64,
    )

    if settings.retrieval.qdrant_url != "http://127.0.0.1:7000":
        raise AssertionError(settings.retrieval.qdrant_url)
    if settings.embeddings.provider != "hash":
        raise AssertionError(settings.embeddings.provider)
    if settings.embeddings.dimensions != 64:
        raise AssertionError(settings.embeddings.dimensions)


def test_resolve_default_datasource_name_uses_explicit_name() -> None:
    """Resolve the explicitly configured default datasource name."""

    settings = AppSettings(
        default_datasource_name="warehouse",
        datasources=[
            DatasourceSettings(
                name="warehouse",
                dialect=Dialect.POSTGRES,
                url="postgresql+psycopg://user:pass@localhost/db",
            )
        ],
    )

    if settings.resolve_default_datasource_name() != "warehouse":
        raise AssertionError(settings.resolve_default_datasource_name())


def test_settings_resolve_datasource_aliases() -> None:
    """Resolve configured datasource aliases to canonical datasource names."""

    settings = AppSettings(
        postgres_demo_host="127.0.0.1",
        postgres_demo_db="sqldbagent_demo",
        postgres_demo_user="sqldbagent",
        postgres_demo_password="sqldbagent",  # noqa: S106  # nosec B106
        datasource_aliases={"demo": "postgres_demo"},
        default_datasource_name="demo",
    )

    if settings.resolve_default_datasource_name() != "postgres_demo":
        raise AssertionError(settings.resolve_default_datasource_name())
    if settings.get_datasource("demo").name != "postgres_demo":
        raise AssertionError(settings.get_datasource("demo"))
