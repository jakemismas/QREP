"""Exports: cut list, yardage, SVG diagrams, PDF booklet.

EXPORTERS maps format name -> callable(quilt, plan, out_dir) -> [written
paths]. S3 registers the text formats; S4 adds svg and pdf. The CLI's
--formats default is every registered format.
"""

from pathlib import Path

from qrep.construct.plan import ConstructionPlan
from qrep.construct.yardage import compute_purchase_lines
from qrep.export.cutlist import render_cutlist_csv, render_cutlist_md
from qrep.export.pdf import build_sections, render_booklet
from qrep.export.svg import (
    render_assembly_svg,
    render_block_svgs,
    render_strip_sets_svg,
    render_top_svg,
)
from qrep.export.yardage_report import render_yardage_md
from qrep.model.schema import Quilt


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def export_cutlist(quilt: Quilt, plan: ConstructionPlan, out_dir: Path) -> list[Path]:
    return [
        _write(out_dir / "cutlist.md", render_cutlist_md(quilt, plan)),
        _write(out_dir / "cutlist.csv", render_cutlist_csv(quilt, plan)),
    ]


def export_yardage(quilt: Quilt, plan: ConstructionPlan, out_dir: Path) -> list[Path]:
    report = compute_purchase_lines(quilt, plan)
    return [_write(out_dir / "yardage.md", render_yardage_md(report))]


def export_svg(quilt: Quilt, plan: ConstructionPlan, out_dir: Path) -> list[Path]:
    written = [_write(out_dir / "top.svg", render_top_svg(quilt))]
    for key, text in render_block_svgs(quilt).items():
        written.append(_write(out_dir / f"block_{key}.svg", text))
    strip_svg = render_strip_sets_svg(quilt, plan)
    if strip_svg is not None:
        written.append(_write(out_dir / "strip_sets.svg", strip_svg))
    written.append(_write(out_dir / "assembly.svg", render_assembly_svg(quilt)))
    return written


def export_pdf(quilt: Quilt, plan: ConstructionPlan, out_dir: Path) -> list[Path]:
    path = out_dir / "booklet.pdf"
    render_booklet(quilt, plan, path)
    return [path]


EXPORTERS = {
    "cutlist": export_cutlist,
    "yardage": export_yardage,
    "svg": export_svg,
    "pdf": export_pdf,
}


def export_all(
    quilt: Quilt,
    plan: ConstructionPlan,
    out_dir: str | Path,
    formats: list[str] | None = None,
) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    selected = formats if formats is not None else list(EXPORTERS)
    written: list[Path] = []
    for name in selected:
        if name not in EXPORTERS:
            raise KeyError(f"unknown export format {name!r}; available: {', '.join(EXPORTERS)}")
        written.extend(EXPORTERS[name](quilt, plan, out))
    return written


__all__ = [
    "EXPORTERS",
    "build_sections",
    "export_all",
    "render_assembly_svg",
    "render_block_svgs",
    "render_booklet",
    "render_cutlist_csv",
    "render_cutlist_md",
    "render_strip_sets_svg",
    "render_top_svg",
    "render_yardage_md",
]
