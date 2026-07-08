"""QREP command-line interface. Signatures are pinned by the design doc."""

from pathlib import Path

import typer
from pydantic import ValidationError

from qrep.construct import compute_yardage, get_strategy
from qrep.export import export_all
from qrep.model import QrepSchemaError, load
from qrep.render import save_render
from qrep.viewer import write_viewer

app = typer.Typer(
    no_args_is_help=True,
    help="Reverse engineer quilts from photographs into production-ready patterns.",
)


def _load_or_exit(quilt_file: Path):
    try:
        return load(quilt_file)
    except FileNotFoundError:
        typer.echo(f"error: file not found: {quilt_file}", err=True)
        raise typer.Exit(1) from None
    except QrepSchemaError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from None
    except ValidationError as e:
        typer.echo(f"error: quilt JSON failed validation:\n{e}", err=True)
        raise typer.Exit(1) from None


def _plan_or_exit(quilt, strategy: str):
    try:
        return get_strategy(strategy)(quilt)
    except KeyError as e:
        typer.echo(f"error: {e.args[0]}", err=True)
        raise typer.Exit(1) from None
    except (NotImplementedError, ValueError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def validate(quilt_file: Path) -> None:
    """Validate a quilt JSON file against the schema."""
    quilt = _load_or_exit(quilt_file)
    typer.echo(
        f"OK: {quilt.metadata.name} is valid "
        f"({quilt.center.rows}x{quilt.center.cols} cells, "
        f"{len(quilt.palette.fabrics)} fabrics)"
    )


@app.command()
def plan(
    quilt_file: Path,
    strategy: str = typer.Option("historical", "--strategy", "-s"),
    output: Path | None = typer.Option(None, "--output", "-o", help="write plan JSON here"),
) -> None:
    """Compute a construction plan and print its metrics."""
    quilt = _load_or_exit(quilt_file)
    result = _plan_or_exit(quilt, strategy)
    m = result.metrics
    distinct = len(result.strip_sets)
    typer.echo(f"strategy: {result.strategy}")
    typer.echo(f"pieces in top: {m.piece_count}")
    typer.echo(f"cut operations: {m.cut_count}")
    typer.echo(f"seams: {m.seam_count}")
    typer.echo(f"strip sets: {m.strip_set_count} physical ({distinct} distinct)")
    typer.echo(f"waste: {m.waste:.1%}")
    typer.echo(f"bias edges: {m.bias_percent:.1%}")
    typer.echo(f"difficulty: {m.difficulty} ({m.heuristic_label})")
    typer.echo(f"time estimate: {m.time_minutes} min ({m.heuristic_label})")
    yardage = compute_yardage(quilt, result)
    for line in yardage.lines:
        label = f"{line.name} ({line.fabric_id})" if line.fabric_id else line.name
        typer.echo(f"yardage - {label}: {line.quarter_yards / 4} yd")
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
        typer.echo(f"wrote {output}")


@app.command()
def render(
    quilt_file: Path,
    level: int = typer.Option(0, "--level", min=0, max=3),
    seed: int = typer.Option(42, "--seed"),
    scale: int = typer.Option(10, "--scale", help="pixels per finished inch"),
    output: Path = typer.Option(Path("render.png"), "--output", "-o"),
) -> None:
    """Render the quilt to a synthetic PNG (plus ground-truth sidecar JSON)."""
    quilt = _load_or_exit(quilt_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    png_path, sidecar_path = save_render(quilt, output, level=level, seed=seed, scale=scale)
    typer.echo(f"wrote {png_path}")
    typer.echo(f"wrote {sidecar_path}")


@app.command()
def view(
    quilt_file: Path,
    output: Path = typer.Option(Path("viewer.html"), "--output", "-o"),
) -> None:
    """Emit the self-contained sizing viewer HTML for a quilt."""
    quilt = _load_or_exit(quilt_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_viewer(quilt, output)
    typer.echo(f"wrote {output}")


@app.command()
def export(
    quilt_file: Path,
    strategy: str = typer.Option("historical", "--strategy", "-s"),
    out: Path = typer.Option(Path("dist"), "--out", help="output directory"),
    formats: str | None = typer.Option(
        None, "--formats", help="comma-separated formats (default: all)"
    ),
) -> None:
    """Export pattern files (cut list, yardage, ...) for a quilt."""
    quilt = _load_or_exit(quilt_file)
    result = _plan_or_exit(quilt, strategy)
    selected = [f.strip() for f in formats.split(",")] if formats else None
    try:
        written = export_all(quilt, result, out, selected)
    except KeyError as e:
        typer.echo(f"error: {e.args[0]}", err=True)
        raise typer.Exit(1) from None
    for path in written:
        typer.echo(f"wrote {path}")
