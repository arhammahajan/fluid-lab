"""Tests for CSV series input and CSV result export."""

import csv
import io
from dataclasses import dataclass

import pytest
from fluid_lab.centrifugal_pump import CentrifugalPumpReadings, evaluate
from fluid_lab.export import read_pairs, read_series, result_rows, write_results_csv


@dataclass(frozen=True, slots=True)
class OneReading:
    """Minimal readings dataclass for the reader tests."""

    x: float


@dataclass(frozen=True, slots=True)
class OneResult:
    """Minimal results dataclass for the writer tests."""

    y: float


def test_read_series_yields_one_instance_per_row() -> None:
    source = io.StringIO("a,b\n1,2\n3,4\n")
    runs = list(read_series(source, lambda a, b: (a, b), ("a", "b")))
    assert runs == [(1.0, 2.0), (3.0, 4.0)]


def test_read_series_rejects_a_missing_column() -> None:
    source = io.StringIO("a\n1\n")
    with pytest.raises(ValueError, match="missing column\\(s\\): b"):
        list(read_series(source, lambda a, b: (a, b), ("a", "b")))


def test_read_series_rejects_a_missing_header() -> None:
    with pytest.raises(ValueError, match="no header row"):
        list(read_series(io.StringIO(""), lambda x: (x,), ("x",)))


def test_read_series_reports_the_offending_line_and_column() -> None:
    source = io.StringIO("x\n1\nnope\n")
    with pytest.raises(ValueError, match="line 3: x='nope' is not a number"):
        list(read_series(source, OneReading, ("x",)))


def test_read_series_ignores_extra_columns() -> None:
    source = io.StringIO("x,note\n1.5,ignored\n")
    assert list(read_series(source, OneReading, ("x",))) == [OneReading(1.5)]


def test_read_pairs_returns_float_tuples() -> None:
    source = io.StringIO("x_cm,y_cm\n10,1\n20,4\n")
    assert list(read_pairs(source, "x_cm", "y_cm")) == [(10.0, 1.0), (20.0, 4.0)]


def test_read_pairs_rejects_a_missing_column() -> None:
    with pytest.raises(ValueError, match="missing column\\(s\\): y_cm"):
        list(read_pairs(io.StringIO("x_cm\n1\n"), "x_cm", "y_cm"))


def test_write_results_csv_round_trips() -> None:
    destination = io.StringIO()
    write_results_csv([OneResult(1.5), OneResult(2.5)], destination)
    rows = list(csv.DictReader(io.StringIO(destination.getvalue())))
    assert rows == [{"y": "1.5"}, {"y": "2.5"}]


def test_write_results_csv_appends_uncertainty_columns() -> None:
    destination = io.StringIO()
    write_results_csv([OneResult(1.5)], destination, [{"u_y": 0.05}])
    rows = list(csv.DictReader(io.StringIO(destination.getvalue())))
    assert rows == [{"y": "1.5", "u_y": "0.05"}]


def test_write_results_csv_with_no_rows_writes_nothing() -> None:
    destination = io.StringIO()
    write_results_csv([], destination)
    assert destination.getvalue() == ""


def test_result_rows_returns_the_field_names() -> None:
    fieldnames, rows = result_rows([OneResult(1.5)])
    assert fieldnames == ["y"]
    assert rows == [{"y": 1.5}]


PUMP_COLUMNS = (
    "time_for_100mm_rise_s",
    "discharge_pressure_kgf_cm2",
    "suction_vacuum_mm_hg",
    "time_for_10_pulses_s",
)


def test_a_pump_series_evaluates_end_to_end() -> None:
    """A two-run series produces two results, which a characteristic curve needs."""
    source = io.StringIO(
        "time_for_100mm_rise_s,discharge_pressure_kgf_cm2,suction_vacuum_mm_hg,time_for_10_pulses_s\n"
        "12.5,0.5,120,20\n"
        "10.0,0.4,100,22\n"
    )
    runs = list(read_series(source, CentrifugalPumpReadings, PUMP_COLUMNS))
    results = [evaluate(run) for run in runs]
    assert len(results) == 2
    assert results[0].actual_discharge_m3_s < results[1].actual_discharge_m3_s

    destination = io.StringIO()
    write_results_csv(results, destination)
    rows = list(csv.DictReader(io.StringIO(destination.getvalue())))
    assert len(rows) == 2
    assert float(rows[0]["efficiency_percent"]) == pytest.approx(27.549061119999998)
