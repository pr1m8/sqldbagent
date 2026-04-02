"""LangChain v1 middleware builders for sqldbagent agents."""

from __future__ import annotations

from typing import Any

from sqldbagent.adapters.langgraph.prompts import create_sqldbagent_system_prompt
from sqldbagent.adapters.langgraph.state import SQLDBAgentState
from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.agent_context import build_sqldbagent_state_seed
from sqldbagent.core.config import AppSettings, load_settings


def create_sqldbagent_middleware(
    *,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
) -> list[Any]:
    """Build the default middleware stack for sqldbagent agents.

    The middleware stack is where LangChain v1's `create_agent(...)` contract
    becomes repo-specific. We use it for:

    - dynamic prompt injection from stored snapshots
    - bounded model and tool call loops
    - structured tool error responses instead of raw exceptions

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.

    Returns:
        list[Any]: LangChain middleware instances in execution order.
    """

    resolved_settings = settings or load_settings()
    middleware_module = require_dependency("langchain.agents.middleware", "langchain")
    middlewares: list[Any] = [
        create_sqldbagent_state_middleware(
            datasource_name=datasource_name,
            settings=resolved_settings,
            schema_name=schema_name,
        ),
        create_sqldbagent_dynamic_prompt_middleware(
            datasource_name=datasource_name,
            settings=resolved_settings,
            schema_name=schema_name,
        ),
    ]

    if resolved_settings.agent.enable_todo_middleware:
        middlewares.append(middleware_module.TodoListMiddleware())

    if resolved_settings.agent.enable_human_in_the_loop:
        middlewares.append(
            middleware_module.HumanInTheLoopMiddleware({"safe_query_sql": True})
        )

    middlewares.extend(
        [
            create_sqldbagent_tool_error_middleware(),
        ]
    )

    if resolved_settings.agent.enable_summarization_middleware:
        summarization_middleware = create_sqldbagent_summarization_middleware(
            settings=resolved_settings
        )
        if summarization_middleware is not None:
            middlewares.append(summarization_middleware)

    middlewares.extend(
        [
            create_sqldbagent_tool_digest_middleware(
                settings=resolved_settings,
            )
        ]
    )

    if resolved_settings.agent.max_model_calls_per_run is not None:
        middlewares.append(
            middleware_module.ModelCallLimitMiddleware(
                run_limit=resolved_settings.agent.max_model_calls_per_run,
                exit_behavior="error",
            )
        )

    if resolved_settings.agent.max_tool_calls_per_run is not None:
        middlewares.append(
            middleware_module.ToolCallLimitMiddleware(
                run_limit=resolved_settings.agent.max_tool_calls_per_run,
                exit_behavior="error",
            )
        )

    return middlewares


def create_sqldbagent_state_middleware(
    *,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
) -> Any:
    """Seed agent state with snapshot and dashboard-oriented context.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.

    Returns:
        Any: LangChain middleware instance created via `@before_agent`.
    """

    resolved_settings = settings or load_settings()
    middleware_module = require_dependency("langchain.agents.middleware", "langchain")

    @middleware_module.before_agent(state_schema=SQLDBAgentState)
    def sqldbagent_state_seed(_state: SQLDBAgentState, _runtime: Any) -> dict[str, Any]:
        return build_sqldbagent_state_seed(
            datasource_name=datasource_name,
            settings=resolved_settings,
            schema_name=schema_name,
        )

    return sqldbagent_state_seed


def create_sqldbagent_dynamic_prompt_middleware(
    *,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
) -> Any:
    """Create dynamic prompt middleware over stored snapshot context.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.

    Returns:
        Any: LangChain middleware instance created via `@dynamic_prompt`.
    """

    resolved_settings = settings or load_settings()
    middleware_module = require_dependency("langchain.agents.middleware", "langchain")

    @middleware_module.dynamic_prompt
    def sqldbagent_dynamic_prompt(_request: Any) -> str:
        return create_sqldbagent_system_prompt(
            datasource_name=datasource_name,
            settings=resolved_settings,
            schema_name=schema_name,
        )

    return sqldbagent_dynamic_prompt


def create_sqldbagent_tool_error_middleware() -> Any:
    """Create tool middleware that converts tool exceptions into ToolMessages.

    Returns:
        Any: LangChain middleware instance created via `@wrap_tool_call`.
    """

    middleware_module = require_dependency("langchain.agents.middleware", "langchain")
    messages_module = require_dependency("langchain_core.messages", "langchain")
    tool_message = messages_module.ToolMessage

    @middleware_module.wrap_tool_call
    def sqldbagent_tool_errors(request: Any, handler: Any) -> Any:
        """Turn tool failures into structured responses the agent can reason over.

        Args:
            request: Tool call request wrapper from LangChain.
            handler: Wrapped tool execution callable.

        Returns:
            Any: Tool response message or command.
        """

        try:
            return handler(request)
        except Exception as exc:  # noqa: BLE001
            tool_name = request.tool_call.get("name", "tool")
            tool_call_id = request.tool_call["id"]
            if tool_name == "safe_query_sql":
                content = (
                    f"`{tool_name}` failed: {exc}. "
                    "Re-check inspection, profile, or snapshot context before retrying SQL."
                )
            else:
                content = f"`{tool_name}` failed: {exc}."
            return tool_message(
                content=content,
                name=tool_name,
                status="error",
                tool_call_id=tool_call_id,
            )

    return sqldbagent_tool_errors


def create_sqldbagent_tool_digest_middleware(
    *,
    settings: AppSettings | None = None,
) -> Any:
    """Create middleware that compresses tool-call outputs into digest state.

    Args:
        settings: Optional application settings.

    Returns:
        Any: LangChain middleware instance created via `@after_agent`.
    """

    resolved_settings = settings or load_settings()
    middleware_module = require_dependency("langchain.agents.middleware", "langchain")

    @middleware_module.after_agent(state_schema=SQLDBAgentState)
    def sqldbagent_tool_digest(
        state: SQLDBAgentState,
        _runtime: Any,
    ) -> dict[str, Any] | None:
        digest = _compress_tool_messages(
            state["messages"],
            limit=resolved_settings.agent.tool_call_digest_limit,
        )
        if not digest:
            return None
        return {"tool_call_digest": digest}

    return sqldbagent_tool_digest


def create_sqldbagent_summarization_middleware(
    *,
    settings: AppSettings | None = None,
) -> Any | None:
    """Create context summarization middleware when configured.

    Args:
        settings: Optional application settings.

    Returns:
        Any | None: LangChain summarization middleware when configured.
    """

    resolved_settings = settings or load_settings()
    middleware_module = require_dependency("langchain.agents.middleware", "langchain")
    model_name = resolved_settings.agent.summarization_model or _build_model_reference(
        resolved_settings
    )
    if model_name is None:
        return None

    return middleware_module.SummarizationMiddleware(
        model=model_name,
        trigger=("fraction", resolved_settings.agent.summarization_trigger_fraction),
        keep=("messages", resolved_settings.agent.summarization_keep_messages),
        summary_prompt=_build_summary_prompt(),
    )


def _build_model_reference(settings: AppSettings) -> str | None:
    """Build a LangChain model reference from provider settings.

    Args:
        settings: Application settings.

    Returns:
        str | None: Provider-qualified model reference when available.
    """

    if not settings.llm.default_provider or not settings.llm.default_model:
        return None
    return f"{settings.llm.default_provider}:{settings.llm.default_model}"


def _compress_tool_messages(messages: list[Any], *, limit: int) -> list[str]:
    """Compress recent tool messages into short digest lines.

    Args:
        messages: Agent message history.
        limit: Maximum digest entries to retain.

    Returns:
        list[str]: Compact tool-call digest entries.
    """

    digest: list[str] = []
    for message in messages:
        if getattr(message, "type", None) != "tool":
            continue
        tool_name = getattr(message, "name", "tool")
        content = str(getattr(message, "content", "")).replace("\n", " ").strip()
        if len(content) > 160:
            content = f"{content[:157]}..."
        digest.append(f"{tool_name}: {content}")
    return digest[-limit:]


def _build_summary_prompt() -> str:
    """Build the repo-specific summarization prompt for long agent sessions.

    Returns:
        str: Prompt template for LangChain summarization middleware.
    """

    return """
<role>
sqldbagent Context Compression Assistant
</role>

<goal>
You are compressing a long-running database intelligence session so the agent can continue working without losing critical context.
</goal>

<instructions>
Summarize only the most important database-specific context and execution history. Keep it concrete and reusable.

Always include these sections:

## OBJECTIVE
What the user is trying to learn or produce.

## DATABASE CONTEXT
Datasource, schema focus, important entities, relationships, row-count/storage/profile hints, and safety constraints.

## SNAPSHOT AND ARTIFACT CONTEXT
Relevant snapshot ids, summaries, docs, diagrams, prompts, or exports already created or loaded.

## TOOL AND QUERY HISTORY
The most important inspection/profile/query actions and what they established.

## OPEN QUESTIONS
What is still unresolved or still needs verification.

## NEXT STEPS
What the agent should do next.
</instructions>

<messages>
Messages to summarize:
{messages}
</messages>
""".strip()
