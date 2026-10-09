"""Cutting math: strip yields, strip sets, borders and top fabrics (MATH.md F2 to F5).

A fabric's length is the sum of its strip plans, never an area estimate. Every
length is integer eighths and every division rounds in integers, never through
a float. Usable width, join loss, seam allowance, margin and increment are
arguments, so these functions read no settings and depend on no planner.
"""

from collections import Counter
from collections.abc import Iterable, Sequence

from pydantic import BaseModel


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


class StripYield(BaseModel):
    strip_width: int
    subcut: int  # the side cut off along the strip; the whole piece for a joined cut
    pieces_per_strip: int | None  # None for a joined cut
    strips: int
    strips_per_piece: int  # k strips joined end to end; 1 unless joined
    last_strip_pieces: int | None  # None for a joined cut
    length: int  # strips x strip_width


class StripSetPlan(BaseModel):
    per_set: int
    sets: int
    fabric_strips: dict[str, int]  # sets x the fabric's count in the sequence


class BorderPiece(BaseModel):
    cut_length: int  # each of the pair is trimmed to this
    strips_per_piece: int  # 1 when the piece fits one strip
    strips: int  # for the pair: 1 when both fit one strip


class BorderBand(BaseModel):
    band_width: int  # finished b
    inner_width: int
    inner_length: int
    strip_width: int
    sides: BorderPiece
    top_bottom: BorderPiece
    strips: int
    length: int  # strips x strip_width


class TopFabricPlan(BaseModel):
    length_needed: int  # sum of the strip plans, before the margin
    purchase: int
    increments: int


def pieces_per_strip(cut_length: int, usable_width: int) -> int:
    if not 0 < cut_length <= usable_width:
        raise ValueError(
            f"cut length {cut_length} must be positive and no longer than the usable width "
            f"{usable_width}"
        )
    return usable_width // cut_length


def joined_strip_count(piece_length: int, usable_width: int, join_loss: int) -> int:
    """F4: each straight join between strips uses join_loss of length."""
    if piece_length <= usable_width:
        return 1
    if not 0 <= join_loss < usable_width:
        raise ValueError(
            f"join loss {join_loss} must be at least 0 and shorter than the usable width "
            f"{usable_width}"
        )
    return _ceil_div(piece_length - join_loss, usable_width - join_loss)


def with_margin(length: int, margin_percent: int) -> int:
    if margin_percent < 0:
        raise ValueError(f"margin {margin_percent} percent must be at least 0")
    # Integers only: ceil(200 x 1.1) is 221 in binary floating point (V-UNIT-02).
    return _ceil_div(length * (100 + margin_percent), 100)


def purchase_increments(purchase: int, increment: int) -> int:
    if increment < 1:
        raise ValueError(f"purchase increment {increment} must be at least 1")
    return _ceil_div(purchase, increment)


def _subcut_yield(quantity: int, strip_width: int, subcut: int, usable_width: int) -> StripYield:
    per = pieces_per_strip(subcut, usable_width)
    strips = _ceil_div(quantity, per)
    return StripYield(
        strip_width=strip_width,
        subcut=subcut,
        pieces_per_strip=per,
        strips=strips,
        strips_per_piece=1,
        last_strip_pieces=quantity - (strips - 1) * per,
        length=strips * strip_width,
    )


def strip_yield(
    quantity: int, side_a: int, side_b: int, usable_width: int, join_loss: int
) -> StripYield:
    """F2: the cheaper orientation for one cut line of identical pieces."""
    if quantity < 1:
        raise ValueError(f"quantity {quantity} must be at least 1")
    short, long = sorted((side_a, side_b))
    if short > usable_width:
        raise ValueError(
            f"both sides of a {side_a} x {side_b} piece exceed the usable width {usable_width}"
        )
    if long <= usable_width:
        first = _subcut_yield(quantity, short, long, usable_width)
    else:
        # Orientation 1 cannot subcut a side longer than the strip, so each
        # piece is joined from k strips the way a border piece is (MATH.md F2).
        k = joined_strip_count(long, usable_width, join_loss)
        first = StripYield(
            strip_width=short,
            subcut=long,
            pieces_per_strip=None,
            strips=quantity * k,
            strips_per_piece=k,
            last_strip_pieces=None,
            length=quantity * k * short,
        )
    second = _subcut_yield(quantity, long, short, usable_width)
    # A tie keeps the narrower strip, which is always the first candidate.
    return second if second.length < first.length else first


def strip_set_plan(
    segments_needed: int, segment_cut_width: int, sequence: Sequence[str], usable_width: int
) -> StripSetPlan:
    """F3: one strip of each fabric in the sequence per set."""
    if segments_needed < 0:
        raise ValueError(f"segments needed {segments_needed} must be at least 0")
    per_set = pieces_per_strip(segment_cut_width, usable_width)
    sets = _ceil_div(segments_needed, per_set)
    counts = Counter(sequence)
    return StripSetPlan(
        per_set=per_set,
        sets=sets,
        fabric_strips={fabric: sets * count for fabric, count in counts.items()},
    )


def _border_pair(cut_length: int, usable_width: int, join_loss: int) -> BorderPiece:
    k = joined_strip_count(cut_length, usable_width, join_loss)
    if k == 1:
        # Only the two identical pieces of a pair share a strip (MATH.md F4).
        strips = _ceil_div(2, pieces_per_strip(cut_length, usable_width))
    else:
        strips = 2 * k
    return BorderPiece(cut_length=cut_length, strips_per_piece=k, strips=strips)


def border_bands(
    center_width: int,
    center_length: int,
    band_widths: Iterable[int],
    usable_width: int,
    join_loss: int,
    seam_allowance: int,
) -> list[BorderBand]:
    """F4: sides first, then top and bottom, per band from the center outward."""
    if seam_allowance < 0:
        raise ValueError(f"seam allowance {seam_allowance} must be at least 0")
    cut_extra = 2 * seam_allowance
    inner_width, inner_length = center_width, center_length
    bands = []
    for band_width in band_widths:
        if band_width < 1:
            raise ValueError(f"border band width {band_width} must be at least 1")
        strip_width = band_width + cut_extra
        sides = _border_pair(inner_length + cut_extra, usable_width, join_loss)
        top_bottom = _border_pair(
            inner_width + 2 * band_width + cut_extra, usable_width, join_loss
        )
        strips = sides.strips + top_bottom.strips
        bands.append(
            BorderBand(
                band_width=band_width,
                inner_width=inner_width,
                inner_length=inner_length,
                strip_width=strip_width,
                sides=sides,
                top_bottom=top_bottom,
                strips=strips,
                length=strips * strip_width,
            )
        )
        inner_width += 2 * band_width
        inner_length += 2 * band_width
    return bands


def top_fabric_plan(
    plan_lengths: Iterable[int], margin_percent: int, increment: int
) -> TopFabricPlan:
    """F5: plan_lengths are the fabric's F2 line lengths, F4 band lengths and
    F3 strip-set strips x strip width."""
    length = sum(plan_lengths)
    purchase = with_margin(length, margin_percent)
    return TopFabricPlan(
        length_needed=length,
        purchase=purchase,
        increments=purchase_increments(purchase, increment),
    )
