"""Rendering of calculation results as aligned, unit-annotated tables.

The original scripts printed values with fixed labels and no alignment, which
made a transcribed lab report easy to misread.  Results are modelled as
:class:`Quantity` rows and rendered by :func:`format_report`.

When an uncertainty is attached to a row, the value is rounded to the precision
implied by that uncertainty (two significant digits on the uncertainty) rather
than to a fixed number of digits, which is the accepted way to quote an
experimental result.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

SYMBOL_WIDTH = 6
"""Width of the engineering-symbol column, in characters."""

VALUE_WIDTH = 14
"""Width of the numeric column when no uncertainty is shown, in characters."""

SIGNIFICANT_DIGITS = 6
"""Number of significant digits used when printing a value without uncertainty."""

UNCERTAINTY_SIGNIFICANT_DIGITS = 1
"""Extra digits kept on the uncertainty before rounding to two significant ones."""


@dataclass(frozen=True, slots=True)
class Quantity:
    """One named result, ready to be printed.

    Attributes:
        field: Name of the field on the results dataclass, used to match an
            uncertainty to this row.
        symbol: Short engineering symbol, e.g. ``"Q_act"``.
        name: Human-readable description, e.g. ``"actual discharge"``.
        value: Numeric value expressed in ``unit``.
        unit: Unit string.  ASCII-only, for maximum terminal compatibility.
        uncertainty: Absolute standard uncertainty in the same unit, if known.
    """

    field: str
    symbol: str
    name: str
    value: float
    unit: str
    uncertainty: float | None = None

    @property
    def label(self) -> str:
        """Return the combined symbol-and-description label."""
        return f"{self.symbol:<{SYMBOL_WIDTH}}{self.name}"

    def render(self, label_width: int) -> str:
        """Return this quantity as one aligned table row.

        Args:
            label_width: Width of the left-hand label column.
        """
        return f"{self.label:<{label_width}}  {self._rendered_value()} {self.unit}"

    def _rendered_value(self) -> str:
        """Return the value, with an uncertainty where one is known."""
        if self.uncertainty is None or not _usable(self.uncertainty):
            return f"{self.value:>{VALUE_WIDTH}.{SIGNIFICANT_DIGITS}g}"
        decimals = _decimals_for(self.uncertainty)
        return f"{self.value:.{decimals}f} +/- {self.uncertainty:.{decimals}f}"


def attach_uncertainties(
    quantities: Iterable[Quantity],
    values: Mapping[str, float],
) -> tuple[Quantity, ...]:
    """Return ``quantities`` with uncertainties looked up by field name.

    Args:
        quantities: Rows to annotate.
        values: Result field name -> absolute standard uncertainty.

    Returns:
        A new tuple of rows; rows with no matching entry are unchanged.
    """
    return tuple(
        replace(quantity, uncertainty=values.get(quantity.field))
        if quantity.field in values
        else quantity
        for quantity in quantities
    )


def format_report(
    title: str,
    quantities: Iterable[Quantity],
    *,
    notes: Iterable[str] = (),
) -> str:
    """Render ``quantities`` as a titled, aligned table.

    Args:
        title: Table heading.
        quantities: Rows to print, in display order.
        notes: Optional warning lines appended below the table, each prefixed
            with ``!`` so that they stand out from the numbers.

    Returns:
        A multi-line string with no trailing newline.
    """
    rows = tuple(quantities)
    width = max((len(row.label) for row in rows), default=0)
    lines = [title, "=" * len(title)]
    lines.extend(row.render(width) for row in rows)
    lines.extend(f"! {note}" for note in notes)
    return "\n".join(lines)


def _usable(uncertainty: float) -> bool:
    """Whether an uncertainty can be used to set the displayed precision."""
    return math.isfinite(uncertainty) and uncertainty > 0.0


def _decimals_for(uncertainty: float) -> int:
    """Return the decimal places implied by a two-significant-digit uncertainty.

    For example ``4.0e-5`` implies 6 decimals (``0.000040``) and ``3.2`` implies
    one decimal (``3.2``).
    """
    exponent = math.floor(math.log10(uncertainty))
    return max(0, -(exponent - UNCERTAINTY_SIGNIFICANT_DIGITS))
