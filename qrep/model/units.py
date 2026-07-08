"""Integer-eighths units and the one shared human-facing length formatter.

All lengths in the model and in JSON are integer eighths of an inch:
1.5" = 12, 0.25" = 2, 3.75" = 30. Float inch arithmetic is forbidden in the
model and exports; this module is the only place eighths become strings.
"""

from math import gcd

EIGHTHS_PER_INCH = 8


def format_inches(eighths: int) -> str:
    """Render an integer-eighths length as a mixed-fraction inch string.

    12 -> '1 1/2"', 30 -> '3 3/4"', 2 -> '1/4"', 600 -> '75"', 0 -> '0"'.
    """
    sign = "-" if eighths < 0 else ""
    whole, rem = divmod(abs(eighths), EIGHTHS_PER_INCH)
    if rem == 0:
        body = str(whole)
    else:
        g = gcd(rem, EIGHTHS_PER_INCH)
        num, den = rem // g, EIGHTHS_PER_INCH // g
        body = f"{num}/{den}" if whole == 0 else f"{whole} {num}/{den}"
    return f'{sign}{body}"'
