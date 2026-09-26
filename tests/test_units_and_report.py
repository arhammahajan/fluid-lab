"""Tests for the shared unit conversions and the report renderer."""

import pytest
from fluid_lab.constants import KGF_CM2_TO_M_OF_WATER
from fluid_lab.report import Quantity, attach_uncertainties, format_report
from fluid_lab.units import cm_to_m, gauge_pressure_to_head_m, mm_to_m, vacuum_to_head_m


def test_gauge_pressure_conversion_matches_the_definition() -> None:
    assert gauge_pressure_to_head_m(1.0) == KGF_CM2_TO_M_OF_WATER
    assert gauge_pressure_to_head_m(0.5) == 5.0
    assert gauge_pressure_to_head_m(0.0) == 0.0


def test_vacuum_conversion_uses_the_mercury_relative_density() -> None:
    assert vacuum_to_head_m(1000.0) == 13.6
    assert vacuum_to_head_m(120.0) == pytest.approx(1.632)


def test_metric_conversions() -> None:
    assert cm_to_m(25.0) == 0.25
    assert mm_to_m(180.0) == 0.18


def test_quantity_label_pads_the_symbol_column() -> None:
    assert Quantity("total_head_m", "H", "total head", 7.052, "m").label == "H     total head"


def test_quantity_renders_without_an_uncertainty_by_default() -> None:
    assert "7.052 m" in Quantity("total_head_m", "H", "total head", 7.052, "m").render(24)
    assert "+/-" not in Quantity("total_head_m", "H", "total head", 7.052, "m").render(24)


@pytest.mark.parametrize(
    ("uncertainty", "expected"),
    [
        (0.5, "7.05 +/- 0.50"),
        (3.2, "78.6 +/- 3.2"),
        (0.01126745, "0.155 +/- 0.011"),
        (0.005625, "0.5625 +/- 0.0056"),
        (4e-5, "0.002240 +/- 0.000040"),
    ],
)
def test_uncertainty_sets_the_displayed_precision(uncertainty: float, expected: str) -> None:
    """The uncertainty is shown to two significant digits and the value matched to it."""
    value = {
        "7.05 +/- 0.50": 7.052,
        "78.6 +/- 3.2": 78.631,
        "0.155 +/- 0.011": 0.15496,
        "0.5625 +/- 0.0056": 0.5625,
        "0.002240 +/- 0.000040": 0.00224,
    }[expected]
    rendered = Quantity("f", "X", "x", value, "-", uncertainty=uncertainty).render(10)
    assert expected in rendered


def test_zero_uncertainty_falls_back_to_plain_formatting() -> None:
    rendered = Quantity("f", "X", "x", 7.052, "m", uncertainty=0.0).render(10)
    assert "+/-" not in rendered
    assert "7.052" in rendered


def test_attach_uncertainties_matches_on_the_field_name() -> None:
    rows = (Quantity("total_head_m", "H", "total head", 7.052, "m"),)
    attached = attach_uncertainties(rows, {"total_head_m": 0.5, "other": 1.0})
    assert attached[0].uncertainty == 0.5


def test_attach_uncertainties_leaves_unmatched_rows_alone() -> None:
    rows = (Quantity("total_head_m", "H", "total head", 7.052, "m"),)
    attached = attach_uncertainties(rows, {"something_else": 0.5})
    assert attached[0].uncertainty is None


def test_format_report_aligns_columns_and_appends_notes() -> None:
    report = format_report(
        "Demo",
        [
            Quantity("total_head_m", "H", "total head", 7.052, "m"),
            Quantity("actual_discharge_m3_s", "Q_act", "actual discharge", 0.00224, "m^3/s"),
        ],
        notes=["check the tank area"],
    )
    lines = report.splitlines()
    assert lines[0] == "Demo"
    assert lines[1] == "===="
    assert lines[2].startswith("H     total head")
    assert lines[3].startswith("Q_act actual discharge")
    assert lines[-1] == "! check the tank area"


def test_format_report_handles_an_empty_result_set() -> None:
    assert format_report("Empty", ()) == "Empty\n====="
