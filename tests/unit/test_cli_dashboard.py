"""Dashboard CLI tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sqldbagent.cli.app import app


def test_dashboard_serve_runs_streamlit_with_repo_app(monkeypatch) -> None:
    """Launch the dashboard CLI with the expected Streamlit command."""

    recorded: dict[str, object] = {}

    class Completed:
        """Small stand-in for `subprocess.CompletedProcess`."""

        returncode = 0

    def fake_run(command, *, env, check):  # noqa: ANN001
        recorded["command"] = command
        recorded["env"] = env
        recorded["check"] = check
        return Completed()

    monkeypatch.setattr(
        "sqldbagent.cli.dashboard.require_dependency", lambda *a, **k: None
    )
    monkeypatch.setattr("sqldbagent.cli.dashboard.subprocess.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "dashboard",
            "serve",
            "--datasource",
            "postgres_demo",
            "--schema",
            "public",
            "--port",
            "8601",
        ],
    )

    if result.exit_code != 0:
        raise AssertionError(result.output)
    command = recorded.get("command")
    if not isinstance(command, list):
        raise AssertionError(recorded)
    if command[:4] != [command[0], "-m", "streamlit", "run"]:
        raise AssertionError(command)
    app_path = Path(command[4])
    if app_path.name != "app.py" or app_path.parent.name != "dashboard":
        raise AssertionError(app_path)
    env = recorded.get("env")
    if not isinstance(env, dict):
        raise AssertionError(recorded)
    if env.get("SQLDBAGENT_DEFAULT_DATASOURCE") != "postgres_demo":
        raise AssertionError(env)
    if env.get("SQLDBAGENT_DEFAULT_SCHEMA") != "public":
        raise AssertionError(env)
