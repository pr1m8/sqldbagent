"""SQL query guard service."""

from __future__ import annotations

from typing import Any

from sqldbagent.core.config import SafetySettings
from sqldbagent.core.enums import Dialect
from sqldbagent.safety.models import QueryGuardResult
from sqldbagent.safety.policies import should_apply_row_limit, to_sqlglot_dialect


class QueryGuardService:
    """Guard SQL through AST inspection and normalization."""

    def __init__(self, policy: SafetySettings, dialect: Dialect) -> None:
        """Initialize the query guard.

        Args:
            policy: Safety policy settings.
            dialect: Datasource dialect.
        """

        self._policy = policy
        self._dialect = dialect
        self._sqlglot_dialect = to_sqlglot_dialect(dialect)

    def lint(self, sql: str) -> QueryGuardResult:
        """Parse and normalize SQL without applying guard rewrites.

        Args:
            sql: SQL text to lint.

        Returns:
            QueryGuardResult: Lint result.
        """

        return self._evaluate(sql, apply_guard=False)

    def guard(self, sql: str, *, max_rows: int | None = None) -> QueryGuardResult:
        """Parse, validate, and normalize SQL under the active policy.

        Args:
            sql: SQL text to guard.
            max_rows: Optional row-limit override for this evaluation.

        Returns:
            QueryGuardResult: Guard result.
        """

        return self._evaluate(sql, apply_guard=True, max_rows=max_rows)

    def _evaluate(
        self,
        sql: str,
        *,
        apply_guard: bool,
        max_rows: int | None = None,
    ) -> QueryGuardResult:
        """Evaluate a SQL statement.

        Args:
            sql: SQL text to evaluate.
            apply_guard: Whether guard rewrites should be applied.
            max_rows: Optional row-limit override.

        Returns:
            QueryGuardResult: Evaluation result.
        """

        sqlglot = self._load_sqlglot()
        exp = sqlglot.exp
        policy = (
            self._policy
            if max_rows is None
            else self._policy.model_copy(update={"max_rows": max_rows})
        )

        try:
            statements = [
                statement
                for statement in sqlglot.parse(sql, dialect=self._sqlglot_dialect)
                if statement is not None
            ]
        except sqlglot.errors.ParseError as exc:
            return QueryGuardResult(
                allowed=False,
                dialect=self._dialect.value,
                original_sql=sql,
                reasons=[str(exc)],
                summary="Query failed to parse.",
            )

        if len(statements) != 1:
            return QueryGuardResult(
                allowed=False,
                dialect=self._dialect.value,
                original_sql=sql,
                reasons=["exactly one SQL statement is required"],
                summary="Query rejected because multiple statements were provided.",
            )

        statement = statements[0]
        statement_type = statement.__class__.__name__.upper()
        referenced_schemas, referenced_tables = self._collect_references(
            statement,
            exp=exp,
        )
        reasons = self._collect_reasons(
            statement,
            exp=exp,
            policy=policy,
            referenced_schemas=referenced_schemas,
        )

        if reasons:
            return QueryGuardResult(
                allowed=False,
                dialect=self._dialect.value,
                original_sql=sql,
                statement_type=statement_type,
                normalized_sql=statement.sql(dialect=self._sqlglot_dialect),
                max_rows=policy.max_rows,
                referenced_schemas=referenced_schemas,
                referenced_tables=referenced_tables,
                reasons=reasons,
                summary=self._summarize_result(
                    allowed=False,
                    statement_type=statement_type,
                    referenced_tables=referenced_tables,
                    reasons=reasons,
                ),
            )

        guarded = statement.copy()
        row_limit_applied = False

        if apply_guard:
            limit_expression = guarded.args.get("limit")
            has_limit = limit_expression is not None

            if should_apply_row_limit(policy, has_limit):
                guarded = guarded.limit(policy.max_rows)
                row_limit_applied = True
            elif has_limit:
                current_limit = self._extract_limit_value(limit_expression, exp=exp)
                if current_limit is None or current_limit > policy.max_rows:
                    guarded = guarded.limit(policy.max_rows)
                    row_limit_applied = True

        return QueryGuardResult(
            allowed=True,
            dialect=self._dialect.value,
            original_sql=sql,
            statement_type=statement_type,
            normalized_sql=guarded.sql(dialect=self._sqlglot_dialect),
            row_limit_applied=row_limit_applied,
            max_rows=policy.max_rows,
            referenced_schemas=referenced_schemas,
            referenced_tables=referenced_tables,
            summary=self._summarize_result(
                allowed=True,
                statement_type=statement_type,
                referenced_tables=referenced_tables,
                reasons=[],
            ),
        )

    def _collect_reasons(
        self,
        statement: Any,
        *,
        exp: Any,
        policy: SafetySettings,
        referenced_schemas: list[str],
    ) -> list[str]:
        """Collect validation failures for a statement.

        Args:
            statement: SQLGlot expression tree.
            exp: SQLGlot expressions module.
            policy: Effective safety policy.
            referenced_schemas: Referenced schemas discovered in the statement.

        Returns:
            list[str]: Validation failure reasons.
        """

        reasons: list[str] = []

        if policy.read_only and not isinstance(statement, exp.Query):
            reasons.append("only read-only query statements are allowed")

        if policy.allowed_schemas:
            denied_schemas = sorted(
                {
                    schema_name
                    for schema_name in referenced_schemas
                    if schema_name not in policy.allowed_schemas
                }
            )
            if denied_schemas:
                reasons.append(
                    "query references disallowed schemas: " + ", ".join(denied_schemas)
                )

        disallowed_node_names = [
            "Delete",
            "Update",
            "Insert",
            "Merge",
            "Create",
            "Drop",
            "Alter",
            "Command",
            "Copy",
            "Grant",
            "Revoke",
            "TruncateTable",
            "Use",
            "Call",
        ]

        for node_name in disallowed_node_names:
            node_type = getattr(exp, node_name, None)
            if node_type is not None and statement.find(node_type):
                reasons.append(
                    f"disallowed SQL operation detected: {node_name.lower()}"
                )

        return reasons

    def _collect_references(
        self, statement: Any, *, exp: Any
    ) -> tuple[list[str], list[str]]:
        """Collect referenced schemas and tables from a SQLGlot statement.

        Args:
            statement: SQLGlot expression tree.
            exp: SQLGlot expressions module.

        Returns:
            tuple[list[str], list[str]]: Referenced schemas and tables.
        """

        referenced_schemas: set[str] = set()
        referenced_tables: set[str] = set()

        for table in statement.find_all(exp.Table):
            schema_name = table.db
            table_name = table.name
            if schema_name:
                referenced_schemas.add(schema_name)
                referenced_tables.add(f"{schema_name}.{table_name}")
            else:
                referenced_tables.add(table_name)

        return sorted(referenced_schemas), sorted(referenced_tables)

    def _extract_limit_value(self, limit_expression: Any, *, exp: Any) -> int | None:
        """Extract a literal row limit when present.

        Args:
            limit_expression: SQLGlot limit expression.
            exp: SQLGlot expressions module.

        Returns:
            int | None: Literal limit value when it can be determined.
        """

        if limit_expression is None:
            return None

        expression = getattr(limit_expression, "expression", None)
        if isinstance(expression, exp.Literal) and expression.is_int:
            return int(expression.this)

        return None

    def _load_sqlglot(self) -> Any:
        """Import SQLGlot lazily.

        Returns:
            Any: SQLGlot module.
        """

        from sqldbagent.adapters.shared import require_dependency

        return require_dependency("sqlglot", "sqlglot")

    def _summarize_result(
        self,
        *,
        allowed: bool,
        statement_type: str | None,
        referenced_tables: list[str],
        reasons: list[str],
    ) -> str:
        """Build a short human-readable summary for a guard evaluation."""

        table_text = ", ".join(referenced_tables) if referenced_tables else "no tables"
        if allowed:
            return (
                f"{statement_type or 'statement'} accepted for {self._dialect.value}; "
                f"references {table_text}."
            )
        return (
            f"{statement_type or 'statement'} rejected for {self._dialect.value}: "
            + "; ".join(reasons)
        )
