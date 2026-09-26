"""Regression and unit tests for the centrifugal-pump calculations.

The golden numbers in :data:`GOLDEN_READINGS` were captured by running the
original ``centrifugal_pump.py`` script with the same inputs.  Two of them are
expected to match bit-for-bit; the brake power and the efficiency must **not**,
because version 2.0 replaced the lab manual's dimensionally wrong "equivalent
weight of water" of 28 with the hydraulic power ``rho * g * Q * H``.  Both the new
value and the size of the correction are pinned below.
"""

import pytest
from fluid_lab.centrifugal_pump import (
    DEFAULT_UNCERTAINTIES,
    CentrifugalPumpPerformance,
    CentrifugalPumpReadings,
    actual_discharge,
    brake_power,
    evaluate,
    format_report,
    indicated_power,
    total_head,
)
from fluid_lab.hydraulics import specific_weight_kn_m3
from fluid_lab.uncertainty import propagate

#: Inputs fed to the original script: ``12.5, 0.5, 120, 20``.
GOLDEN_READINGS = CentrifugalPumpReadings(
    time_for_100mm_rise_s=12.5,
    discharge_pressure_kgf_cm2=0.5,
    suction_vacuum_mm_hg=120.0,
    time_for_10_pulses_s=20.0,
)

#: The output power the original script reported for these inputs.
LEGACY_BRAKE_POWER_KW = 0.44230143999999993

#: ``28 / (rho * g)`` where ``rho * g = 9.81 kN/m^3``.
LEGACY_POWER_INFLATION = 28.0 / 9.81


def test_unchanged_values_still_match_the_original_script_bit_for_bit() -> None:
    result = evaluate(GOLDEN_READINGS)
    assert result.actual_discharge_m3_s == 0.00224  # "Q_act: 0.00224 m^3/s"
    assert result.total_head_m == 7.052  # "H: 7.052 m"
    assert result.indicated_power_kw == 0.5625  # "I.P.: 0.5625 kW"


def test_brake_power_now_uses_the_hydraulic_relation() -> None:
    """B.P. = rho * g * Q * H, not 28 * Q * H."""
    result = evaluate(GOLDEN_READINGS)
    assert result.brake_power_kw == 0.15496346879999998
    assert result.brake_power_kw == pytest.approx(specific_weight_kn_m3() * 0.00224 * 7.052)


def test_efficiency_dropped_because_the_power_constant_was_fixed() -> None:
    """The old 78.6 % was inflated by the wrong constant; the honest value is ~27.5 %."""
    result = evaluate(GOLDEN_READINGS)
    assert result.efficiency_percent == 27.549061119999998
    assert result.brake_power_kw * LEGACY_POWER_INFLATION == pytest.approx(
        LEGACY_BRAKE_POWER_KW, rel=1e-12
    )
    assert pytest.approx(2.8542, abs=1e-4) == LEGACY_POWER_INFLATION


def test_discharge_is_measured_tank_volume_over_time() -> None:
    """Q_act is (0.7 m x 0.4 m x 0.1 m) / t."""
    assert actual_discharge(10.0) == pytest.approx(0.28 * 0.1 / 10.0)


def test_total_head_sums_gauge_conversions_and_level_difference() -> None:
    """H = 10 * p_gauge + 13.6/1000 * vacuum + 0.42."""
    assert total_head(0.5, 120.0) == 5.0 + 1.632 + 0.42


def test_brake_power_scales_with_discharge_and_head() -> None:
    assert brake_power(0.00224, 7.052) == pytest.approx(9.81 * 0.00224 * 7.052)


def test_indicated_power_uses_the_energy_meter_constant() -> None:
    """I.P. = (3600 / 1600) * (5 / t)."""
    assert indicated_power(20.0) == (3600.0 / 1600.0) * (5.0 / 20.0)


@pytest.mark.parametrize("time_s", [0.0, -1.0, float("nan"), float("inf")])
def test_rejects_unusable_rise_time(time_s: float) -> None:
    with pytest.raises(ValueError, match="time for 100 mm rise"):
        actual_discharge(time_s)


@pytest.mark.parametrize("time_s", [0.0, -0.5])
def test_rejects_unusable_pulse_time(time_s: float) -> None:
    with pytest.raises(ValueError, match="energy-meter pulses"):
        indicated_power(time_s)


def test_evaluate_propagates_validation_errors() -> None:
    bad = CentrifugalPumpReadings(0.0, 0.5, 120.0, 20.0)
    with pytest.raises(ValueError, match="time for 100 mm rise"):
        evaluate(bad)


def test_results_are_immutable() -> None:
    result = evaluate(GOLDEN_READINGS)
    assert isinstance(result, CentrifugalPumpPerformance)
    with pytest.raises(AttributeError):
        result.total_head_m = 1.0  # type: ignore[misc]


def test_a_healthy_run_reports_no_warnings() -> None:
    assert evaluate(GOLDEN_READINGS).warnings() == ()
    assert evaluate(GOLDEN_READINGS).is_consistent()


def test_an_impossible_efficiency_is_flagged() -> None:
    """Efficiency above 100 % means a reading or a constant is wrong."""
    # A long pulse time makes I.P. tiny, so B.P./I.P. exceeds 100 %.
    impossible = CentrifugalPumpReadings(12.5, 0.5, 120.0, 100.0)
    result = evaluate(impossible)
    assert not result.is_consistent()
    assert result.indicated_power_kw == pytest.approx(0.1125)
    assert "exceeds 100 %" in result.warnings()[0]
    assert "! efficiency is" in format_report(result)


def test_report_labels_carry_units() -> None:
    report = format_report(evaluate(GOLDEN_READINGS))
    assert "Centrifugal pump test" in report
    assert "7.052 m" in report
    assert "0.5625 kW" in report
    assert "27.5491 %" in report


def test_report_can_show_standard_uncertainties() -> None:
    readings = GOLDEN_READINGS
    budget = propagate(evaluate, readings, DEFAULT_UNCERTAINTIES)
    report = format_report(evaluate(readings), budget)
    assert "+/-" in report
    assert "27.5 +/- 2.0 %" in report


def test_default_uncertainties_cover_every_reading() -> None:
    assert set(DEFAULT_UNCERTAINTIES) == {
        "time_for_100mm_rise_s",
        "discharge_pressure_kgf_cm2",
        "suction_vacuum_mm_hg",
        "time_for_10_pulses_s",
    }
