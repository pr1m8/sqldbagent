"""SQL safety tests."""

from sqldbagent.core.config import SafetySettings
from sqldbagent.core.enums import Dialect
from sqldbagent.safety.guard import QueryGuardService


def test_query_guard_adds_limit_to_select() -> None:
    """Add a row limit to an otherwise unbounded select."""

    guard = QueryGuardService(
        policy=SafetySettings(max_rows=25),
        dialect=Dialect.SQLITE,
    )

    result = guard.guard("select id from users")

    if not result.allowed:
        raise AssertionError(result.reasons)
    if not result.row_limit_applied:
        raise AssertionError(result)
    if "LIMIT 25" not in (result.normalized_sql or ""):
        raise AssertionError(result.normalized_sql)


def test_query_guard_denies_mutating_statement() -> None:
    """Deny mutating SQL under the read-only policy."""

    guard = QueryGuardService(
        policy=SafetySettings(),
        dialect=Dialect.POSTGRES,
    )

    result = guard.guard("DELETE FROM users")

    if result.allowed:
        raise AssertionError(result)
    if "read-only" not in " ".join(result.reasons):
        raise AssertionError(result.reasons)


def test_query_guard_denies_multiple_statements() -> None:
    """Require exactly one statement."""

    guard = QueryGuardService(
        policy=SafetySettings(),
        dialect=Dialect.POSTGRES,
    )

    result = guard.guard("SELECT 1; SELECT 2;")

    if result.allowed:
        raise AssertionError(result)
    if "exactly one SQL statement is required" not in result.reasons:
        raise AssertionError(result.reasons)


def test_query_lint_normalizes_sql_without_limit_rewrite() -> None:
    """Lint SQL without applying guard limit rewrites."""

    guard = QueryGuardService(
        policy=SafetySettings(max_rows=10),
        dialect=Dialect.POSTGRES,
    )

    result = guard.lint("select id from users")

    if not result.allowed:
        raise AssertionError(result.reasons)
    if result.row_limit_applied:
        raise AssertionError(result)
    if "LIMIT 10" in (result.normalized_sql or ""):
        raise AssertionError(result.normalized_sql)


def test_query_guard_allows_writable_dml_when_policy_enables_it() -> None:
    """Allow a writable statement only when the datasource policy opts in."""

    guard = QueryGuardService(
        policy=SafetySettings(read_only=True, allow_writes=True),
        dialect=Dialect.POSTGRES,
    )

    result = guard.guard(
        "UPDATE users SET email = 'new@example.com' WHERE id = 1",
        access_mode="writable",
    )

    if not result.allowed:
        raise AssertionError(result.reasons)
    if result.access_mode != "writable":
        raise AssertionError(result)
    if not result.warnings:
        raise AssertionError(result)


def test_query_guard_denies_writable_mode_when_policy_disables_it() -> None:
    """Reject writable mode when the datasource policy keeps writes disabled."""

    guard = QueryGuardService(
        policy=SafetySettings(read_only=True, allow_writes=False),
        dialect=Dialect.POSTGRES,
    )

    result = guard.guard(
        "UPDATE users SET email = 'new@example.com' WHERE id = 1",
        access_mode="writable",
    )

    if result.allowed:
        raise AssertionError(result)
    if "writable access mode is unavailable" not in " ".join(result.reasons):
        raise AssertionError(result.reasons)
