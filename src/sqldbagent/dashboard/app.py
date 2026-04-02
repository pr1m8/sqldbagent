"""Streamlit chat dashboard over the persisted sqldbagent agent."""

from __future__ import annotations

from collections.abc import MutableMapping
from html import escape
from json import dumps as json_dumps
from uuid import uuid4

from sqldbagent.adapters.langgraph.checkpoint import create_memory_checkpointer
from sqldbagent.core.config import AppSettings
from sqldbagent.dashboard.models import DashboardThreadEntryModel
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


def _build_checkpoint_status(observability: dict[str, object]) -> str:
    """Build sidebar copy describing the active checkpoint mode.

    Args:
        observability: Session observability payload.

    Returns:
        str: Human-readable checkpoint description for the dashboard sidebar.
    """

    if observability.get("checkpoint_backend") == "postgres":
        return "Persistence is enabled through the configured Postgres checkpointer."
    return "Persistence is scoped to this Streamlit session via an in-memory saver."


def _build_mermaid_embed(mermaid_text: str) -> str:
    """Build embeddable Mermaid HTML for Streamlit components.

    Args:
        mermaid_text: Mermaid diagram source text.

    Returns:
        str: Self-contained HTML payload for `streamlit.components.v1.html`.
    """

    return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      body {{
        margin: 0;
        background: #fbfffe;
        font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .frame {{
        border: 1px solid #d8efe9;
        border-radius: 14px;
        padding: 1rem;
        background: linear-gradient(180deg, #fcfffe 0%, #f5fbf9 100%);
        overflow: auto;
      }}
      .mermaid {{
        min-width: 100%;
      }}
    </style>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({{
        startOnLoad: true,
        securityLevel: "loose",
        theme: "default",
      }});
      window.addEventListener("load", () => {{
        const target = document.getElementById("diagram");
        if (target) {{
          target.textContent = {json_dumps(mermaid_text)};
          mermaid.run({{ nodes: [target] }});
        }}
      }});
    </script>
  </head>
  <body>
    <div class="frame">
      <pre id="diagram" class="mermaid">{escape(mermaid_text)}</pre>
    </div>
  </body>
</html>
""".strip()


def _escape_graphviz_label(value: str) -> str:
    """Escape one Graphviz label fragment.

    Args:
        value: Raw label text.

    Returns:
        str: Graphviz-safe label text.
    """

    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_graphviz_dot(graph: object) -> str:
    """Build a Graphviz DOT graph from one diagram bundle graph payload.

    Args:
        graph: Diagram graph model with `nodes` and `edges` collections.

    Returns:
        str: DOT source suitable for `st.graphviz_chart`.
    """

    lines = [
        "digraph schema {",
        '  graph [rankdir="LR", pad="0.3", nodesep="0.5", ranksep="0.8"];',
        '  node [shape="box", style="rounded,filled", color="#1f6f64", fillcolor="#ecf8f5", fontname="Helvetica", fontsize="11"];',
        '  edge [color="#4b6b66", fontname="Helvetica", fontsize="10"];',
    ]

    for node in getattr(graph, "nodes", []):
        kind = getattr(node, "kind", "table")
        label_parts = [getattr(node, "label", getattr(node, "object_name", "object"))]
        summary = getattr(node, "summary", None)
        if summary:
            label_parts.append(summary[:80])
        shape = "box" if kind == "table" else "ellipse"
        fillcolor = "#ecf8f5" if kind == "table" else "#f8f4ea"
        label = "\\n".join(_escape_graphviz_label(part) for part in label_parts if part)
        node_id = _escape_graphviz_label(getattr(node, "node_id", "node"))
        lines.append(
            f'  "{node_id}" [label="{label}", shape="{shape}", fillcolor="{fillcolor}"];'
        )

    for edge in getattr(graph, "edges", []):
        source = _escape_graphviz_label(getattr(edge, "source_node_id", "source"))
        target = _escape_graphviz_label(getattr(edge, "target_node_id", "target"))
        label = (
            getattr(edge, "label", None) or getattr(edge, "constraint_name", "") or ""
        )
        safe_label = _escape_graphviz_label(label)
        if safe_label:
            lines.append(f'  "{source}" -> "{target}" [label="{safe_label}"];')
        else:
            lines.append(f'  "{source}" -> "{target}";')

    lines.append("}")
    return "\n".join(lines)


def _format_thread_label(
    entry: DashboardThreadEntryModel | None,
    *,
    current_thread_id: str,
    thread_id: str,
) -> str:
    """Build a readable label for a dashboard thread selector.

    Args:
        entry: Optional persisted thread summary.
        current_thread_id: Currently active dashboard thread id.
        thread_id: Thread id to label.

    Returns:
        str: Human-readable thread label.
    """

    if thread_id == current_thread_id and entry is None:
        return f"Current thread ({thread_id[:8]})"
    if entry is None:
        return thread_id
    preview = entry.last_user_message or entry.last_assistant_message or thread_id[:8]
    schema_name = entry.schema_name or "default"
    updated_at = entry.updated_at.strftime("%Y-%m-%d %H:%M")
    return f"{preview} [{schema_name}] · {updated_at}"


def main() -> None:
    """Render the dashboard chat application."""

    import streamlit as st
    import streamlit.components.v1 as components

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
        available_threads = service.list_threads(
            datasource_name=datasource_name,
            schema_name=schema_name or None,
        )
        thread_lookup = {entry.thread_id: entry for entry in available_threads}
        thread_options = [
            st.session_state.dashboard_thread_id,
            *[
                entry.thread_id
                for entry in available_threads
                if entry.thread_id != st.session_state.dashboard_thread_id
            ],
        ]
        selected_thread = st.selectbox(
            "Saved Threads",
            options=thread_options,
            format_func=lambda value: _format_thread_label(
                thread_lookup.get(value),
                current_thread_id=st.session_state.dashboard_thread_id,
                thread_id=value,
            ),
        )
        thread_id = st.text_input(
            "Thread ID",
            value=selected_thread,
            help="Reuse this value to continue the same persisted conversation.",
        )
        if st.button("New Thread", use_container_width=True):
            st.session_state.dashboard_thread_id = service.new_thread_id()
            st.rerun()
        st.session_state.dashboard_datasource = datasource_name
        st.session_state.dashboard_schema = schema_name
        st.session_state.dashboard_thread_id = thread_id

    session = service.load_thread(
        thread_id=thread_id,
        datasource_name=datasource_name,
        schema_name=schema_name or None,
    )
    observability = session.observability
    summary_cards = session.dashboard_payload.get("cards", [])

    with st.sidebar:
        if summary_cards:
            st.subheader("Context")
            for card in summary_cards:
                st.metric(
                    label=str(card.get("title", "Value")),
                    value=str(card.get("value", "")),
                )
        st.subheader("Observability")
        st.write(
            f"Checkpoint backend: `{observability.get('checkpoint_backend', 'unknown')}`",
        )
        st.write(_build_checkpoint_status(observability))
        if observability.get("langsmith_tracing"):
            st.success("LangSmith tracing is enabled for dashboard turns.")
        else:
            st.info("LangSmith tracing is currently disabled.")
        langsmith_project = observability.get("langsmith_project")
        if langsmith_project:
            st.write(f"Project: `{langsmith_project}`")
        langsmith_endpoint = observability.get("langsmith_endpoint")
        if langsmith_endpoint:
            st.write(f"Endpoint: `{langsmith_endpoint}`")
        langsmith_workspace_id = observability.get("langsmith_workspace_id")
        if langsmith_workspace_id:
            st.write(f"Workspace: `{langsmith_workspace_id}`")
        langsmith_tags = observability.get("langsmith_tags") or []
        if langsmith_tags:
            st.write("Tags: " + ", ".join(str(tag) for tag in langsmith_tags))
        if session.latest_snapshot_summary:
            with st.expander("Latest Snapshot", expanded=False):
                st.write(session.latest_snapshot_summary)
        if session.tool_call_digest:
            with st.expander("Tool Digest", expanded=False):
                for line in session.tool_call_digest:
                    st.write(f"- {line}")

    if summary_cards:
        visible_cards = summary_cards[:4]
        columns = st.columns(len(visible_cards))
        for column, card in zip(columns, visible_cards, strict=False):
            with column:
                st.metric(
                    label=str(card.get("title", "Value")),
                    value=str(card.get("value", "")),
                )

    chat_tab, schema_tab, prompt_tab, threads_tab = st.tabs(
        ["Chat", "Schema", "Prompt", "Threads"]
    )

    with chat_tab:
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

    with schema_tab:
        if session.diagram_bundle is None:
            st.info(
                "No diagram bundle is available yet. Create a snapshot for this schema "
                "and the dashboard will load or generate the Mermaid ER view."
            )
        else:
            st.caption(session.diagram_bundle.summary or "Stored schema diagram")
            graph = session.diagram_bundle.graph
            graph_tab, mermaid_tab, graph_data_tab = st.tabs(
                ["Graph", "Mermaid", "Graph Data"]
            )
            with graph_tab:
                if graph.nodes:
                    st.graphviz_chart(
                        _build_graphviz_dot(graph),
                        use_container_width=True,
                    )
                else:
                    st.info("No graph nodes are available for this schema snapshot.")
            with mermaid_tab:
                components.html(
                    _build_mermaid_embed(session.diagram_bundle.mermaid_erd),
                    height=720,
                    scrolling=True,
                )
                st.subheader("Mermaid Source")
                st.code(session.diagram_bundle.mermaid_erd, language="mermaid")
                st.download_button(
                    label="Download Mermaid",
                    data=session.diagram_bundle.mermaid_erd,
                    file_name=(
                        f"{session.diagram_bundle.datasource_name}"
                        f"_{session.diagram_bundle.schema_name}"
                        f"_{session.diagram_bundle.snapshot_id}.mmd"
                    ),
                    mime="text/plain",
                    use_container_width=True,
                )
            with graph_data_tab:
                left_column, right_column = st.columns([2, 1])
                with left_column:
                    st.subheader("Nodes")
                    st.dataframe(
                        [
                            {
                                "label": node.label,
                                "kind": node.kind,
                                "summary": node.summary or "",
                            }
                            for node in graph.nodes
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                with right_column:
                    st.subheader("Graph Summary")
                    st.metric("Nodes", len(graph.nodes))
                    st.metric("Edges", len(graph.edges))
                    st.dataframe(
                        [
                            {
                                "from": edge.source_node_id,
                                "to": edge.target_node_id,
                                "label": edge.label or "",
                            }
                            for edge in graph.edges
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

    with prompt_tab:
        if session.prompt_bundle is None:
            st.info(
                "No prompt bundle is available yet. Create a snapshot for this schema "
                "and the dashboard will load or generate the prompt artifact."
            )
        else:
            prompt_bundle = session.prompt_bundle
            st.caption(prompt_bundle.summary or "Stored prompt bundle")
            top_left, top_right = st.columns([2, 1])
            with top_left:
                st.subheader("System Prompt")
                st.code(prompt_bundle.system_prompt, language="text")
            with top_right:
                st.subheader("Bundle Details")
                st.metric("Sections", len(prompt_bundle.sections))
                st.metric("Snapshot", prompt_bundle.snapshot_id)
                st.download_button(
                    label="Download Prompt Markdown",
                    data=service.render_prompt_markdown(prompt_bundle),
                    file_name=(
                        f"{prompt_bundle.datasource_name}"
                        f"_{prompt_bundle.schema_name}"
                        f"_{prompt_bundle.snapshot_id}.prompt.md"
                    ),
                    mime="text/markdown",
                    use_container_width=True,
                )
                st.download_button(
                    label="Download Prompt JSON",
                    data=prompt_bundle.model_dump_json(indent=2),
                    file_name=(
                        f"{prompt_bundle.datasource_name}"
                        f"_{prompt_bundle.schema_name}"
                        f"_{prompt_bundle.snapshot_id}.prompt.json"
                    ),
                    mime="application/json",
                    use_container_width=True,
                )
            st.subheader("Prompt Sections")
            for section in prompt_bundle.sections:
                with st.expander(section.title, expanded=False):
                    st.markdown(section.content)
            st.subheader("State Seed")
            st.json(prompt_bundle.state_seed, expanded=False)

    with threads_tab:
        threads = session.available_threads or available_threads
        if not threads:
            st.info(
                "No saved dashboard threads are available yet. Start a conversation "
                "and it will appear here for later reuse."
            )
        else:
            st.dataframe(
                [
                    {
                        "thread_id": entry.thread_id,
                        "schema": entry.schema_name or "default",
                        "updated_at": entry.updated_at.isoformat(timespec="seconds"),
                        "messages": entry.message_count,
                        "snapshot_id": entry.latest_snapshot_id or "",
                        "last_user": entry.last_user_message or "",
                        "last_assistant": entry.last_assistant_message or "",
                    }
                    for entry in threads
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Use the Saved Threads selector in the sidebar to reopen one of these conversations."
            )


if __name__ == "__main__":
    main()
