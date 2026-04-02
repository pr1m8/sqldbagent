# LangGraph API

```{eval-rst}
.. automodule:: sqldbagent.adapters.langgraph.agent
   :members:
   :undoc-members:

.. automodule:: sqldbagent.adapters.langgraph.middleware
   :members:
   :undoc-members:

.. automodule:: sqldbagent.adapters.langgraph.observability
   :members:
   :undoc-members:
```

## Runtime Entry Point

The LangGraph runtime entrypoint used by `langgraph.json` lives in `sqldbagent.adapters.langgraph.runtime`. It intentionally exposes a module-level `agent` object for LangGraph CLI and SDK loading, so the docs keep that module descriptive rather than importing it through autodoc.
