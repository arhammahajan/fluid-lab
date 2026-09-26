"""Propagation of measurement uncertainty through the experiment calculations.

For a result ``y = f(x_1 ... x_n)`` with independent readings, the combined
standard uncertainty is

    ``u(y) = sqrt( sum_i (df/dx_i)^2 * u(x_i)^2 )``

The partial derivatives are obtained by **central finite differences of the
existing ``evaluate`` function**.  Nothing is hand-derived, so editing a formula
cannot silently invalidate a sensitivity expression, and no experiment module
needs to maintain a second copy of its own physics.

The budget also records each reading's contribution ``|df/dx_i| * u(x_i)``, so
the dominant error source for a given result can be reported directly.

Note:
    This is a first-order (linear) treatment that assumes the readings are
    independent.  Any reading that appears in more than one place in a formula is
    handled correctly, but correlated instrument errors (for example a single
    thermometer used for both a head and a density correction) are not.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace
from typing import Any, Final

RELATIVE_STEP: Final[float] = 1e-5
"""Relative step used for the central differences.

Truncation error scales with ``step^2`` (~1e-10) and round-off with
``eps/step`` (~2e-11), so this balances the two without needing an analytic
derivative.
"""

ABSOLUTE_STEP: Final[float] = 1e-6
"""Step used when a reading is zero and a relative step would vanish."""


@dataclass(frozen=True, slots=True)
class UncertaintyBudget:
    """Combined standard uncertainties for one evaluated run."""

    standard_uncertainty: Mapping[str, float]
    """Result field name -> combined standard uncertainty ``u(y)``."""

    contributions: Mapping[tuple[str, str], float]
    """``(result field, reading field) -> |df/dx| * u(x)``."""

    def dominant_source(self, result_field: str) -> str | None:
        """Return the reading that contributes most to ``result_field``.

        Args:
            result_field: Name of a result attribute.

        Returns:
            The name of the largest-contributing reading field, or ``None`` when
            no reading contributes to the result.
        """
        candidates = {
            reading: contribution
            for (result, reading), contribution in self.contributions.items()
            if result == result_field
        }
        if not candidates:
            return None
        return max(candidates, key=lambda reading: candidates[reading])

    def as_columns(self) -> dict[str, float]:
        """Return the uncertainties keyed as ``u_<result field>`` for export."""
        return {f"u_{name}": value for name, value in self.standard_uncertainty.items()}


def propagate(
    evaluate: Callable[..., Any],
    readings: Any,
    uncertainties: Mapping[str, float],
) -> UncertaintyBudget:
    """Propagate reading uncertainties to every result of ``evaluate``.

    Args:
        evaluate: A pure ``readings -> results`` function, e.g.
            :func:`fluid_lab.centrifugal_pump.evaluate`.
        readings: An instance of the matching frozen readings dataclass.
        uncertainties: Absolute standard uncertainty for each reading to be
            included, keyed by attribute name.  Readings omitted from the mapping
            are treated as exact.  Non-numeric fields (such as the device type)
            must not appear here.

    Returns:
        The :class:`UncertaintyBudget` for this run.

    Raises:
        ValueError: If a key is not a readable numeric attribute of ``readings``,
            or if an uncertainty is negative.
    """
    baseline = evaluate(readings)
    result_names = [result_field.name for result_field in fields(baseline)]
    variances: dict[str, float] = {}
    contributions: dict[tuple[str, str], float] = {}

    for name, uncertainty in uncertainties.items():
        _require_readable(readings, name)
        if uncertainty < 0.0 or not math.isfinite(uncertainty):
            raise ValueError(f"uncertainty for {name!r} must be finite and non-negative")
        if uncertainty == 0.0:
            continue
        derivatives = _partial_derivatives(evaluate, readings, baseline, name)
        for result_name, partial in derivatives.items():
            contribution = abs(partial) * uncertainty
            contributions[(result_name, name)] = contribution
            variances[result_name] = variances.get(result_name, 0.0) + contribution**2

    budget = {name: math.sqrt(variances.get(name, 0.0)) for name in result_names}
    return UncertaintyBudget(standard_uncertainty=budget, contributions=contributions)


def _require_readable(readings: Any, name: str) -> None:
    """Raise ``ValueError`` unless ``name`` is a numeric field of ``readings``."""
    available = {field.name for field in fields(readings)}
    if name not in available:
        raise ValueError(
            f"{name!r} is not a reading of {type(readings).__name__}; "
            f"expected one of: {', '.join(sorted(available))}"
        )


def _partial_derivatives(
    evaluate: Callable[..., Any],
    readings: Any,
    baseline: Any,
    name: str,
) -> dict[str, float]:
    """Return ``{result field: df/dx_i}`` for the reading called ``name``.

    Falls back to a one-sided difference when the central step would leave the
    valid domain (for example a perturbation that would make a time negative).
    """
    value = float(getattr(readings, name))
    step = abs(value) * RELATIVE_STEP
    if step == 0.0:
        step = ABSOLUTE_STEP

    forward = _perturbed(evaluate, readings, name, value + step)
    backward = _perturbed(evaluate, readings, name, value - step)

    if forward is not None and backward is not None:
        return {
            result: (getattr(forward, result) - getattr(backward, result)) / (2 * step)
            for result in _numeric_fields(baseline)
        }
    if forward is not None:
        return {
            result: (getattr(forward, result) - getattr(baseline, result)) / step
            for result in _numeric_fields(baseline)
        }
    if backward is not None:
        return {
            result: (getattr(baseline, result) - getattr(backward, result)) / step
            for result in _numeric_fields(baseline)
        }
    return dict.fromkeys(_numeric_fields(baseline), 0.0)


def _numeric_fields(result: Any) -> list[str]:
    """Return the names of the result's float-valued fields."""
    return [
        field.name for field in fields(result) if isinstance(getattr(result, field.name), float)
    ]


def _perturbed(
    evaluate: Callable[..., Any],
    readings: Any,
    name: str,
    new_value: float,
) -> Any | None:
    """Evaluate with ``name`` replaced by ``new_value``, or ``None`` if invalid."""
    try:
        return evaluate(replace(readings, **{name: new_value}))
    except ValueError:
        return None
