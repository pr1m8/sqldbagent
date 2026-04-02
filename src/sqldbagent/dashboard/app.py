"""Streamlit chat dashboard over the persisted sqldbagent agent."""

from __future__ import annotations

from collections.abc import MutableMapping
from uuid import uuid4

from sqldbagent.adapters.langgraph.checkpoint import create_memory_checkpointer
from sqldbagent.core.config import AppSettings
from sqldbagent.dashboard.service import DashboardChatService


def _resolve_dashboard_checkpointer(
    session_state: MutableMapping[str, object],
    settings: AppSettings,
) -> object | None:
    """Resolve the dashboard checkpointer for the active UI session.

    Args:
        session_state: Streamlit session state mapping.
        settings: Application settings.

    Returns:
        object | None: A stable per-session memory saver when Postgres
        checkpointing is not enabled; otherwise `None` so the service can use
        the configured Postgres saver.
    """

    if settings.agent.checkpoint.backend == "postgres":
        return None
    checkpointer = session_state.get("dashboard_checkpointer")
    if checkpointer is None:
        checkpointer = create_memory_checkpointer()
        session_state["dashboard_checkpointer"] = checkpointer
    return checkpointer


def _build_checkpoint_status(settings: AppSettings) -> str:
    """Build sidebar copy describing the active checkpoint mode.

    Args:
        settings: Application settings.

    Returns:
        str: Human-readable checkpoint description for the dashboard sidebar.
    """

    if settings.agent.checkpoint.backend == "postgres":
        return "Persistence is enabled through the configured Postgres checkpointer."
    return "Persistence is scoped to this Streamlit session via an in-memory saver."


def main() -> None:
    """Render the dashboard chat application."""

    import streamlit as st

    from sqldbagent.core.config import load_settings

    st.set_page_config(
        page_title="sqldbagent Chat",
        layout="wide",
    )
    settings = load_settings()
    service = DashboardChatService(
        settings=settings,
        checkpointer=_resolve_dashboard_checkpointer(st.session_state, settings),
    )

    datasource_options = [datasource.name for datasource in settings.datasources]
    if not datasource_options:
        st.error("No datasources are configured.")
        return

    default_datasource = settings.resolve_default_datasource_name()
    default_schema = settings.default_schema_name or "public"
    if "dashboard_thread_id" not in st.session_state:
        st.session_state.dashboard_thread_id = uuid4().hex
    if "dashboard_datasource" not in st.session_state:
        st.session_state.dashboard_datasource = default_datasource
    if "dashboard_schema" not in st.session_state:
        st.session_state.dashboard_schema = default_schema

    st.title("sqldbagent Chat")
    st.caption(
        "Persistent chat over the LangGraph-backed sqldbagent agent. "
        "Reuse a thread ID to continue the same conversation with checkpointed state."
    )

    with st.sidebar:
        selected_datasource = st.session_state.dashboard_datasource
        if selected_datasource not in datasource_options:
            selected_datasource = default_datasource
        st.subheader("Session")
        datasource_name = st.selectbox(
            "Datasource",
            options=datasource_options,
            index=datasource_options.index(selected_datasource),
        )
        schema_name = st.text_input("Schema", value=st.session_state.dashboard_schema)
        thread_id = st.text_input(
            "Thread ID",
            value=st.session_state.dashboard_thread_id,
            help="Reuse this value to continue the same persisted conversation.",
        )
        if st.button("New Thread", use_container_width=True):
            st.session_state.dashboard_thread_id = service.new_thread_id()
            st.rerun()
        st.session_state.dashboard_datasource = datasource_name
        st.session_state.dashboard_schema = schema_name
        st.session_state.dashboard_thread_id = thread_id
        st.divider()
        st.write(
            f"Checkpoint backend: `{settings.agent.checkpoint.backend}`",
        )
        st.write(_build_checkpoint_status(settings))

    session = service.load_thread(
        thread_id=thread_id,
        datasource_name=datasource_name,
        schema_name=schema_name or None,
    )

    with st.sidebar:
        cards = session.dashboard_payload.get("cards", [])
        if cards:
            st.subheader("Context")
            for card in cards:
                st.metric(
                    label=str(card.get("title", "Value")),
                    value=str(card.get("value", "")),
                )
        if session.latest_snapshot_summary:
            with st.expander("Latest Snapshot", expanded=False):
                st.write(session.latest_snapshot_summary)
        if session.tool_call_digest:
            with st.expander("Tool Digest", expanded=False):
                for line in session.tool_call_digest:
                    st.write(f"- {line}")

    for message in session.messages:
        if message.role == "user":
            with st.chat_message("user"):
                st.markdown(message.content)
        else:
            with st.chat_message("assistant"):
                if message.kind == "tool" and message.name:
                    st.caption(f"Tool: {message.name}")
                st.markdown(message.content)

    if not session.messages:
        st.info(
            "Start with a question about the selected datasource. "
            "The agent will reuse stored snapshot context, retrieval, and safe SQL."
        )

    prompt = st.chat_input("Ask the database intelligence agent")
    if prompt:
        with st.spinner("Running agent turn..."):
            session = service.run_turn(
                thread_id=thread_id,
                user_message=prompt,
                datasource_name=datasource_name,
                schema_name=schema_name or None,
            )
        st.session_state.dashboard_thread_id = session.thread_id
        st.rerun()


if __name__ == "__main__":
    main()
