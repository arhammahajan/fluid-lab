"""Regression and unit tests for the orifice / mouthpiece calculations.

The golden numbers were captured by running the original
``orifice_mouthpiece.py`` script with the same inputs.  Every value is reproduced
to within one ULP: version 2.0 replaced the bare ``0.00875 m^3`` collected-volume
literal with ``area x rise``, and ``0.175 * 0.05`` is not bit-identical to
``0.00875`` in binary floating point.  The difference is ~2e-16 relative and is
pinned by :func:`test_tank_volume_is_now_area_times_rise`.

The golden input set is physically impossible (it yields ``C_d > 1`` because the
collecting time is far too short for the stated head).  It is kept as the
regression fixture precisely because it exercises the inconsistency warning;
:data:`CONSISTENT_READINGS` is the textbook-realistic counterpart.
"""

from math import pi, sqrt

import pytest
from fluid_lab.orifice_mouthpiece import (
    COLLECTING_TANK_AREA_M2,
    COLLECTING_TANK_RISE_M,
    COLLECTING_TANK_VOLUME_M3,
    DEFAULT_UNCERTAINTIES,
    DEVICE_CHARACTERISTICS,
    ORIFICE_AREA_M2,
    OrificeDevice,
    OrificeMouthpieceReadings,
    TrajectoryPoint,
    actual_discharge,
    coefficient_of_velocity,
    coefficient_of_velocity_from_trajectory,
    evaluate,
    format_report,
    theoretical_discharge,
)
from fluid_lab.uncertainty import propagate

ULEP_TOLERANCE = 1e-12
"""Relative tolerance covering the one-ULP tank-volume change."""

#: Inputs fed to the original script: ``15, 180, 25, 5``.
GOLDEN_READINGS = OrificeMouthpieceReadings(
    time_for_50mm_rise_s=15.0,
    head_over_orifice_mm=180.0,
    horizontal_distance_cm=25.0,
    vertical_distance_cm=5.0,
)

#: A textbook-like run: H = 600 mm, t = 18.12 s, x = 47.5 cm, y = 10 cm.
CONSISTENT_READINGS = OrificeMouthpieceReadings(
    time_for_50mm_rise_s=18.12,
    head_over_orifice_mm=600.0,
    horizontal_distance_cm=47.5,
    vertical_distance_cm=10.0,
)


def test_matches_original_script_to_within_one_ulp() -> None:
    """Every published number is reproduced (bar the tank-volume ULP)."""
    result = evaluate(GOLDEN_READINGS)
    assert result.actual_discharge_m3_s == pytest.approx(0.0005833333333333334, rel=ULEP_TOLERANCE)
    assert result.theoretical_discharge_m3_s == 0.0004265534689361962
    assert result.coefficient_of_discharge == pytest.approx(1.367550320920232, rel=ULEP_TOLERANCE)
    assert result.coefficient_of_velocity == 1.317615691736825
    assert result.coefficient_of_contraction == pytest.approx(
        1.0378977189605152, rel=ULEP_TOLERANCE
    )


def test_tank_volume_is_now_area_times_rise() -> None:
    """The bare 0.00875 literal became area x rise, worth one ULP."""
    assert COLLECTING_TANK_VOLUME_M3 == COLLECTING_TANK_AREA_M2 * COLLECTING_TANK_RISE_M
    assert pytest.approx(0.00875, rel=ULEP_TOLERANCE) == COLLECTING_TANK_VOLUME_M3
    assert COLLECTING_TANK_VOLUME_M3 != 0.00875  # one ULP below the old literal


def test_orifice_area_comes_from_the_diameter() -> None:
    assert (pi / 4) * (0.017**2) == ORIFICE_AREA_M2


def test_actual_discharge_is_the_collected_volume_over_time() -> None:
    assert actual_discharge(15.0) == COLLECTING_TANK_VOLUME_M3 / 15.0


def test_theoretical_discharge_is_the_torricelli_equation() -> None:
    assert theoretical_discharge(0.18) == ORIFICE_AREA_M2 * sqrt(2 * 9.81 * 0.18)
    assert theoretical_discharge(0.18) == pytest.approx(0.0004265534689361962)


def test_velocity_coefficient_follows_the_projectile_relation() -> None:
    """C_v = x / sqrt(4 y H), so C_v grows with x and falls with y and H."""
    assert coefficient_of_velocity(0.25, 0.05, 0.18) == pytest.approx(1.317615691736825)
    assert coefficient_of_velocity(0.5, 0.05, 0.18) > coefficient_of_velocity(0.25, 0.05, 0.18)
    assert coefficient_of_velocity(0.25, 0.1, 0.18) < coefficient_of_velocity(0.25, 0.05, 0.18)


# --------------------------------------------------------------------------- #
# Multi-point trajectory regression
# --------------------------------------------------------------------------- #


def trajectory_for(
    coefficient: float,
    head_m: float,
    coordinates: tuple[float, ...],
) -> list[TrajectoryPoint]:
    """Build exactly-on-trajectory points for a chosen ``C_v`` and head."""
    slope = 1.0 / (4.0 * coefficient**2 * head_m)
    return [TrajectoryPoint(x, slope * x**2) for x in coordinates]


def test_regression_recovers_a_known_velocity_coefficient() -> None:
    points = trajectory_for(coefficient=0.97, head_m=0.6, coordinates=(0.1, 0.2, 0.3, 0.4))
    assert coefficient_of_velocity_from_trajectory(points, 0.6) == pytest.approx(0.97, rel=1e-9)


def test_regression_agrees_with_the_single_point_formula() -> None:
    """Two coincident points reduce the least-squares fit to the single-point value."""
    point = TrajectoryPoint.from_centimetres(47.5, 10.0)
    assert coefficient_of_velocity_from_trajectory([point, point], 0.6) == pytest.approx(
        coefficient_of_velocity(0.475, 0.1, 0.6)
    )


def test_regression_is_robust_to_one_bad_point() -> None:
    """Averaging several points is the point of the method."""
    points = trajectory_for(coefficient=0.97, head_m=0.6, coordinates=(0.1, 0.2, 0.3, 0.4))
    exact = coefficient_of_velocity_from_trajectory(points, 0.6)
    points[1] = TrajectoryPoint(points[1].horizontal_m, points[1].vertical_m * 1.5)
    perturbed = coefficient_of_velocity_from_trajectory(points, 0.6)
    assert perturbed != pytest.approx(exact)
    assert abs(perturbed - 0.97) < 0.05


def test_from_centimetres_converts_to_metres() -> None:
    point = TrajectoryPoint.from_centimetres(47.5, 10.0)
    assert point.horizontal_m == 0.475
    assert point.vertical_m == 0.1


def test_regression_requires_at_least_two_points() -> None:
    with pytest.raises(ValueError, match="at least two trajectory points"):
        coefficient_of_velocity_from_trajectory([TrajectoryPoint(0.1, 0.01)], 0.6)


def test_regression_rejects_a_zero_slope() -> None:
    with pytest.raises(ValueError, match="non-positive slope"):
        coefficient_of_velocity_from_trajectory(
            [TrajectoryPoint(0.1, -0.01), TrajectoryPoint(0.2, -0.02)], 0.6
        )


def test_regression_rejects_all_zero_horizontal_coordinates() -> None:
    with pytest.raises(ValueError, match="every trajectory point has x = 0"):
        coefficient_of_velocity_from_trajectory(
            [TrajectoryPoint(0.0, 0.01), TrajectoryPoint(0.0, 0.02)], 0.6
        )


def test_regression_rejects_a_non_positive_head() -> None:
    points = trajectory_for(coefficient=0.97, head_m=0.6, coordinates=(0.1, 0.2))
    with pytest.raises(ValueError, match="head over orifice"):
        coefficient_of_velocity_from_trajectory(points, 0.0)


# --------------------------------------------------------------------------- #
# Device-specific expectations
# --------------------------------------------------------------------------- #


def test_consistent_run_gives_textbook_coefficients_for_an_orifice() -> None:
    """C_d ~ 0.62, C_v ~ 0.97, C_c ~ 0.64 and no warnings at all."""
    result = evaluate(CONSISTENT_READINGS)
    assert result.coefficient_of_discharge == pytest.approx(0.6200647014001986)
    assert result.coefficient_of_velocity == pytest.approx(0.9695896898516747)
    assert result.coefficient_of_contraction == pytest.approx(0.6395124740807161)
    assert result.is_consistent
    assert result.warnings() == ()
    assert result.device is OrificeDevice.ORIFICE


def test_physically_impossible_run_is_flagged() -> None:
    """A coefficient above 1.0 must be surfaced, not silently reported."""
    result = evaluate(GOLDEN_READINGS)
    assert not result.is_consistent
    assert "exceed 1.0" in result.warnings()[0]
    assert "! one or more coefficients exceed 1.0" in format_report(result)


def test_discharge_coefficient_outside_the_indicative_range_is_flagged() -> None:
    """0.62 is a delight for an orifice but far too low for a mouthpiece."""
    mouthpiece = OrificeMouthpieceReadings(
        time_for_50mm_rise_s=18.12,
        head_over_orifice_mm=600.0,
        horizontal_distance_cm=47.5,
        vertical_distance_cm=10.0,
        device=OrificeDevice.MOUTHPIECE,
    )
    result = evaluate(mouthpiece)
    low, high = DEVICE_CHARACTERISTICS[OrificeDevice.MOUTHPIECE].typical_discharge_coefficient
    assert not low <= result.coefficient_of_discharge <= high
    assert any("outside the indicative range" in note for note in result.warnings())


def test_mouthpiece_contraction_should_be_about_one() -> None:
    """The mouthpiece jet fills the outlet, so C_c must not sit near 0.64."""
    mouthpiece = OrificeMouthpieceReadings(
        time_for_50mm_rise_s=18.12,
        head_over_orifice_mm=600.0,
        horizontal_distance_cm=47.5,
        vertical_distance_cm=10.0,
        device=OrificeDevice.MOUTHPIECE,
    )
    assert any("fills the outlet" in note for note in evaluate(mouthpiece).warnings())


def test_device_defaults_to_an_orifice() -> None:
    assert OrificeMouthpieceReadings(15.0, 180.0, 25.0, 5.0).device is OrificeDevice.ORIFICE


def test_report_title_names_the_device() -> None:
    assert "sharp-edged orifice" in format_report(evaluate(CONSISTENT_READINGS))


def test_contraction_is_the_ratio_of_discharge_to_velocity_coefficient() -> None:
    """C_d = C_c * C_v is an identity, never an independent measurement."""
    result = evaluate(CONSISTENT_READINGS)
    assert result.coefficient_of_contraction == pytest.approx(
        result.coefficient_of_discharge / result.coefficient_of_velocity
    )


def test_report_can_show_standard_uncertainties() -> None:
    readings = CONSISTENT_READINGS
    budget = propagate(evaluate, readings, DEFAULT_UNCERTAINTIES)
    report = format_report(evaluate(readings), budget)
    assert "+/-" in report


def test_default_uncertainties_cover_every_numeric_reading() -> None:
    assert set(DEFAULT_UNCERTAINTIES) == {
        "time_for_50mm_rise_s",
        "head_over_orifice_mm",
        "horizontal_distance_cm",
        "vertical_distance_cm",
    }


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("time_s", [0.0, -3.0, float("nan")])
def test_rejects_unusable_rise_time(time_s: float) -> None:
    with pytest.raises(ValueError, match="time for 50 mm rise"):
        actual_discharge(time_s)


@pytest.mark.parametrize("head_m", [0.0, -0.18, float("nan")])
def test_rejects_unusable_head(head_m: float) -> None:
    with pytest.raises(ValueError, match="head over orifice"):
        theoretical_discharge(head_m)


@pytest.mark.parametrize("vertical_m", [0.0, -0.05])
def test_rejects_unusable_trajectory_coordinate(vertical_m: float) -> None:
    with pytest.raises(ValueError, match="vertical distance"):
        coefficient_of_velocity(0.25, vertical_m, 0.18)
