"""Regression and unit tests for the Francis-turbine calculations.

Version 2.0 changed two things, both deliberate and both pinned here:

* the venturimeter head is now the standard mercury-U-tube relation
  ``h = (rho_Hg / rho_w - 1) R = 12.6 R`` instead of the original ``10.33 R``;
* the head gained an optional datum term, defaulting to zero so that the
  original behaviour is reproduced when no datum was recorded.

The vacuum conversion also moved from the original ``1.033/76`` to the shared
``13.6/1000`` mercury factor, a 0.015 % shift.
"""

from math import pi, sqrt

import pytest
from fluid_lab.francis_turbine import (
    DEFAULT_UNCERTAINTIES,
    EFFECTIVE_BRAKE_RADIUS_M,
    MANOMETER_HEAD_FACTOR,
    PIPE_AREA_M2,
    THROAT_AREA_M2,
    FrancisTurbineReadings,
    discharge,
    evaluate,
    format_report,
    input_power,
    manometer_head,
    output_power,
    torque,
    total_head,
)
from fluid_lab.uncertainty import propagate
from fluid_lab.units import vacuum_to_head_m

#: Inputs fed to the original script: ``0.4, 100, 0.35, 5, 1.5, 900``.
GOLDEN_READINGS = FrancisTurbineReadings(
    discharge_pressure_kgf_cm2=0.4,
    suction_vacuum_mm_hg=100.0,
    manometer_deflection_m=0.35,
    tight_side_mass_kg=5.0,
    slack_side_mass_kg=1.5,
    speed_rpm=900.0,
)

#: Relative tolerance that covers the 0.015 % mercury-constant shift.
MERCURY_TOL = 1e-3


def test_unchanged_values_still_match_the_original_script_bit_for_bit() -> None:
    result = evaluate(GOLDEN_READINGS)
    assert result.pipe_area_m2 == 0.005026548245743669
    assert result.throat_area_m2 == 0.0015904312808798326
    assert result.torque_nm == 4.050980640000001
    assert result.output_power_kw == 0.3817959305537544


def test_head_carries_only_the_documented_mercury_shift() -> None:
    """The head depends on the vacuum conversion, not on the manometer factor."""
    result = evaluate(GOLDEN_READINGS)
    assert result.total_head_m == 5.36
    assert result.total_head_m == pytest.approx(5.359210526315789, rel=MERCURY_TOL)


def test_manometer_factor_change_moved_discharge_and_power() -> None:
    """H = 12.6 R instead of 10.33 R: h, Q, E_i and eta all move with it.

    Q scales as sqrt(h), so the 12.6/10.33 change raises the discharge by 10.4 %
    and brings the efficiency down from the original 53.02 %.
    """
    result = evaluate(GOLDEN_READINGS)
    assert result.manometer_head_m == pytest.approx(4.41)
    assert result.manometer_head_m == pytest.approx(0.35 * 12.6)
    assert result.discharge_m3_s == pytest.approx(0.015127300355055676)
    assert result.discharge_m3_s / 0.013697027199218507 == pytest.approx(
        (12.6 / 10.33) ** 0.5, rel=1e-9
    )
    assert result.input_power_kw == pytest.approx(0.7954176563493955)
    assert result.efficiency_percent == pytest.approx(47.999428665692896)
    assert result.efficiency_percent < 53.01944187760716


def test_vacuum_conversion_now_uses_the_shared_mercury_density() -> None:
    """The one intentional numerical change, documented rather than silent."""
    legacy = 100.0 * 1.033 / 76
    current = vacuum_to_head_m(100.0)
    assert current == 100.0 * 13.6 / 1000
    assert current != legacy
    assert current == pytest.approx(legacy, rel=MERCURY_TOL)


def test_head_is_pressure_plus_vacuum_head() -> None:
    assert total_head(0.4, 100.0) == 4.0 + 1.36


def test_datum_term_is_added_when_supplied() -> None:
    """The missing datum term of version 1.0 is now representable."""
    assert total_head(0.4, 100.0, 0.5) == 4.0 + 1.36 + 0.5
    with_datum = FrancisTurbineReadings(
        discharge_pressure_kgf_cm2=0.4,
        suction_vacuum_mm_hg=100.0,
        manometer_deflection_m=0.35,
        tight_side_mass_kg=5.0,
        slack_side_mass_kg=1.5,
        speed_rpm=900.0,
        datum_difference_m=0.25,
    )
    assert evaluate(with_datum).total_head_m == pytest.approx(5.36 + 0.25)


def test_datum_defaults_to_zero_so_old_records_still_reproduce() -> None:
    assert GOLDEN_READINGS.datum_difference_m == 0.0


def test_area_constants_come_from_the_pipe_and_throat_diameters() -> None:
    assert (pi / 4) * (0.08**2) == PIPE_AREA_M2
    assert (pi / 4) * (0.045**2) == THROAT_AREA_M2


def test_mercury_head_factor_accounts_for_the_water_column() -> None:
    """H = (S_Hg - 1) R; using the mercury column alone would overstate the head."""
    assert MANOMETER_HEAD_FACTOR == 13.6 - 1.0
    assert pytest.approx(12.6) == MANOMETER_HEAD_FACTOR


def test_manometer_head_uses_the_mercury_relation_not_10_33() -> None:
    assert manometer_head(0.35) == pytest.approx(0.35 * 12.6)
    assert manometer_head(0.35) != pytest.approx(0.35 * 10.33)
    assert manometer_head(0.0) == 0.0


def test_discharge_is_the_venturimeter_equation() -> None:
    head = manometer_head(0.35)
    expected = (0.97 * PIPE_AREA_M2 * THROAT_AREA_M2 * sqrt(2 * 9.81 * head)) / sqrt(
        PIPE_AREA_M2**2 - THROAT_AREA_M2**2
    )
    assert discharge(head) == expected


def test_discharge_grows_with_the_square_root_of_head() -> None:
    assert discharge(4.0) == pytest.approx(2 * discharge(1.0))


def test_input_power_is_rho_g_q_h_in_kilowatts() -> None:
    assert input_power(0.015127300355055676, 5.36) == pytest.approx(0.7954176563493955)


def test_effective_brake_radius_is_measured_to_the_rope_centreline() -> None:
    assert EFFECTIVE_BRAKE_RADIUS_M == (0.2 + 2 * 0.012) / 2


def test_torque_includes_the_hanger_and_rope_masses() -> None:
    assert torque(5.0, 1.5) == (5.0 + 0.094 + 0.093 - 1.5) * 9.81 * EFFECTIVE_BRAKE_RADIUS_M


def test_output_power_scales_with_speed() -> None:
    assert output_power(4.050980640000001, 900.0) == (2 * pi * 900.0 * 4.050980640000001) / (
        60.0 * 1000.0
    )


@pytest.mark.parametrize("reading", [-0.1, float("nan")])
def test_rejects_unusable_manometer_deflection(reading: float) -> None:
    with pytest.raises(ValueError, match="manometer deflection"):
        manometer_head(reading)


@pytest.mark.parametrize("speed_rpm", [-1.0, float("nan")])
def test_rejects_unusable_speed(speed_rpm: float) -> None:
    with pytest.raises(ValueError, match="turbine speed"):
        output_power(1.0, speed_rpm)


def test_rejects_zero_water_power() -> None:
    """A zero head makes the efficiency undefined rather than inf/nan."""
    no_head = FrancisTurbineReadings(
        discharge_pressure_kgf_cm2=0.0,
        suction_vacuum_mm_hg=0.0,
        manometer_deflection_m=0.35,
        tight_side_mass_kg=5.0,
        slack_side_mass_kg=1.5,
        speed_rpm=900.0,
    )
    with pytest.raises(ValueError, match="input \\(water\\) power"):
        evaluate(no_head)


def test_a_healthy_run_reports_no_warnings() -> None:
    assert evaluate(GOLDEN_READINGS).warnings() == ()


def test_swapped_spring_balances_are_flagged() -> None:
    """W2 greater than W1 plus the hanging masses gives negative torque."""
    swapped = FrancisTurbineReadings(
        discharge_pressure_kgf_cm2=0.4,
        suction_vacuum_mm_hg=100.0,
        manometer_deflection_m=0.35,
        tight_side_mass_kg=1.0,
        slack_side_mass_kg=9.0,
        speed_rpm=900.0,
    )
    result = evaluate(swapped)
    assert result.torque_nm < 0.0
    assert "spring balances are probably swapped" in result.warnings()[0]


def test_report_shows_head_and_efficiency() -> None:
    report = format_report(evaluate(GOLDEN_READINGS))
    assert "Francis turbine test" in report
    assert "5.36 m" in report
    assert "47.9994 %" in report


def test_report_can_show_standard_uncertainties() -> None:
    readings = GOLDEN_READINGS
    budget = propagate(evaluate, readings, DEFAULT_UNCERTAINTIES)
    report = format_report(evaluate(readings), budget)
    assert "+/-" in report


def test_default_uncertainties_cover_every_readable_field() -> None:
    assert set(DEFAULT_UNCERTAINTIES) == {
        "discharge_pressure_kgf_cm2",
        "suction_vacuum_mm_hg",
        "manometer_deflection_m",
        "tight_side_mass_kg",
        "slack_side_mass_kg",
        "speed_rpm",
        "datum_difference_m",
    }
