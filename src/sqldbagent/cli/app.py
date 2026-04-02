"""Typer CLI for sqldbagent."""

from __future__ import annotations

from sqldbagent.cli._typer import load_typer
from sqldbagent.cli.config import app as config_app
from sqldbagent.cli.docs import app as docs_app
from sqldbagent.cli.inspect import app as inspect_app
from sqldbagent.cli.profile import app as profile_app
from sqldbagent.cli.query import app as query_app
from sqldbagent.cli.rag import app as rag_app
from sqldbagent.cli.snapshot import app as snapshot_app

typer = load_typer()
app = typer.Typer(help="sqldbagent command line interface.")
app.add_typer(config_app, name="config")
app.add_typer(docs_app, name="docs")
app.add_typer(inspect_app, name="inspect")
app.add_typer(profile_app, name="profile")
app.add_typer(query_app, name="query")
app.add_typer(rag_app, name="rag")
app.add_typer(snapshot_app, name="snapshot")
