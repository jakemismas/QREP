"""Views for screening and proposing corpus truth, and the committed copies (plan D3a).

Screening reads sheets of fetched photos at a size where the piecing shows; proposers read a
ruler view whose grid labels are source-image pixels, plus zooms of any region, so a corner
read off a view is already in the annotation's coordinates. Nothing here runs QREP: a proposal
must never be seeded from QREP output (plan section 8.2). Views are written beside the cache,
inside the main checkout's ignored corpus/private/, and never into a worktree.

Usage:
    python scripts/eval/corpus_screen.py sheets OUT_DIR IMAGE...
    python scripts/eval/corpus_screen.py ruler IMAGE OUT_PNG
    python scripts/eval/corpus_screen.py zoom IMAGE X0 Y0 X1 Y1 OUT_PNG
    python scripts/eval/corpus_screen.py corners IMAGE OUT_DIR
    python scripts/eval/corpus_screen.py downsize IMAGE OUT_JPG
"""

import argparse
import hashlib
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

# Museum scans run to several thousand pixels; a 700 px tile still shows a 15 x 15 field's
# squares at about 40 px each, enough to tell squares from triangles.
SHEET_TILE = 700
SHEET_COLUMNS = 2
SHEET_PER_PAGE = 4
RULER_SIDE = 1400
ZOOM_SIDE = 900
CORNER_FRACTION = 0.2
# Plan D3a, criterion 10: committed copies are at most 800 px on the long side.
COMMIT_SIDE = 800
JPEG_QUALITY = 90
LABEL = (255, 0, 160)


def _font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _open(path: Path) -> Image.Image:
    # Pixels as the file stores them, before any EXIF rotation: annotation coordinates
    # index the image the way a decoder that ignores orientation reads it, and the
    # museum scans carry no rotation tag.
    with Image.open(path) as image:
        return image.convert("RGB")


def _nice_step(span: float, lines: int) -> int:
    raw = span / lines
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 5, 10):
        if raw <= factor * magnitude:
            return int(factor * magnitude)
    return int(10 * magnitude)


def _grid(view: Image.Image, origin: tuple[float, float], scale: float, step: int) -> None:
    """Grid lines every step source pixels, labeled in source pixels."""
    draw = ImageDraw.Draw(view)
    font = _font(16)
    ox, oy = origin
    width, height = view.size
    first_x = math.ceil(ox / step) * step
    first_y = math.ceil(oy / step) * step
    for sx in range(first_x, int(ox + width / scale) + 1, step):
        x = (sx - ox) * scale
        draw.line([(x, 0), (x, height)], fill=LABEL, width=1)
        draw.text((x + 2, 2), str(sx), fill=LABEL, font=font)
    for sy in range(first_y, int(oy + height / scale) + 1, step):
        y = (sy - oy) * scale
        draw.line([(0, y), (width, y)], fill=LABEL, width=1)
        draw.text((2, y + 2), str(sy), fill=LABEL, font=font)


def ruler(path: Path, out: Path, side: int = RULER_SIDE) -> float:
    """The whole photo at most side px, gridded in source pixels; returns the scale."""
    image = _open(path)
    scale = min(1.0, side / max(image.size))
    view = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    _grid(view, (0, 0), scale, _nice_step(max(image.size), 12))
    ImageDraw.Draw(view).text(
        (8, view.height - 24), f"{path.name}  {image.width} x {image.height} px",
        fill=LABEL, font=_font(18),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    view.save(out)
    return scale


def zoom(path: Path, box: tuple[int, int, int, int], out: Path, side: int = ZOOM_SIDE) -> float:
    """A source-pixel region scaled to side px, gridded in source pixels."""
    image = _open(path)
    x0, y0, x1, y1 = (max(0, box[0]), max(0, box[1]), min(image.width, box[2]),
                      min(image.height, box[3]))
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"empty region {box} on a {image.width} x {image.height} image")
    crop = image.crop((x0, y0, x1, y1))
    scale = side / max(crop.size)
    view = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    _grid(view, (x0, y0), scale, _nice_step(max(crop.size), 10))
    out.parent.mkdir(parents=True, exist_ok=True)
    view.save(out)
    return scale


def corners(path: Path, out_dir: Path, fraction: float = CORNER_FRACTION) -> list[Path]:
    """Zooms of the four corner regions, named by corner."""
    with Image.open(path) as image:
        width, height = image.size
    dx, dy = round(width * fraction), round(height * fraction)
    boxes = {
        "top_left": (0, 0, dx, dy),
        "top_right": (width - dx, 0, width, dy),
        "bottom_right": (width - dx, height - dy, width, height),
        "bottom_left": (0, height - dy, dx, height),
    }
    written = []
    for name, box in boxes.items():
        out = out_dir / f"{path.stem}.{name}.png"
        zoom(path, box, out)
        written.append(out)
    return written


def sheets(paths: list[Path], out_dir: Path) -> list[Path]:
    """Screening sheets of SHEET_PER_PAGE photos, each tile labeled with its file stem."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = math.ceil(SHEET_PER_PAGE / SHEET_COLUMNS)
    written = []
    for page, start in enumerate(range(0, len(paths), SHEET_PER_PAGE), 1):
        sheet = Image.new("RGB", (SHEET_TILE * SHEET_COLUMNS, (SHEET_TILE + 30) * rows), "white")
        draw = ImageDraw.Draw(sheet)
        for i, path in enumerate(paths[start:start + SHEET_PER_PAGE]):
            tile = ImageOps.contain(_open(path), (SHEET_TILE, SHEET_TILE), Image.LANCZOS)
            x, y = (i % SHEET_COLUMNS) * SHEET_TILE, (i // SHEET_COLUMNS) * (SHEET_TILE + 30)
            sheet.paste(tile, (x, y + 30))
            draw.text((x + 4, y + 4), path.stem, fill="black", font=_font(20))
        out = out_dir / f"sheet-{page:03d}.jpg"
        sheet.save(out, quality=85)
        written.append(out)
    return written


def downsize(path: Path, out: Path, side: int = COMMIT_SIDE) -> tuple[str, int, int]:
    """A committed copy at most side px on the long side; returns its sha256 and size."""
    image = _open(path)
    copy = ImageOps.contain(image, (side, side), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    copy.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return hashlib.sha256(out.read_bytes()).hexdigest(), copy.width, copy.height


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("sheets")
    p.add_argument("out_dir", type=Path)
    p.add_argument("images", type=Path, nargs="+")
    p = sub.add_parser("ruler")
    p.add_argument("image", type=Path)
    p.add_argument("out", type=Path)
    p = sub.add_parser("zoom")
    p.add_argument("image", type=Path)
    p.add_argument("box", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    p.add_argument("out", type=Path)
    p = sub.add_parser("corners")
    p.add_argument("image", type=Path)
    p.add_argument("out_dir", type=Path)
    p = sub.add_parser("downsize")
    p.add_argument("image", type=Path)
    p.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "sheets":
        for out in sheets(args.images, args.out_dir):
            print(out)
    elif args.command == "ruler":
        print(f"scale {ruler(args.image, args.out):.4f}")
    elif args.command == "zoom":
        print(f"scale {zoom(args.image, tuple(args.box), args.out):.4f}")
    elif args.command == "corners":
        for out in corners(args.image, args.out_dir):
            print(out)
    else:
        sha, width, height = downsize(args.image, args.out)
        print(f"{sha} {width} {height}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
