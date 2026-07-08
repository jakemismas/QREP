"""QREP command-line interface."""

import typer

app = typer.Typer(
    no_args_is_help=True,
    help="Reverse engineer quilts from photographs into production-ready patterns.",
)


@app.callback()
def main() -> None:
    """QREP: Quilt Reverse Engineering Platform."""
