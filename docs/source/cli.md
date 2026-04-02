# CLI

The CLI is the first-class operator surface for sqldbagent.

## Core Command Groups

- `sqldbagent config validate`
- `sqldbagent inspect ...`
- `sqldbagent profile ...`
- `sqldbagent query ...`
- `sqldbagent snapshot ...`
- `sqldbagent diagram ...`
- `sqldbagent docs ...`
- `sqldbagent prompt ...`
- `sqldbagent rag ...`
- `sqldbagent dashboard serve`
- `sqldbagent mcp serve`

## Demo Helpers

The repository `Makefile` exposes a local demo flow:

```bash
make demo-up
make demo-inspect
make demo-snapshot
make demo-prompt
make demo-rag-index
make demo-rag-query
make dashboard-demo
```
