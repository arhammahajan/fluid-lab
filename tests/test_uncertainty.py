"""Tests for the uncertainty propagation.

The finite-difference sensitivities are validated against analytic derivatives of
simple synthetic functions, so a mistake in the differentiation or the
quadrature would show up here rather than only in the experiment modules.
"""

import math
from dataclasses import dataclass

import pytest
from fluid_lab import centrifugal_pump
from fluid_lab.centrifugal_pump import CentrifugalPumpReadings, evaluate
from fluid_lab.uncertainty import UncertaintyBudget, propagate


@dataclass(frozen=True, slots=True)
class TwoReadings:
    """Minimal readings dataclass for the synthetic checks."""

    a: float
    b: float


@dataclass(frozen=True, slots=True)
class Product:
    """Result of multiplying the two readings."""

    value: float


@dataclass(frozen=True, slots=True)
class SquareRoot:
    """Result of a square root, used to exercise the domain check."""

    value: float


def product(readings: TwoReadings) -> Product:
    """Return ``a * b``, whose relative uncertainty adds in quadrature."""
    return Product(readings.a * readings.b)


def square_root(readings: TwoReadings) -> SquareRoot:
    """Return ``sqrt(a)``; raises outside the valid domain like the real modules."""
    if readings.a <= 0.0:
        raise ValueError("a must be positive")
    return SquareRoot(math.sqrt(readings.a))


def test_product_uncertainty_matches_the_analytic_quadrature() -> None:
    """u(ab) = sqrt((b*u_a)^2 + (a*u_b)^2)."""
    budget = propagate(product, TwoReadings(a=3.0, b=4.0), {"a": 0.1, "b": 0.2})
    expected = math.sqrt((4.0 * 0.1) ** 2 + (3.0 * 0.2) ** 2)
    assert budget.standard_uncertainty["value"] == pytest.approx(expected, rel=1e-6)


def test_zero_uncertainty_contributes_nothing() -> None:
    """A reading declared exact is skipped entirely, producing no contribution."""
    exact = propagate(product, TwoReadings(a=3.0, b=4.0), {"a": 0.1, "b": 0.0})
    assert exact.standard_uncertainty["value"] == pytest.approx(4.0 * 0.1, rel=1e-6)
    assert ("value", "b") not in exact.contributions
    assert exact.dominant_source("value") == "a"


def test_omitted_readings_are_treated_as_exact() -> None:
    budget = propagate(product, TwoReadings(a=3.0, b=4.0), {"a": 0.1})
    assert budget.standard_uncertainty["value"] == pytest.approx(0.4, rel=1e-6)


def test_dominant_source_picks_the_largest_contribution() -> None:
    """A's contribution is 0.4 and b's is 0.6, so b dominates."""
    budget = propagate(product, TwoReadings(a=3.0, b=4.0), {"a": 0.1, "b": 0.2})
    assert budget.dominant_source("value") == "b"
    assert budget.contributions[("value", "a")] == pytest.approx(0.4, rel=1e-6)
    assert budget.contributions[("value", "b")] == pytest.approx(0.6, rel=1e-6)


def test_dominant_source_is_none_for_an_unknown_result() -> None:
    budget = propagate(product, TwoReadings(a=3.0, b=4.0), {"a": 0.1})
    assert budget.dominant_source("not_a_field") is None


def test_zero_reading_uses_an_absolute_step() -> None:
    """A zero reading would give a zero relative step; it must still work."""
    budget = propagate(product, TwoReadings(a=0.0, b=4.0), {"a": 0.1})
    assert budget.standard_uncertainty["value"] == pytest.approx(0.4, rel=1e-6)


def test_one_sided_difference_when_a_step_leaves_the_domain() -> None:
    """``a - step`` is negative here, so the backward difference is unavailable."""
    budget = propagate(square_root, TwoReadings(a=1e-7, b=0.0), {"a": 1e-9})
    assert budget.standard_uncertainty["value"] > 0.0
    assert math.isfinite(budget.standard_uncertainty["value"])


def test_as_columns_prefixes_the_field_names() -> None:
    budget = propagate(product, TwoReadings(a=3.0, b=4.0), {"a": 0.1})
    assert set(budget.as_columns()) == {"u_value"}


def test_every_result_field_gets_an_uncertainty_entry() -> None:
    readings = CentrifugalPumpReadings(12.5, 0.5, 120.0, 20.0)
    budget = propagate(evaluate, readings, centrifugal_pump.DEFAULT_UNCERTAINTIES)
    assert set(budget.standard_uncertainty) == {
        "actual_discharge_m3_s",
        "total_head_m",
        "brake_power_kw",
        "indicated_power_kw",
        "efficiency_percent",
    }


def test_pump_discharge_uncertainty_matches_volume_over_time() -> None:
    """Q = V/t, so u(Q) = V * u(t) / t^2, which is exactly what a hand calc gives."""
    readings = CentrifugalPumpReadings(12.5, 0.5, 120.0, 20.0)
    budget = propagate(evaluate, readings, {"time_for_100mm_rise_s": 0.2})
    volume = 0.7 * 0.4 * 0.1
    assert budget.standard_uncertainty["actual_discharge_m3_s"] == pytest.approx(
        volume * 0.2 / 12.5**2, rel=1e-6
    )


def test_pump_input_power_uncertainty_matches_the_energy_meter_relation() -> None:
    readings = CentrifugalPumpReadings(12.5, 0.5, 120.0, 20.0)
    budget = propagate(evaluate, readings, {"time_for_10_pulses_s": 0.2})
    factor = 3600.0 / 1600.0 * 5.0
    assert budget.standard_uncertainty["indicated_power_kw"] == pytest.approx(
        factor * 0.2 / 20.0**2, rel=1e-6
    )


def test_pump_uncertainty_budget_is_dominated_by_different_readings() -> None:
    readings = CentrifugalPumpReadings(12.5, 0.5, 120.0, 20.0)
    budget = propagate(evaluate, readings, centrifugal_pump.DEFAULT_UNCERTAINTIES)
    assert budget.dominant_source("actual_discharge_m3_s") == "time_for_100mm_rise_s"
    assert budget.dominant_source("total_head_m") == "discharge_pressure_kgf_cm2"


def test_synthetic_results_are_reported_as_a_budget() -> None:
    budget = propagate(product, TwoReadings(a=1.0, b=1.0), {"a": 0.1, "b": 0.1})
    assert isinstance(budget, UncertaintyBudget)


def test_rejects_an_unknown_reading_name() -> None:
    with pytest.raises(ValueError, match="is not a reading of TwoReadings"):
        propagate(product, TwoReadings(a=1.0, b=1.0), {"c": 0.1})


@pytest.mark.parametrize("uncertainty", [-0.1, float("nan"), float("inf")])
def test_rejects_an_unusable_uncertainty(uncertainty: float) -> None:
    with pytest.raises(ValueError, match="must be finite and non-negative"):
        propagate(product, TwoReadings(a=1.0, b=1.0), {"a": uncertainty})
