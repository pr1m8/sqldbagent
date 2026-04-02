"""Streamlit chat dashboard over the persisted sqldbagent agent."""

from __future__ import annotations

import subprocess  # nosec B404
from collections.abc import MutableMapping
from html import escape
from json import dumps as json_dumps
from shutil import which
from uuid import uuid4

import orjson

from sqldbagent.adapters.langgraph.checkpoint import create_memory_checkpointer
from sqldbagent.adapters.langgraph.store import create_memory_store
from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import AppSettings
from sqldbagent.dashboard.models import (
    ChatMessageModel,
    DashboardThreadEntryModel,
    DashboardTurnProgressModel,
)
from sqldbagent.dashboard.service import DashboardChatService

_GRAPHVIZ_DOT_EXECUTABLE = which("dot")


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
        checkpointing is disabled or unavailable; otherwise `None` so the
        service can use the configured Postgres saver.
    """

    if (
        settings.agent.checkpoint.backend == "postgres"
        and settings.agent.checkpoint.postgres_url is not None
    ):
        return None
    checkpointer = session_state.get("dashboard_checkpointer")
    if checkpointer is None:
        checkpointer = create_memory_checkpointer()
        session_state["dashboard_checkpointer"] = checkpointer
    return checkpointer


def _resolve_dashboard_store(
    session_state: MutableMapping[str, object],
    settings: AppSettings,
) -> object | None:
    """Resolve the dashboard long-term memory store for the active UI session.

    Args:
        session_state: Streamlit session state mapping.
        settings: Application settings.

    Returns:
        object | None: A stable per-session memory store when Postgres memory is
        disabled or unavailable; otherwise `None` so the service can use the
        configured Postgres store.
    """

    if settings.agent.memory.backend == "disabled":
        return None
    if (
        settings.agent.memory.backend == "postgres"
        and settings.agent.memory.postgres_url is not None
    ):
        return None
    store = session_state.get("dashboard_store")
    if store is None:
        store = create_memory_store()
        session_state["dashboard_store"] = store
    return store


def _build_checkpoint_status(observability: dict[str, object]) -> str:
    """Build sidebar copy describing the active checkpoint mode.

    Args:
        observability: Session observability payload.

    Returns:
        str: Human-readable checkpoint description for the dashboard sidebar.
    """

    summary = observability.get("checkpoint_summary")
    if isinstance(summary, str) and summary.strip():
        return summary
    if observability.get("checkpoint_backend") == "postgres":
        return "Durable thread persistence is active through the configured Postgres checkpoint database."
    return "Thread persistence is scoped to the current dashboard session."


def _build_database_access_status(observability: dict[str, object]) -> str:
    """Build sidebar copy describing the active read-only database path."""

    summary = observability.get("database_access_summary")
    if isinstance(summary, str) and summary.strip():
        return summary
    return "All dashboard SQL stays on the central guarded read-only execution path."


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
      :root {{
        color-scheme: light;
        --surface: #fbfffe;
        --surface-strong: #ffffff;
        --surface-soft: #f3fbf8;
        --surface-muted: #eef8f4;
        --border: #d3ebe3;
        --border-strong: #8fc7b6;
        --text: #12332e;
        --text-soft: #4e6e66;
        --accent: #1f6f64;
        --accent-soft: rgba(31, 111, 100, 0.12);
        --shadow: 0 18px 50px rgba(25, 74, 66, 0.12);
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        padding: 0;
        background:
          radial-gradient(circle at top left, rgba(222, 245, 238, 0.95), transparent 34%),
          radial-gradient(circle at top right, rgba(245, 251, 249, 0.98), transparent 28%),
          linear-gradient(180deg, #f8fcfb 0%, #eff8f5 100%);
        color: var(--text);
        font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .frame {{
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 1rem;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.94) 0%, rgba(247, 252, 250, 0.98) 100%);
        box-shadow: var(--shadow);
      }}
      .header {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.85rem;
      }}
      .title-block {{
        display: flex;
        flex-direction: column;
        gap: 0.22rem;
      }}
      .title {{
        font-size: 1rem;
        font-weight: 700;
        letter-spacing: 0.01em;
      }}
      .subtitle {{
        color: var(--text-soft);
        font-size: 0.88rem;
      }}
      .badges {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
      }}
      .badge {{
        border: 1px solid var(--border);
        background: var(--surface-soft);
        color: var(--text);
        border-radius: 999px;
        padding: 0.28rem 0.72rem;
        font-size: 0.82rem;
        font-weight: 600;
      }}
      .toolbar {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        align-items: center;
        margin-bottom: 0.9rem;
      }}
      .toolbar button {{
        border: 1px solid var(--border);
        background: var(--surface-strong);
        color: var(--text);
        border-radius: 999px;
        padding: 0.42rem 0.92rem;
        cursor: pointer;
        font-size: 0.9rem;
        font-weight: 600;
        box-shadow: 0 6px 18px rgba(32, 80, 71, 0.06);
        transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
      }}
      .toolbar button:hover {{
        transform: translateY(-1px);
        background: var(--surface-soft);
        box-shadow: 0 10px 24px rgba(32, 80, 71, 0.1);
      }}
      .toolbar button.primary {{
        border-color: var(--accent);
        background: linear-gradient(180deg, #ffffff 0%, #eaf8f3 100%);
      }}
      .toolbar .hint {{
        color: var(--text-soft);
        font-size: 0.84rem;
        margin-left: auto;
      }}
      .viewport {{
        position: relative;
        height: 680px;
        overflow: hidden;
        border: 1px solid var(--border);
        border-radius: 16px;
        background:
          linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 252, 250, 0.98) 100%),
          radial-gradient(circle at top, rgba(224, 244, 236, 0.85), transparent 58%);
      }}
      .viewport::before {{
        content: "";
        position: absolute;
        inset: 0;
        background-image:
          linear-gradient(rgba(31, 111, 100, 0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(31, 111, 100, 0.03) 1px, transparent 1px);
        background-size: 28px 28px;
        pointer-events: none;
      }}
      .surface {{
        width: 100%;
        height: 100%;
      }}
      .surface svg {{
        display: block;
        width: 100%;
        height: 100%;
        overflow: visible;
        filter: drop-shadow(0 14px 28px rgba(28, 73, 65, 0.08));
      }}
      .footer {{
        margin-top: 0.8rem;
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 0.7rem;
        align-items: center;
      }}
      .status {{
        color: var(--text-soft);
        font-size: 0.86rem;
      }}
      .legend {{
        color: var(--text-soft);
        font-size: 0.82rem;
      }}
      @media (max-width: 820px) {{
        .viewport {{
          height: 560px;
        }}
        .toolbar .hint {{
          width: 100%;
          margin-left: 0;
        }}
      }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.2/dist/svg-pan-zoom.min.js"></script>
    <script>
      const diagramSource = {json_dumps(mermaid_text)};
      const simplifyTypeToken = (token) => {{
        const normalized = String(token || "")
          .replace(/[^A-Za-z0-9_]/g, "_")
          .replace(/_+/g, "_")
          .replace(/^_+|_+$/g, "");
        if (!normalized) {{
          return "TYPE";
        }}
        return /^[A-Za-z]/.test(normalized) ? normalized : "TYPE_" + normalized;
      }};
      const buildFallbackDiagramSource = (source) => {{
        return String(source || "")
          .split("\\n")
          .map((line) => {{
            if (/^\\s*%%/.test(line)) {{
              return "";
            }}
            if (/^\\s*direction\\s+/i.test(line)) {{
              return "";
            }}
            if (/^\\s{{4,}}[A-Za-z]/.test(line) && !line.includes("{{") && !line.includes("}}")) {{
              const match = line.match(/^(\\s+)(\\S+)(\\s+.+)$/);
              if (match) {{
                return match[1] + simplifyTypeToken(match[2]) + match[3];
              }}
            }}
            return line;
          }})
          .filter((line) => line !== "")
          .join("\\n");
      }};
      const renderDiagram = async (mermaidApi, source, id) => {{
        await mermaidApi.parse(source, {{ suppressErrors: false }});
        return mermaidApi.render(id, source);
      }};

        mermaid.initialize({{
        startOnLoad: true,
        securityLevel: "loose",
        theme: "base",
        themeVariables: {{
          primaryColor: "#f7fbfa",
          primaryTextColor: "#173a35",
          primaryBorderColor: "#2d6f66",
          lineColor: "#3a6d67",
          secondaryColor: "#eef6f3",
          tertiaryColor: "#ffffff",
          background: "#ffffff",
          mainBkg: "#ffffff",
          nodeBkg: "#fbfdfc",
          clusterBkg: "#f4faf8",
          edgeLabelBackground: "#f9fcfb",
          fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        }},
      }});

      window.addEventListener("load", async () => {{
        const surface = document.getElementById("surface");
        const status = document.getElementById("status");
        const zoomBadge = document.getElementById("zoom-badge");
        const zoomIn = document.getElementById("zoom-in");
        const zoomOut = document.getElementById("zoom-out");
        const fit = document.getElementById("fit-view");
        const actualSize = document.getElementById("actual-size");
        const centerView = document.getElementById("center-view");
        const openViewer = document.getElementById("open-viewer");
        const downloadSvg = document.getElementById("download-svg");

        if (!surface || !status || !zoomBadge) {{
          return;
        }}

        try {{
          const renderResult = await renderDiagram(
            mermaid,
            diagramSource,
            "sqldbagent-mermaid-diagram"
          );
          surface.innerHTML = renderResult.svg;
        }} catch (error) {{
          const fallbackSource = buildFallbackDiagramSource(diagramSource);
          try {{
            const fallbackResult = await renderDiagram(
              mermaid,
              fallbackSource,
              "sqldbagent-mermaid-diagram-fallback"
            );
            surface.innerHTML = fallbackResult.svg;
            status.textContent =
              "Rendered a simplified Mermaid fallback after the primary diagram failed to parse.";
          }} catch (fallbackError) {{
            const primaryMessage = error?.message || String(error) || "Unknown Mermaid error";
            const fallbackMessage =
              fallbackError?.message || String(fallbackError) || "Unknown fallback Mermaid error";
            status.textContent = "Unable to render Mermaid SVG.";
            surface.innerHTML =
              "<div style=\\"padding:1rem;color:#9b2c2c;font-weight:600;\\">Mermaid rendering failed.<br/><span style=\\"font-weight:400;white-space:pre-wrap;\\">Primary error: "
              + primaryMessage
              + "\\nFallback error: "
              + fallbackMessage
              + "</span></div>";
            return;
          }}
        }}

        const svg = surface.querySelector("svg");
        if (!svg) {{
          status.textContent = "Unable to render Mermaid SVG.";
          surface.innerHTML = "<div style=\\"padding:1rem;color:#9b2c2c;font-weight:600;\\">Mermaid rendering failed.<br/><span style=\\"font-weight:400;white-space:pre-wrap;\\">No SVG was returned by Mermaid.</span></div>";
          return;
        }}

        svg.removeAttribute("width");
        svg.removeAttribute("height");
        svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

        const serializedSvg = () => new XMLSerializer().serializeToString(svg);

        const updateStatus = (panZoomInstance) => {{
          const zoomLevel = Math.round(panZoomInstance.getZoom() * 100);
          zoomBadge.textContent = "Zoom " + zoomLevel + "%";
          status.textContent =
            "Drag to pan, scroll to zoom, double-click to zoom in, or open a focused viewer in a new window.";
        }};

        const buildViewerHtml = (svgMarkup) => {{
          return [
            "<!doctype html>",
            "<html>",
            "<head>",
            "<meta charset=\\"utf-8\\" />",
            "<title>sqldbagent schema viewer</title>",
            "<style>",
            "body{{margin:0;background:linear-gradient(180deg,#f8fcfb 0%,#edf8f4 100%);font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#12332e;}}",
            ".shell{{padding:18px;display:flex;flex-direction:column;gap:14px;min-height:100vh;}}",
            ".toolbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;}}",
            ".toolbar button{{border:1px solid #cfe7df;background:#fff;border-radius:999px;padding:8px 14px;font-size:14px;font-weight:600;color:#12332e;cursor:pointer;}}",
            ".toolbar .hint{{margin-left:auto;color:#4e6e66;font-size:13px;}}",
            ".viewport{{flex:1;min-height:78vh;border:1px solid #d3ebe3;border-radius:18px;overflow:hidden;background:linear-gradient(180deg,rgba(255,255,255,.97) 0%,rgba(247,252,250,.98) 100%);box-shadow:0 18px 50px rgba(25,74,66,.12);}}",
            "#viewer-surface{{width:100%;height:100%;}}",
            "#viewer-surface svg{{width:100%;height:100%;display:block;overflow:visible;filter:drop-shadow(0 14px 28px rgba(28,73,65,.08));}}",
            "</style>",
            "<script src=\\"https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.2/dist/svg-pan-zoom.min.js\\"></" + "script>",
            "</head>",
            "<body>",
            "<div class=\\"shell\\">",
            "<div class=\\"toolbar\\">",
            "<button id=\\"zoom-in\\" type=\\"button\\">Zoom In</button>",
            "<button id=\\"zoom-out\\" type=\\"button\\">Zoom Out</button>",
            "<button id=\\"fit-view\\" type=\\"button\\">Fit</button>",
            "<button id=\\"actual-size\\" type=\\"button\\">Actual Size</button>",
            "<button id=\\"center-view\\" type=\\"button\\">Center</button>",
            "<button id=\\"download-svg\\" type=\\"button\\">Download SVG</button>",
            "<span class=\\"hint\\">Focused Mermaid viewer</span>",
            "</div>",
            "<div class=\\"viewport\\"><div id=\\"viewer-surface\\">" + svgMarkup + "</div></div>",
            "</div>",
            "<script>",
            "const svg=document.querySelector('#viewer-surface svg');",
            "if(svg){{svg.removeAttribute('width');svg.removeAttribute('height');svg.setAttribute('preserveAspectRatio','xMidYMid meet');const panZoom=window.svgPanZoom(svg,{{controlIconsEnabled:false,zoomEnabled:true,panEnabled:true,fit:true,center:true,minZoom:0.2,maxZoom:12,dblClickZoomEnabled:true,mouseWheelZoomEnabled:true,preventMouseEventsDefault:true}});",
            "const sync=()=>{{panZoom.resize();}};window.addEventListener('resize',sync);",
            "document.getElementById('zoom-in')?.addEventListener('click',()=>panZoom.zoomIn());",
            "document.getElementById('zoom-out')?.addEventListener('click',()=>panZoom.zoomOut());",
            "document.getElementById('fit-view')?.addEventListener('click',()=>{{panZoom.resize();panZoom.fit();panZoom.center();}});",
            "document.getElementById('actual-size')?.addEventListener('click',()=>{{panZoom.resetZoom();panZoom.center();}});",
            "document.getElementById('center-view')?.addEventListener('click',()=>panZoom.center());",
            "document.getElementById('download-svg')?.addEventListener('click',()=>{{const blob=new Blob([new XMLSerializer().serializeToString(svg)],{{type:'image/svg+xml;charset=utf-8'}});const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='sqldbagent-schema.svg';anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}});",
            "panZoom.resize();panZoom.fit();panZoom.center();}}",
            "</" + "script>",
            "</body>",
            "</html>",
          ].join("");
        }};

        const panZoom = window.svgPanZoom(svg, {{
          controlIconsEnabled: false,
          zoomEnabled: true,
          panEnabled: true,
          fit: true,
          center: true,
          minZoom: 0.2,
          maxZoom: 12,
          dblClickZoomEnabled: true,
          mouseWheelZoomEnabled: true,
          preventMouseEventsDefault: true,
        }});

        const fitDiagram = () => {{
          panZoom.resize();
          panZoom.fit();
          panZoom.center();
          updateStatus(panZoom);
        }};

        zoomIn?.addEventListener("click", () => {{
          panZoom.zoomIn();
          updateStatus(panZoom);
        }});
        zoomOut?.addEventListener("click", () => {{
          panZoom.zoomOut();
          updateStatus(panZoom);
        }});
        fit?.addEventListener("click", fitDiagram);
        actualSize?.addEventListener("click", () => {{
          panZoom.resetZoom();
          panZoom.center();
          updateStatus(panZoom);
        }});
        centerView?.addEventListener("click", () => {{
          panZoom.center();
          updateStatus(panZoom);
        }});
        openViewer?.addEventListener("click", () => {{
          const viewerHtml = buildViewerHtml(serializedSvg());
          const blob = new Blob([viewerHtml], {{ type: "text/html;charset=utf-8" }});
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank", "noopener,noreferrer");
          window.setTimeout(() => URL.revokeObjectURL(url), 60000);
        }});
        downloadSvg?.addEventListener("click", () => {{
          const blob = new Blob([serializedSvg()], {{
            type: "image/svg+xml;charset=utf-8",
          }});
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = "sqldbagent-schema.svg";
          anchor.click();
          window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        }});

        window.addEventListener("resize", fitDiagram);
        fitDiagram();
      }});
    </script>
  </head>
  <body>
    <div class="frame">
      <div class="header">
        <div class="title-block">
          <div class="title">Schema Viewer</div>
          <div class="subtitle">Navigate the Mermaid diagram like an interactive canvas.</div>
        </div>
        <div class="badges">
          <span id="zoom-badge" class="badge">Zoom 100%</span>
          <span class="badge">Interactive Mermaid SVG</span>
        </div>
      </div>
      <div class="toolbar">
        <button id="zoom-in" type="button">Zoom In</button>
        <button id="zoom-out" type="button">Zoom Out</button>
        <button id="fit-view" type="button">Fit</button>
        <button id="actual-size" type="button">Actual Size</button>
        <button id="center-view" type="button">Center</button>
        <button id="open-viewer" type="button" class="primary">Open Focus View</button>
        <button id="download-svg" type="button">Download SVG</button>
        <span class="hint">Plotly-style navigation: drag, wheel zoom, and pop-out viewing.</span>
      </div>
      <div id="viewport" class="viewport">
        <div id="surface" class="surface" aria-label="Interactive Mermaid diagram">
          <pre id="diagram-source" style="display:none;">{escape(mermaid_text)}</pre>
        </div>
      </div>
      <div class="footer">
        <div id="status" class="status">Rendering Mermaid diagram...</div>
        <div class="legend">Use the focused viewer for the cleanest large-schema exploration.</div>
      </div>
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


def _render_graphviz_image(graph: object, *, image_format: str = "png") -> bytes | None:
    """Render a schema graph into an image via the local Graphviz `dot` binary.

    Args:
        graph: Diagram graph model with `nodes` and `edges` collections.
        image_format: Output image format supported by Graphviz, typically
            `png` or `svg`.

    Returns:
        bytes | None: Rendered image bytes, or `None` when Graphviz rendering
        is unavailable.
    """

    if _GRAPHVIZ_DOT_EXECUTABLE is None:
        return None
    try:
        completed = subprocess.run(  # nosec B603
            [_GRAPHVIZ_DOT_EXECUTABLE, f"-T{image_format}"],
            input=_build_graphviz_dot(graph).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except Exception:  # noqa: BLE001
        return None
    if not completed.stdout:
        return None
    return completed.stdout


def _build_plotly_schema_figure(graph: object) -> object:
    """Build an interactive Plotly schema graph from one diagram graph payload.

    Args:
        graph: Diagram graph model with `nodes` and `edges` collections.

    Returns:
        object: Plotly figure instance for `st.plotly_chart`.
    """

    networkx = require_dependency("networkx", "networkx")
    graph_objects = require_dependency("plotly.graph_objects", "plotly")

    diagram_graph = networkx.DiGraph()
    node_lookup = {
        getattr(node, "node_id", ""): node for node in getattr(graph, "nodes", [])
    }
    for node in getattr(graph, "nodes", []):
        diagram_graph.add_node(
            getattr(node, "node_id", ""),
            label=getattr(node, "label", getattr(node, "object_name", "object")),
            kind=getattr(node, "kind", "table"),
            summary=getattr(node, "summary", "") or "",
        )
    for edge in getattr(graph, "edges", []):
        diagram_graph.add_edge(
            getattr(edge, "source_node_id", ""),
            getattr(edge, "target_node_id", ""),
            label=getattr(edge, "label", "")
            or getattr(edge, "constraint_name", "")
            or "",
        )

    figure = graph_objects.Figure()
    if not diagram_graph.nodes:
        figure.update_layout(
            margin={"l": 10, "r": 10, "t": 10, "b": 10},
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return figure

    positions = networkx.spring_layout(
        diagram_graph,
        seed=17,
        k=max(0.8, 2.2 / max(1, len(diagram_graph.nodes))),
    )

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for source_node_id, target_node_id in diagram_graph.edges:
        source_x, source_y = positions[source_node_id]
        target_x, target_y = positions[target_node_id]
        edge_x.extend([source_x, target_x, None])
        edge_y.extend([source_y, target_y, None])

    figure.add_trace(
        graph_objects.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"color": "#6f8f88", "width": 1.5},
            hoverinfo="skip",
            name="relationships",
        )
    )

    node_x: list[float] = []
    node_y: list[float] = []
    node_text: list[str] = []
    node_colors: list[str] = []
    node_sizes: list[int] = []
    for node_id, attributes in diagram_graph.nodes(data=True):
        x_pos, y_pos = positions[node_id]
        node_x.append(x_pos)
        node_y.append(y_pos)
        summary = str(attributes.get("summary") or "")
        label = str(attributes.get("label") or node_id)
        kind = str(attributes.get("kind") or "table")
        original_node = node_lookup.get(node_id)
        metadata = (
            {}
            if original_node is None
            else getattr(original_node, "metadata", {}) or {}
        )
        node_text.append(
            "<br>".join(
                part
                for part in [
                    f"<b>{label}</b>",
                    f"kind={kind}",
                    summary,
                    (
                        f"columns={metadata.get('column_count')}"
                        if metadata.get("column_count") is not None
                        else ""
                    ),
                    (
                        f"relationships={metadata.get('foreign_key_count')}"
                        if metadata.get("foreign_key_count") is not None
                        else ""
                    ),
                ]
                if part
            )
        )
        node_colors.append("#1f6f64" if kind == "table" else "#b8860b")
        node_sizes.append(26 if kind == "table" else 22)

    figure.add_trace(
        graph_objects.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=[
                str(attributes.get("label") or node_id)
                for node_id, attributes in diagram_graph.nodes(data=True)
            ],
            textposition="top center",
            hovertemplate="%{hovertext}<extra></extra>",
            hovertext=node_text,
            marker={
                "size": node_sizes,
                "color": node_colors,
                "line": {"color": "#e7f6f1", "width": 1.5},
            },
            name="objects",
        )
    )

    figure.update_layout(
        showlegend=False,
        dragmode="pan",
        margin={"l": 10, "r": 10, "t": 24, "b": 10},
        paper_bgcolor="#f8fcfb",
        plot_bgcolor="#f8fcfb",
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return figure


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
    preview = (
        entry.display_name
        or entry.last_user_message
        or entry.last_assistant_message
        or thread_id[:8]
    )
    schema_name = entry.schema_name or "default"
    updated_at = entry.updated_at.strftime("%Y-%m-%d %H:%M")
    return f"{preview} [{schema_name}] · {updated_at}"


def _decode_tool_payload(content: str) -> object | None:
    """Decode one tool-message payload when it is valid JSON."""

    try:
        return orjson.loads(content)
    except orjson.JSONDecodeError:
        return None


def _summarize_tool_message(message: ChatMessageModel) -> str:
    """Build a compact dashboard summary for one tool transcript row."""

    payload = _decode_tool_payload(message.content)
    if isinstance(payload, dict):
        summary = payload.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        if "row_count" in payload and "columns" in payload:
            return (
                f"Returned {payload.get('row_count', 0)} row(s) across "
                f"{len(payload.get('columns') or [])} column(s)."
            )
        if "rows" in payload and isinstance(payload.get("rows"), list):
            return f"Returned {len(payload.get('rows') or [])} row(s)."
    if isinstance(payload, list):
        return f"Returned {len(payload)} item(s)."
    normalized = " ".join(message.content.split())
    if len(normalized) <= 220:
        return normalized
    return normalized[:219].rstrip() + "…"


def _render_tool_message(
    *,
    st: object,
    message: ChatMessageModel,
    show_details: bool,
) -> None:
    """Render one tool transcript entry with a compact summary first."""

    summary = _summarize_tool_message(message)
    payload = _decode_tool_payload(message.content)
    st.caption(f"Tool: {message.name or 'tool'}")
    st.markdown(summary)

    if isinstance(payload, dict) and "rows" in payload and "columns" in payload:
        rows = payload.get("rows") or []
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("The query completed but returned no rows.")

    if not show_details:
        return

    with st.expander("Tool details", expanded=False):
        if payload is not None:
            st.json(payload, expanded=False)
        else:
            st.code(message.content, language="text")


def _render_progress_log(
    *,
    target: object,
    events: list[DashboardTurnProgressModel],
) -> None:
    """Render streamed progress events into one compact Markdown block."""

    lines: list[str] = []
    for event in events[-8:]:
        line = f"- {event.label}"
        if event.detail:
            line += f"\n  {event.detail}"
        lines.append(line)
    target.markdown("\n".join(lines) if lines else "_Waiting for agent progress..._")


def _should_render_chat_message(
    message: ChatMessageModel,
    *,
    show_tool_traces: bool,
) -> bool:
    """Return whether one transcript message should be shown in the chat tab.

    Args:
        message: Rendered transcript message.
        show_tool_traces: Whether tool transcript rows should be shown.

    Returns:
        bool: `True` when the message should appear in the main chat transcript.
    """

    if message.kind == "tool" and not show_tool_traces:
        return False
    return True


def _should_show_example_questions(messages: list[ChatMessageModel]) -> bool:
    """Return whether starter questions should be shown for the thread.

    Args:
        messages: Current rendered transcript messages.

    Returns:
        bool: `True` only when the thread has not started yet.
    """

    return not any(message.role == "user" for message in messages)


def _build_query_placeholder(schema_name: str | None) -> str:
    """Build help text for the dashboard query editor."""

    if schema_name:
        return (
            "Write a read-only SELECT query against the active schema.\n"
            f"Current schema focus: {schema_name}\n"
            "The safety layer will normalize and limit the query before execution."
        )
    return (
        "Write a read-only SELECT query for the selected datasource.\n"
        "The safety layer will normalize and limit the query before execution."
    )


def _render_query_result(*, st: object, result_payload: dict[str, object]) -> None:
    """Render one guarded query result payload in the dashboard."""

    guard = result_payload.get("guard")
    guard_payload = guard if isinstance(guard, dict) else {}
    summary = str(result_payload.get("summary") or "Query completed.")
    if guard_payload.get("allowed"):
        st.success(summary)
    else:
        st.error(summary)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Mode", str(result_payload.get("mode", "unknown")))
    metric_columns[1].metric("Rows", int(result_payload.get("row_count", 0) or 0))
    metric_columns[2].metric(
        "Truncated",
        "yes" if bool(result_payload.get("truncated")) else "no",
    )
    duration_value = result_payload.get("duration_ms")
    metric_columns[3].metric(
        "Duration",
        "n/a" if duration_value is None else f"{duration_value} ms",
    )

    normalized_sql = guard_payload.get("normalized_sql")
    if isinstance(normalized_sql, str) and normalized_sql.strip():
        with st.expander("Guarded SQL", expanded=False):
            st.code(normalized_sql, language="sql")

    reasons = guard_payload.get("reasons")
    if isinstance(reasons, list) and reasons:
        with st.expander("Guard Reasons", expanded=True):
            for reason in reasons:
                st.write(f"- {reason}")

    if not guard_payload.get("allowed"):
        with st.expander("Raw Result", expanded=False):
            st.json(result_payload, expanded=False)
        return

    rows = result_payload.get("rows")
    if isinstance(rows, list) and rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("The guarded query completed but returned no rows.")

    with st.expander("Raw Result", expanded=False):
        st.json(result_payload, expanded=False)


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
        store=_resolve_dashboard_store(st.session_state, settings),
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
    if "dashboard_query_sql" not in st.session_state:
        st.session_state.dashboard_query_sql = ""
    if "dashboard_query_max_rows" not in st.session_state:
        st.session_state.dashboard_query_max_rows = settings.get_datasource(
            default_datasource
        ).safety.max_rows
    if "dashboard_query_mode" not in st.session_state:
        st.session_state.dashboard_query_mode = "sync"
    if "dashboard_query_access_mode" not in st.session_state:
        st.session_state.dashboard_query_access_mode = "read_only"
    if "dashboard_query_result" not in st.session_state:
        st.session_state.dashboard_query_result = None

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
        active_thread_entry = next(
            (
                entry
                for entry in session.available_threads
                if entry.thread_id == session.thread_id
                and entry.datasource_name == session.datasource_name
                and entry.schema_name == session.schema_name
            ),
            None,
        )
        with st.expander("Thread Details", expanded=False):
            with st.form("thread-metadata-form"):
                thread_display_name = st.text_input(
                    "Thread Name",
                    value=(
                        ""
                        if active_thread_entry is None
                        else active_thread_entry.display_name or ""
                    ),
                    help="Optional saved title for the current persisted thread.",
                )
                save_thread_name = st.form_submit_button(
                    "Save Thread Name",
                    use_container_width=True,
                )
            if save_thread_name:
                service.update_thread_display_name(
                    thread_id=session.thread_id,
                    datasource_name=session.datasource_name,
                    schema_name=session.schema_name,
                    display_name=thread_display_name,
                )
                st.success("Saved thread name.")
                st.rerun()
        prompt_enhancement = (
            None if session.prompt_bundle is None else session.prompt_bundle.enhancement
        )
        has_initial_annotation = bool(
            prompt_enhancement
            and any(
                [
                    prompt_enhancement.user_context,
                    prompt_enhancement.business_rules,
                    prompt_enhancement.additional_effective_context,
                    prompt_enhancement.answer_style,
                ]
            )
        )
        with st.expander(
            "Initial Annotation",
            expanded=not has_initial_annotation and not session.messages,
        ):
            if session.prompt_bundle is None:
                st.info(
                    "Create or load a schema snapshot first, then the dashboard can save onboarding notes for this datasource and schema."
                )
            else:
                st.write(
                    "Add domain notes for a new datasource or schema so the agent starts with better context."
                )
                with st.form("initial-annotation-form"):
                    initial_user_context = st.text_area(
                        "Domain Context",
                        value=(
                            ""
                            if prompt_enhancement is None
                            else prompt_enhancement.user_context or ""
                        ),
                        height=140,
                        help="Business goals, domain language, or stakeholder context.",
                    )
                    initial_business_rules = st.text_area(
                        "Business Rules",
                        value=(
                            ""
                            if prompt_enhancement is None
                            else prompt_enhancement.business_rules or ""
                        ),
                        height=140,
                        help="Interpretation rules, caveats, and known data constraints.",
                    )
                    initial_answer_style = st.text_area(
                        "Answer Style",
                        value=(
                            ""
                            if prompt_enhancement is None
                            else prompt_enhancement.answer_style or ""
                        ),
                        height=100,
                        help="Optional style guidance for summaries and analysis.",
                    )
                    initial_effective_context = st.text_area(
                        "Additional Effective Prompt Context",
                        value=(
                            ""
                            if prompt_enhancement is None
                            else prompt_enhancement.additional_effective_context or ""
                        ),
                        height=140,
                        help=(
                            "Extra instructions to inject directly into the merged "
                            "effective prompt for this datasource and schema."
                        ),
                    )
                    save_initial_annotation = st.form_submit_button(
                        "Save Initial Annotation",
                        use_container_width=True,
                    )
                if save_initial_annotation:
                    updated_bundle = service.update_prompt_bundle_enhancement(
                        datasource_name=session.datasource_name,
                        schema_name=session.schema_name
                        or session.prompt_bundle.schema_name,
                        active=True,
                        user_context=initial_user_context,
                        business_rules=initial_business_rules,
                        additional_effective_context=initial_effective_context,
                        answer_style=initial_answer_style,
                        refresh_generated=True,
                    )
                    if updated_bundle is None:
                        st.error("No stored snapshot is available yet for this schema.")
                    else:
                        st.success("Saved initial annotation.")
                        st.rerun()
        if summary_cards:
            st.subheader("Context")
            for card in summary_cards:
                st.metric(
                    label=str(card.get("title", "Value")),
                    value=str(card.get("value", "")),
                )
        if session.retrieval_manifest is not None:
            with st.expander("Retrieval Index", expanded=False):
                st.write(f"Collection: `{session.retrieval_manifest.collection_name}`")
                st.write(f"Documents: `{session.retrieval_manifest.document_count}`")
                st.write(f"Snapshot: `{session.retrieval_manifest.snapshot_id}`")
        st.subheader("Observability")
        observability_columns = st.columns(2)
        observability_columns[0].metric(
            "Persistence",
            (
                "durable"
                if bool(observability.get("checkpoint_is_durable"))
                else "session"
            ),
        )
        observability_columns[1].metric(
            "Checkpoint",
            str(observability.get("checkpoint_backend", "unknown")),
        )
        checkpoint_status = _build_checkpoint_status(observability)
        checkpoint_recommendation = observability.get("checkpoint_recommendation")
        requested_backend = observability.get("checkpoint_requested_backend")
        active_backend = observability.get("checkpoint_backend")
        if observability.get("checkpoint_status") == "fallback":
            st.warning(checkpoint_status)
        elif observability.get("checkpoint_is_durable"):
            st.success(checkpoint_status)
        else:
            st.info(checkpoint_status)
        if (
            isinstance(requested_backend, str)
            and isinstance(active_backend, str)
            and requested_backend != active_backend
        ):
            st.caption(
                f"Requested backend: `{requested_backend}`. Active backend: `{active_backend}`."
            )
        if isinstance(checkpoint_recommendation, str) and checkpoint_recommendation:
            st.caption(checkpoint_recommendation)
        memory_status = observability.get("memory_summary")
        if isinstance(memory_status, str) and memory_status:
            st.write(memory_status)
        memory_backend = observability.get("memory_backend")
        if memory_backend:
            st.caption(f"Memory backend: `{memory_backend}`")
        st.write(_build_database_access_status(observability))
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

    chat_tab, schema_tab, prompt_tab, retrieval_tab, query_tab, threads_tab = st.tabs(
        ["Chat", "Schema", "Prompt", "Retrieval", "Query", "Threads"]
    )

    with chat_tab:
        show_tool_traces = bool(
            st.session_state.get("dashboard_show_tool_traces", False)
        )
        hidden_tool_count = 0
        for message in session.messages:
            if not _should_render_chat_message(
                message,
                show_tool_traces=show_tool_traces,
            ):
                hidden_tool_count += 1
                continue
            if message.role == "user":
                with st.chat_message("user"):
                    st.markdown(message.content)
            elif message.kind == "tool":
                with st.chat_message("assistant"):
                    _render_tool_message(
                        st=st,
                        message=message,
                        show_details=show_tool_traces,
                    )
            else:
                with st.chat_message("assistant"):
                    st.markdown(message.content)

        if not session.messages:
            st.info(
                "Start with a question about the selected datasource. "
                "The agent will reuse stored snapshot context, retrieval, and safe SQL."
            )
        st.toggle(
            "Show tool traces",
            key="dashboard_show_tool_traces",
            value=show_tool_traces,
            help="Show or hide tool transcript rows in the main chat. The tool digest and final assistant answer remain available either way.",
        )
        if hidden_tool_count:
            st.caption(
                f"{hidden_tool_count} tool trace message(s) are hidden from the chat transcript."
            )
        selected_example_question: str | None = None
        pending_turn_container = st.container()
        example_question_container = st.container()
        if session.example_questions and _should_show_example_questions(
            session.messages
        ):
            with example_question_container:
                st.subheader("Example Questions")
                example_columns = st.columns(2)
                for index, question in enumerate(session.example_questions):
                    with example_columns[index % len(example_columns)]:
                        if st.button(
                            question,
                            key=f"example-question-{thread_id}-{index}",
                            use_container_width=True,
                        ):
                            selected_example_question = question

        prompt = st.chat_input("Ask the database intelligence agent")
        submitted_prompt = selected_example_question or prompt
        if submitted_prompt:
            example_question_container.empty()
            with pending_turn_container:
                with st.chat_message("user"):
                    st.markdown(submitted_prompt)
                progress_events: list[DashboardTurnProgressModel] = []
                progress_status = st.status(
                    "Starting agent turn...",
                    expanded=True,
                )
                with progress_status:
                    progress_log = st.empty()

            def on_progress(event: DashboardTurnProgressModel) -> None:
                progress_events.append(event)
                progress_status.update(
                    label=event.label,
                    state="running",
                    expanded=True,
                )
                _render_progress_log(target=progress_log, events=progress_events)

            try:
                session = service.run_turn(
                    thread_id=thread_id,
                    user_message=submitted_prompt,
                    datasource_name=datasource_name,
                    schema_name=schema_name or None,
                    progress_callback=on_progress,
                )
            except Exception as exc:  # noqa: BLE001
                progress_status.update(
                    label="Agent turn failed.",
                    state="error",
                    expanded=True,
                )
                _render_progress_log(target=progress_log, events=progress_events)
                st.exception(exc)
                return
            progress_status.update(
                label="Agent turn complete.",
                state="complete",
                expanded=False,
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
            png_bytes = _render_graphviz_image(graph, image_format="png")
            svg_bytes = _render_graphviz_image(graph, image_format="svg")
            interactive_tab, image_tab, mermaid_tab, graph_tab, graph_data_tab = (
                st.tabs(["Interactive", "Image", "Mermaid", "Graphviz", "Graph Data"])
            )
            with interactive_tab:
                st.plotly_chart(
                    _build_plotly_schema_figure(graph),
                    use_container_width=True,
                    config={"displaylogo": False, "scrollZoom": True},
                )
                st.caption(
                    "Interactive schema view backed by the stored graph payload. "
                    "Use Mermaid below when you want the textual ER artifact itself."
                )
            with image_tab:
                if png_bytes is None:
                    st.info(
                        "A generated schema image is not available in this environment."
                    )
                else:
                    st.image(
                        png_bytes,
                        caption="Generated schema image fallback",
                        use_container_width=True,
                    )
                    st.caption(
                        "This image is rendered locally from the stored schema graph, so it still works even when the browser Mermaid renderer does not."
                    )
                    st.download_button(
                        label="Download PNG",
                        data=png_bytes,
                        file_name=(
                            f"{session.diagram_bundle.datasource_name}"
                            f"_{session.diagram_bundle.schema_name}"
                            f"_{session.diagram_bundle.snapshot_id}.png"
                        ),
                        mime="image/png",
                        use_container_width=True,
                    )
                    if svg_bytes is not None:
                        st.download_button(
                            label="Download SVG",
                            data=svg_bytes,
                            file_name=(
                                f"{session.diagram_bundle.datasource_name}"
                                f"_{session.diagram_bundle.schema_name}"
                                f"_{session.diagram_bundle.snapshot_id}.svg"
                            ),
                            mime="image/svg+xml",
                            use_container_width=True,
                        )
            with mermaid_tab:
                components.html(
                    _build_mermaid_embed(session.diagram_bundle.mermaid_erd),
                    height=860,
                    scrolling=False,
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
            with graph_tab:
                if graph.nodes:
                    st.graphviz_chart(
                        _build_graphviz_dot(graph),
                        use_container_width=True,
                    )
                    st.caption(
                        "Graphviz is kept as a secondary structural view. The Mermaid visual above is the primary schema render."
                    )
                else:
                    st.info("No graph nodes are available for this schema snapshot.")
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
                st.subheader("Effective System Prompt")
                st.code(prompt_bundle.system_prompt, language="text")
            with top_right:
                st.subheader("Bundle Details")
                st.metric("Sections", len(prompt_bundle.sections))
                st.metric("Snapshot", prompt_bundle.snapshot_id)
                st.metric(
                    "Base Prompt Tokens",
                    str(
                        prompt_bundle.token_estimates.get(
                            "base_system_prompt_tokens",
                            "?",
                        )
                    ),
                )
                st.metric(
                    "System Prompt Tokens",
                    str(prompt_bundle.token_estimates.get("system_prompt_tokens", "?")),
                )
                st.metric(
                    "Enhancement Tokens",
                    str(
                        prompt_bundle.token_estimates.get(
                            "enhancement_text_tokens",
                            (
                                prompt_bundle.enhancement.token_estimates.get(
                                    "generated_context_tokens",
                                    "?",
                                )
                                if prompt_bundle.enhancement is not None
                                else "?"
                            ),
                        )
                    ),
                )
                st.metric(
                    "Prompt Delta",
                    str(prompt_bundle.token_estimates.get("prompt_delta_tokens", "?")),
                )
                enhancement = prompt_bundle.enhancement
                generated_context_exists = bool(
                    enhancement is not None and enhancement.generated_context.strip()
                )
                if st.button(
                    (
                        "Refresh Additional Schema Context"
                        if generated_context_exists
                        else "Generate Additional Schema Context"
                    ),
                    use_container_width=True,
                ):
                    refreshed_bundle = service.refresh_prompt_bundle_context(
                        datasource_name=datasource_name,
                        schema_name=schema_name or prompt_bundle.schema_name,
                    )
                    if refreshed_bundle is None:
                        st.error("No stored snapshot is available yet for this schema.")
                    else:
                        st.success("Updated additional schema context.")
                        st.rerun()
                with st.expander("Live Prompt Exploration", expanded=False):
                    focus_tables_csv = st.text_input(
                        "Focus Tables (optional)",
                        value="",
                        help=(
                            "Optional comma-separated list of tables to explore and "
                            "save into the effective prompt. Leave blank to let the "
                            "service choose the highest-signal tables."
                        ),
                    )
                    live_max_tables = st.number_input(
                        "Max Tables",
                        min_value=1,
                        max_value=6,
                        value=4,
                        step=1,
                    )
                    unique_value_limit = st.number_input(
                        "Distinct Values Per Column",
                        min_value=2,
                        max_value=20,
                        value=8,
                        step=1,
                    )
                    sync_memory = st.checkbox(
                        "Also sync a concise summary into long-term memory",
                        value=True,
                        help=(
                            "When a store backend is configured, this saves a short "
                            "exploration summary and preferred tables for later runs."
                        ),
                    )
                    if st.button(
                        "Explore Live DB And Save To Prompt",
                        use_container_width=True,
                    ):
                        explored_bundle = service.explore_prompt_bundle_context(
                            datasource_name=datasource_name,
                            schema_name=schema_name or prompt_bundle.schema_name,
                            table_names=[
                                value.strip()
                                for value in focus_tables_csv.split(",")
                                if value.strip()
                            ]
                            or None,
                            max_tables=int(live_max_tables),
                            unique_value_limit=int(unique_value_limit),
                            sync_memory=sync_memory,
                        )
                        if explored_bundle is None:
                            st.error(
                                "No stored snapshot is available yet for this schema."
                            )
                        else:
                            st.success(
                                "Saved live prompt exploration and refreshed the prompt bundle."
                            )
                            st.rerun()
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
            prompt_views = st.tabs(
                [
                    "Effective Prompt",
                    "Base Prompt",
                    "Enhancement",
                    "Token Budget",
                    "Sections",
                    "State Seed",
                ]
            )
            with prompt_views[0]:
                st.code(prompt_bundle.system_prompt, language="text")
            with prompt_views[1]:
                st.code(prompt_bundle.base_system_prompt, language="text")
            with prompt_views[2]:
                if enhancement is None:
                    st.info("No prompt enhancement is stored for this schema yet.")
                else:
                    st.caption(enhancement.summary or "Prompt enhancement")
                    if enhancement.exploration is not None:
                        st.info(
                            enhancement.exploration.summary
                            or "Saved live exploration context is active for this schema."
                        )
                    st.caption(
                        "Effective enhancement tokens: "
                        f"`{enhancement.token_estimates.get('effective_enhancement_tokens', '?')}`"
                    )
                    st.write(
                        "Use this saved context to keep the dynamic prompt grounded in "
                        "schema-specific guidance and your domain notes."
                    )
                    with st.form("prompt-enhancement-form"):
                        enhancement_active = st.checkbox(
                            "Use saved prompt enhancement",
                            value=enhancement.active,
                        )
                        user_context = st.text_area(
                            "User Context",
                            value=enhancement.user_context or "",
                            height=160,
                            help=(
                                "Domain notes, business terminology, stakeholder goals, "
                                "or any extra context the agent should remember."
                            ),
                        )
                        business_rules = st.text_area(
                            "Business Rules And Caveats",
                            value=enhancement.business_rules or "",
                            height=160,
                            help=(
                                "Constraints, interpretation rules, data-quality caveats, "
                                "or known exceptions for this schema."
                            ),
                        )
                        additional_effective_context = st.text_area(
                            "Additional Effective Prompt Context",
                            value=enhancement.additional_effective_context or "",
                            height=160,
                            help=(
                                "Extra instructions to inject directly into the "
                                "effective system prompt for this schema."
                            ),
                        )
                        answer_style = st.text_area(
                            "Answer Style",
                            value=enhancement.answer_style or "",
                            height=120,
                            help=(
                                "Optional instructions for how answers should be shaped, "
                                "summarized, or formatted."
                            ),
                        )
                        action_left, action_right = st.columns(2)
                        save_prompt_context = action_left.form_submit_button(
                            "Save Prompt Context",
                            use_container_width=True,
                        )
                        refresh_prompt_context = action_right.form_submit_button(
                            "Save And Refresh DB Guidance",
                            use_container_width=True,
                        )
                    if save_prompt_context or refresh_prompt_context:
                        updated_bundle = service.update_prompt_bundle_enhancement(
                            datasource_name=datasource_name,
                            schema_name=schema_name or prompt_bundle.schema_name,
                            active=enhancement_active,
                            user_context=user_context,
                            business_rules=business_rules,
                            additional_effective_context=additional_effective_context,
                            answer_style=answer_style,
                            refresh_generated=refresh_prompt_context,
                        )
                        if updated_bundle is None:
                            st.error(
                                "No stored snapshot is available yet for this schema. "
                                "Create a snapshot before saving prompt enhancements."
                            )
                        else:
                            st.success("Saved prompt enhancement.")
                            st.rerun()
                    enhancement_tabs = st.tabs(
                        [
                            "Merged Guidance",
                            "Generated DB Guidance",
                            "Live Exploration",
                            "Enhancement JSON",
                        ]
                    )
                    with enhancement_tabs[0]:
                        st.code(prompt_bundle.system_prompt, language="text")
                    with enhancement_tabs[1]:
                        st.code(enhancement.generated_context, language="text")
                    with enhancement_tabs[2]:
                        if enhancement.exploration is None:
                            st.info(
                                "No saved live exploration context exists for this schema yet."
                            )
                        else:
                            st.caption(
                                enhancement.exploration.summary
                                or "Saved live exploration"
                            )
                            exploration_left, exploration_right = st.columns([2, 1])
                            with exploration_left:
                                st.code(
                                    enhancement.exploration.context,
                                    language="text",
                                )
                            with exploration_right:
                                st.metric(
                                    "Exploration Tokens",
                                    str(
                                        enhancement.exploration.token_estimates.get(
                                            "token_count",
                                            "?",
                                        )
                                    ),
                                )
                                st.metric(
                                    "Focus Tables",
                                    str(len(enhancement.exploration.focus_tables)),
                                )
                                st.write(
                                    "\n".join(
                                        f"- `{table_name}`"
                                        for table_name in enhancement.exploration.focus_tables
                                    )
                                    or "No saved focus tables."
                                )
                    with enhancement_tabs[3]:
                        st.json(enhancement.model_dump(mode="json"), expanded=False)
                        st.download_button(
                            label="Download Enhancement JSON",
                            data=enhancement.model_dump_json(indent=2),
                            file_name=(
                                f"{prompt_bundle.datasource_name}"
                                f"_{prompt_bundle.schema_name}.prompt-enhancement.json"
                            ),
                            mime="application/json",
                            use_container_width=True,
                        )
            with prompt_views[3]:
                token_left, token_right = st.columns(2)
                with token_left:
                    st.subheader("Prompt Layers")
                    st.dataframe(
                        [
                            {
                                "layer": "base_system_prompt",
                                "tokens": prompt_bundle.token_estimates.get(
                                    "base_system_prompt_tokens"
                                ),
                                "characters": prompt_bundle.token_estimates.get(
                                    "base_system_prompt_characters"
                                ),
                            },
                            {
                                "layer": "system_prompt",
                                "tokens": prompt_bundle.token_estimates.get(
                                    "system_prompt_tokens"
                                ),
                                "characters": prompt_bundle.token_estimates.get(
                                    "system_prompt_characters"
                                ),
                            },
                            {
                                "layer": "enhancement_text",
                                "tokens": prompt_bundle.token_estimates.get(
                                    "enhancement_text_tokens"
                                ),
                                "characters": prompt_bundle.token_estimates.get(
                                    "enhancement_characters"
                                ),
                            },
                        ],
                        hide_index=True,
                        use_container_width=True,
                    )
                with token_right:
                    st.subheader("Enhancement Layers")
                    if enhancement is None:
                        st.info("No prompt enhancement is stored for this schema yet.")
                    else:
                        st.dataframe(
                            [
                                {
                                    "layer": "generated_context",
                                    "tokens": enhancement.token_estimates.get(
                                        "generated_context_tokens"
                                    ),
                                    "characters": enhancement.token_estimates.get(
                                        "generated_context_characters"
                                    ),
                                },
                                {
                                    "layer": "exploration_context",
                                    "tokens": enhancement.token_estimates.get(
                                        "exploration_context_tokens"
                                    ),
                                    "characters": enhancement.token_estimates.get(
                                        "exploration_context_characters"
                                    ),
                                },
                                {
                                    "layer": "user_context",
                                    "tokens": enhancement.token_estimates.get(
                                        "user_context_tokens"
                                    ),
                                    "characters": enhancement.token_estimates.get(
                                        "user_context_characters"
                                    ),
                                },
                                {
                                    "layer": "business_rules",
                                    "tokens": enhancement.token_estimates.get(
                                        "business_rules_tokens"
                                    ),
                                    "characters": enhancement.token_estimates.get(
                                        "business_rules_characters"
                                    ),
                                },
                                {
                                    "layer": "additional_effective_context",
                                    "tokens": enhancement.token_estimates.get(
                                        "additional_effective_context_tokens"
                                    ),
                                    "characters": enhancement.token_estimates.get(
                                        "additional_effective_context_characters"
                                    ),
                                },
                                {
                                    "layer": "answer_style",
                                    "tokens": enhancement.token_estimates.get(
                                        "answer_style_tokens"
                                    ),
                                    "characters": enhancement.token_estimates.get(
                                        "answer_style_characters"
                                    ),
                                },
                            ],
                            hide_index=True,
                            use_container_width=True,
                        )
            with prompt_views[4]:
                for section in prompt_bundle.sections:
                    with st.expander(section.title, expanded=False):
                        st.markdown(section.content)
            with prompt_views[5]:
                st.json(prompt_bundle.state_seed, expanded=False)

    with retrieval_tab:
        resolved_retrieval_schema = (
            schema_name
            or session.schema_name
            or settings.default_schema_name
            or "public"
        )
        active_snapshot_id = (
            session.latest_snapshot_id
            or (
                None
                if session.prompt_bundle is None
                else session.prompt_bundle.snapshot_id
            )
            or (
                None
                if session.diagram_bundle is None
                else session.diagram_bundle.snapshot_id
            )
        )
        if active_snapshot_id is None:
            st.info(
                "No stored snapshot is available yet. Create a snapshot first, then you can build a retrieval index for it."
            )
        else:
            manifest = session.retrieval_manifest
            if manifest is None:
                st.info(
                    "No retrieval index is saved for the active snapshot yet. The agent can auto-index on first retrieval, or you can build it now."
                )
            else:
                st.caption(manifest.summary or "Stored retrieval index manifest")
                left_column, right_column = st.columns([2, 1])
                with left_column:
                    st.json(manifest.model_dump(mode="json"), expanded=False)
                with right_column:
                    st.metric("Documents", manifest.document_count)
                    st.metric("Snapshot", manifest.snapshot_id)
                    st.write(f"Collection: `{manifest.collection_name}`")
            if session.latest_snapshot_summary:
                st.caption(session.latest_snapshot_summary)

            action_left, action_right = st.columns(2)
            if action_left.button(
                "Load Or Build Retrieval Index",
                use_container_width=True,
            ):
                ensured_manifest = service.ensure_retrieval_index(
                    datasource_name=datasource_name,
                    schema_name=resolved_retrieval_schema,
                    recreate_collection=False,
                )
                if ensured_manifest is None:
                    st.error("No stored snapshot is available yet for this schema.")
                else:
                    st.success("Retrieval index is ready.")
                    st.rerun()
            if action_right.button(
                "Rebuild Retrieval Index",
                use_container_width=True,
            ):
                ensured_manifest = service.ensure_retrieval_index(
                    datasource_name=datasource_name,
                    schema_name=resolved_retrieval_schema,
                    recreate_collection=True,
                )
                if ensured_manifest is None:
                    st.error("No stored snapshot is available yet for this schema.")
                else:
                    st.success("Rebuilt retrieval index.")
                    st.rerun()

    with query_tab:
        resolved_query_datasource = settings.resolve_datasource_name(datasource_name)
        datasource_config = settings.get_datasource(resolved_query_datasource)
        supports_async_queries = service.supports_async_queries(
            datasource_name=resolved_query_datasource
        )
        writable_supported = bool(datasource_config.safety.allow_writes)
        st.caption(
            "Run guarded SQL against the selected datasource. The dashboard defaults to read-only access and uses the same safety and query services as the CLI and agent tools."
        )
        if schema_name:
            st.write(f"Current schema focus: `{schema_name}`")

        query_mode_options = ["sync", "async"] if supports_async_queries else ["sync"]
        if st.session_state.dashboard_query_mode not in query_mode_options:
            st.session_state.dashboard_query_mode = query_mode_options[0]

        query_mode = st.segmented_control(
            "Execution Mode",
            options=query_mode_options,
            selection_mode="single",
            default=st.session_state.dashboard_query_mode,
            help="Use the async path when the datasource driver supports it.",
        )
        if query_mode is not None:
            st.session_state.dashboard_query_mode = query_mode

        access_mode_options = (
            ["read_only", "writable"] if writable_supported else ["read_only"]
        )
        if st.session_state.dashboard_query_access_mode not in access_mode_options:
            st.session_state.dashboard_query_access_mode = access_mode_options[0]
        query_access_mode = st.segmented_control(
            "Access Mode",
            options=access_mode_options,
            selection_mode="single",
            default=st.session_state.dashboard_query_access_mode,
            help=(
                "Read-only is the default. Writable mode is only available when "
                "the datasource policy explicitly enables writes."
            ),
        )
        if query_access_mode is not None:
            st.session_state.dashboard_query_access_mode = query_access_mode
        if st.session_state.dashboard_query_access_mode == "writable":
            st.warning(
                "Writable access is explicit and higher risk. Review the SQL carefully before running it."
            )
        else:
            st.info("Read-only remains the default and recommended query mode.")

        st.text_area(
            "SQL",
            key="dashboard_query_sql",
            height=180,
            placeholder=_build_query_placeholder(schema_name),
        )
        max_rows = st.number_input(
            "Max Rows",
            min_value=1,
            max_value=max(
                datasource_config.safety.max_rows,
                int(st.session_state.dashboard_query_max_rows),
            ),
            value=int(st.session_state.dashboard_query_max_rows),
            step=1,
            help="The guard layer enforces this limit on top of the datasource safety policy.",
        )
        st.session_state.dashboard_query_max_rows = int(max_rows)

        action_left, action_right = st.columns(2)
        run_query = action_left.button(
            "Run Guarded Query",
            use_container_width=True,
        )
        clear_query_result = action_right.button(
            "Clear Query Result",
            use_container_width=True,
        )
        if clear_query_result:
            st.session_state.dashboard_query_result = None
            st.rerun()

        if run_query:
            with st.spinner("Running guarded query..."):
                result = service.run_safe_query(
                    datasource_name=resolved_query_datasource,
                    sql=st.session_state.dashboard_query_sql,
                    max_rows=int(max_rows),
                    mode=st.session_state.dashboard_query_mode,
                    access_mode=st.session_state.dashboard_query_access_mode,
                )
            st.session_state.dashboard_query_result = result.model_dump(mode="json")

        if st.session_state.dashboard_query_result is not None:
            _render_query_result(
                st=st,
                result_payload=st.session_state.dashboard_query_result,
            )

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
