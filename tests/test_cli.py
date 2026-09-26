"""Tests for the command-line interface."""

import csv
import io
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest
from fluid_lab.cli import EXPERIMENTS, main

PUMP_ARGV = [
    "centrifugal-pump",
    "--t-rise",
    "12.5",
    "--p-discharge",
    "0.5",
    "--vacuum",
    "120",
    "--t-pulses",
    "20",
]

ORIFICE_ARGV = [
    "orifice-mouthpiece",
    "--t-rise",
    "15",
    "--head",
    "180",
    "--x",
    "25",
    "--y",
    "5",
]

PUMP_COLUMNS = (
    "time_for_100mm_rise_s",
    "discharge_pressure_kgf_cm2",
    "suction_vacuum_mm_hg",
    "time_for_10_pulses_s",
)


def write_csv_file(
    path: Path,
    header: tuple[str, ...],
    rows: Iterable[Sequence[object]],
) -> Path:
    """Write a small CSV fixture and return its path."""
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_list_names_every_experiment(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--list"]) == 0
    printed = capsys.readouterr().out
    for key in EXPERIMENTS:
        assert key in printed


def test_scripted_run_prints_the_report_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(PUMP_ARGV) == 0
    printed = capsys.readouterr().out
    assert "Centrifugal pump test" in printed
    assert "27.5491 %" in printed


def test_json_flag_produces_parsable_results(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([*PUMP_ARGV, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["actual_discharge_m3_s"] == 0.00224
    assert payload["brake_power_kw"] == pytest.approx(0.15496346879999998)
    assert payload["efficiency_percent"] == pytest.approx(27.549061119999998)


def test_json_flag_is_accepted_before_the_experiment_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The flag must not be clobbered by the sub-parser's default."""
    assert main(["--json", *PUMP_ARGV]) == 0
    assert "actual_discharge_m3_s" in json.loads(capsys.readouterr().out)


def test_inconsistent_orifice_run_prints_a_warning(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(ORIFICE_ARGV) == 0
    assert "! one or more coefficients exceed 1.0" in capsys.readouterr().out


def test_missing_experiment_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "choose an experiment" in capsys.readouterr().err


def test_unusable_reading_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["orifice-mouthpiece", "--t-rise", "0", "--head", "180", "--x", "25", "--y", "5"]
    assert main(argv) == 2
    assert "time for 50 mm rise" in capsys.readouterr().err


def test_unparsable_reading_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["centrifugal-pump", "--t-rise", "soon", "--p-discharge", "0.5"]
    assert main(argv) == 2
    assert "could not convert" in capsys.readouterr().err


def test_missing_readings_are_prompted_for(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses = iter(["12.5", "0.5", "120", "20"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    assert main(["centrifugal-pump"]) == 0
    assert "27.5491 %" in capsys.readouterr().out


def test_invalid_prompt_input_is_rejected_and_retried(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses = iter(["not-a-number", "12.5", "0.5", "120", "20"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    assert main(["centrifugal-pump"]) == 0
    assert "please enter a valid value" in capsys.readouterr().err


def test_partial_command_line_prompts_only_for_the_gaps(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return {"Suction": "120", "Time required for 10": "20"}.get(prompt.split(":")[0], "0.5")

    monkeypatch.setattr("builtins.input", fake_input)
    argv = ["centrifugal-pump", "--t-rise", "12.5", "--p-discharge", "0.5"]
    assert main(argv) == 0
    assert len(prompts) == 2
    assert capsys.readouterr().out


def test_fields_with_defaults_are_never_prompted_for(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--datum`` and ``--device`` have defaults and must not block a run."""
    table = ["5", "1.5", "900", "0.4", "100", "0.35"]

    def fake_input(prompt: str = "") -> str:
        return table.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)
    assert main(["francis-turbine"]) == 0
    assert table == []
    assert "total head" in capsys.readouterr().out


def test_negative_readings_are_still_checkable(capsys: pytest.CaptureFixture[str]) -> None:
    """``--t-rise=-1`` must reach validation rather than being parsed as a flag."""
    argv = [
        "centrifugal-pump",
        "--t-rise=-1",
        "--p-discharge",
        "0.5",
        "--vacuum",
        "120",
        "--t-pulses",
        "20",
    ]
    assert main(argv) == 2
    assert "time for 100 mm rise" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Uncertainty
# --------------------------------------------------------------------------- #


def test_uncertainty_flag_adds_standard_uncertainties(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([*PUMP_ARGV, "--uncertainty"]) == 0
    assert "27.5 +/- 2.0 %" in capsys.readouterr().out


def test_uncertainty_flag_is_accepted_before_the_experiment_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--uncertainty", *PUMP_ARGV]) == 0
    assert "+/-" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CSV export and series input
# --------------------------------------------------------------------------- #


def test_csv_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([*PUMP_ARGV, "--csv", "-"]) == 0
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert len(rows) == 1
    assert float(rows[0]["efficiency_percent"]) == pytest.approx(27.549061119999998)


def test_csv_to_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    destination = tmp_path / "results.csv"
    assert main([*PUMP_ARGV, "--csv", str(destination)]) == 0
    assert capsys.readouterr().out == ""
    with destination.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert float(rows[0]["total_head_m"]) == pytest.approx(7.052)


def test_csv_includes_uncertainty_columns_only_when_requested(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([*PUMP_ARGV, "--csv", "-", "--uncertainty"]) == 0
    header = capsys.readouterr().out.splitlines()[0]
    assert "u_efficiency_percent" in header

    assert main([*PUMP_ARGV, "--csv", "-"]) == 0
    assert "u_efficiency_percent" not in capsys.readouterr().out.splitlines()[0]


def test_series_reads_many_runs_from_a_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    series = write_csv_file(
        tmp_path / "runs.csv",
        PUMP_COLUMNS,
        [(12.5, 0.5, 120, 20), (10.0, 0.4, 100, 22)],
    )
    assert main([*PUMP_ARGV[0:1], "--series", str(series), "--csv", "-"]) == 0
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert len(rows) == 2
    assert float(rows[0]["actual_discharge_m3_s"]) == pytest.approx(0.00224)
    assert float(rows[1]["actual_discharge_m3_s"]) == pytest.approx(0.0028)


def test_series_prints_one_table_per_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    series = write_csv_file(
        tmp_path / "runs.csv",
        PUMP_COLUMNS,
        [(12.5, 0.5, 120, 20), (10.0, 0.4, 100, 22)],
    )
    assert main([*PUMP_ARGV[0:1], "--series", str(series)]) == 0
    assert capsys.readouterr().out.count("Centrifugal pump test") == 2


def test_series_with_a_missing_column_is_a_usage_error(tmp_path: Path) -> None:
    series = write_csv_file(tmp_path / "bad.csv", ("time_for_100mm_rise_s",), [(12.5,)])
    assert main([*PUMP_ARGV[0:1], "--series", str(series)]) == 2


def test_series_with_a_bad_cell_is_a_usage_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    series = write_csv_file(tmp_path / "bad.csv", PUMP_COLUMNS, [("soon", 0.5, 120, 20)])
    assert main([*PUMP_ARGV[0:1], "--series", str(series)]) == 2
    assert "is not a number" in capsys.readouterr().err


def test_missing_series_file_is_a_usage_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    absent = tmp_path / "nope.csv"
    assert main([*PUMP_ARGV[0:1], "--series", str(absent)]) == 2
    assert "error" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Experiment-specific flags
# --------------------------------------------------------------------------- #


def test_datum_flag_is_added_to_the_turbine_head(capsys: pytest.CaptureFixture[str]) -> None:
    base = [
        "francis-turbine",
        "--p-discharge",
        "0.4",
        "--p-suction",
        "100",
        "--manometer",
        "0.35",
        "--w1",
        "5",
        "--w2",
        "1.5",
        "--rpm",
        "900",
    ]
    assert main([*base, "--json"]) == 0
    without = json.loads(capsys.readouterr().out)["total_head_m"]

    assert main([*base, "--datum", "0.5", "--json"]) == 0
    with_datum = json.loads(capsys.readouterr().out)["total_head_m"]

    assert with_datum == pytest.approx(without + 0.5)
    assert without == pytest.approx(5.36)


def test_device_flag_changes_the_report_and_the_checks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    consistent = [
        "orifice-mouthpiece",
        "--t-rise",
        "18.12",
        "--head",
        "600",
        "--x",
        "47.5",
        "--y",
        "10",
    ]
    assert main([*consistent, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["device"] == "orifice"

    assert main([*consistent, "--device", "mouthpiece"]) == 0
    printed = capsys.readouterr().out
    assert "external cylindrical mouthpiece" in printed
    assert "! C_d" in printed
    assert "fills the outlet" in printed


def test_an_unknown_device_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["orifice-mouthpiece", "--device", "nozzle"])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_trajectory_file_adds_a_least_squares_regression(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    coefficient, head_m = 0.97, 0.6
    slope = 1.0 / (4.0 * coefficient**2 * head_m)
    rows = [(x_cm, 100.0 * slope * (x_cm / 100.0) ** 2) for x_cm in (10.0, 20.0, 30.0, 40.0)]
    trajectory = write_csv_file(tmp_path / "trajectory.csv", ("x_cm", "y_cm"), rows)

    argv = [
        "orifice-mouthpiece",
        "--t-rise",
        "18.12",
        "--head",
        "600",
        "--x",
        "47.5",
        "--y",
        "10",
        "--trajectory-file",
        str(trajectory),
    ]
    assert main(argv) == 0
    printed = capsys.readouterr().out
    assert "Trajectory regression" in printed
    assert "least-squares fit over 4 points" in printed
    assert "0.97" in printed


def test_trajectory_regression_appears_in_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trajectory = write_csv_file(
        tmp_path / "trajectory.csv", ("x_cm", "y_cm"), [(10.0, 0.443), (20.0, 1.771)]
    )
    argv = [
        "orifice-mouthpiece",
        "--t-rise",
        "18.12",
        "--head",
        "600",
        "--x",
        "47.5",
        "--y",
        "10",
        "--trajectory-file",
        str(trajectory),
        "--json",
    ]
    assert main(argv) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["trajectory_regression"]["point_count"] == 2
    assert payload["trajectory_regression"]["coefficient_of_velocity"] > 0.0


def test_trajectory_file_needs_a_head(capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        "orifice-mouthpiece",
        "--t-rise",
        "18.12",
        "--x",
        "47.5",
        "--y",
        "10",
        "--trajectory-file",
        "whatever.csv",
    ]
    assert main(argv) == 2
    assert "needs --head" in capsys.readouterr().err


def test_trajectory_file_cannot_be_combined_with_a_series(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    series = write_csv_file(
        tmp_path / "runs.csv",
        (
            "time_for_50mm_rise_s",
            "head_over_orifice_mm",
            "horizontal_distance_cm",
            "vertical_distance_cm",
        ),
        [(18.12, 600, 47.5, 10)],
    )
    argv = ["orifice-mouthpiece", "--series", str(series), "--trajectory-file", str(series)]
    assert main(argv) == 2
    assert "drop --series" in capsys.readouterr().err
