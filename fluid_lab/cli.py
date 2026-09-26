"""Command-line front end for the fluid-mechanics experiment calculators.

Two input modes are supported for every experiment:

* interactive -- run the sub-command with no flags and it prompts for each
  reading, exactly like the original scripts;
* scripted -- pass the readings as flags, which makes the results reproducible
  and easy to paste into a logbook or a spreadsheet.

A whole series of runs can be read from a CSV whose columns are the reading
names, which is what turns a set of runs into a characteristic curve.

Examples:
    ``fluid-lab centrifugal-pump``
    ``fluid-lab centrifugal-pump --t-rise 12.5 --p-discharge 0.5 --vacuum 120 --t-pulses 20``
    ``fluid-lab centrifugal-pump --series runs.csv --csv results.csv``
    ``fluid-lab orifice-mouthpiece --t-rise 18.12 --head 600 --x 47.5 --y 10 --json``
"""

import argparse
import json
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from fluid_lab import centrifugal_pump, francis_turbine, orifice_mouthpiece
from fluid_lab.export import read_pairs, read_series, write_results_csv
from fluid_lab.orifice_mouthpiece import OrificeDevice, TrajectoryPoint
from fluid_lab.report import Quantity
from fluid_lab.report import format_report as format_table
from fluid_lab.uncertainty import UncertaintyBudget, propagate
from fluid_lab.units import mm_to_m

EXIT_OK: Final[int] = 0
EXIT_USAGE: Final[int] = 2
STDOUT_PATH: Final[str] = "-"
TRAJECTORY_COLUMNS: Final[tuple[str, str]] = ("x_cm", "y_cm")
"""Header names expected in a ``--trajectory-file``, matching the rig reading units."""


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Description of one input of an experiment.

    Attributes:
        name: Keyword name of the attribute on the readings dataclass.
        flag: Command-line flag that supplies the value.
        prompt: Prompt shown in interactive mode.
        help: One-line explanation, used both in ``--help`` and interactively.
        parser: Converts a raw command-line string to the field's own type.
        default: Value used when the flag is omitted.  ``None`` means "prompt
            interactively", so every field that has a default never prompts.
        choices: Allowed values for a non-numeric field; empty for a number.
    """

    name: str
    flag: str
    prompt: str
    help: str
    parser: Callable[[str], object] = float
    default: object | None = None
    choices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Experiment[ReadingsT, ResultsT]:
    """Everything the CLI needs in order to run one experiment."""

    key: str
    title: str
    summary: str
    readings_factory: Callable[..., ReadingsT]
    fields: tuple[FieldSpec, ...]
    evaluate: Callable[[ReadingsT], ResultsT]
    format_report: Callable[..., str]
    uncertainties: Mapping[str, float]
    trajectory: bool = False

    @property
    def field_names(self) -> tuple[str, ...]:
        """Return the reading names in constructor order."""
        return tuple(field.name for field in self.fields)

    def build_readings(self, arguments: argparse.Namespace) -> ReadingsT:
        """Build the readings dataclass from the parsed arguments.

        Any flag that was not supplied and has no default is prompted for, so a
        partial command line (for example only the flow-rate readings) still
        works interactively.

        Args:
            arguments: Namespace produced by :func:`_build_parser`.

        Returns:
            A populated readings instance.
        """
        values: dict[str, object] = {}
        for field in self.fields:
            raw = getattr(arguments, field.name, None)
            if raw is None:
                raw = (
                    field.default
                    if field.default is not None
                    else _prompt(field.prompt, field.parser)
                )
            values[field.name] = field.parser(raw) if isinstance(raw, str) else raw
        return self.readings_factory(**values)


EXPERIMENTS: Final[dict[str, Experiment[Any, Any]]] = {
    "centrifugal-pump": Experiment(
        key="centrifugal-pump",
        title="Centrifugal pump test",
        summary="Pump discharge, head, brake/indicated power and efficiency",
        readings_factory=centrifugal_pump.CentrifugalPumpReadings,
        fields=(
            FieldSpec(
                "time_for_100mm_rise_s",
                "--t-rise",
                "Time required for 100 mm rise [s]",
                "time for a 100 mm rise in the measuring tank",
            ),
            FieldSpec(
                "discharge_pressure_kgf_cm2",
                "--p-discharge",
                "Discharge pressure gauge reading [kgf/cm^2]",
                "Bourdon gauge on the delivery side",
            ),
            FieldSpec(
                "suction_vacuum_mm_hg",
                "--vacuum",
                "Suction vacuum gauge reading [mm Hg]",
                "vacuum gauge on the suction side",
            ),
            FieldSpec(
                "time_for_10_pulses_s",
                "--t-pulses",
                "Time required for 10 pulses [s]",
                "time for 10 energy-meter disc pulses",
            ),
        ),
        evaluate=centrifugal_pump.evaluate,
        format_report=centrifugal_pump.format_report,
        uncertainties=centrifugal_pump.DEFAULT_UNCERTAINTIES,
    ),
    "francis-turbine": Experiment(
        key="francis-turbine",
        title="Francis turbine test",
        summary="Turbine head, discharge, torque, input/output power, efficiency",
        readings_factory=francis_turbine.FrancisTurbineReadings,
        fields=(
            FieldSpec(
                "discharge_pressure_kgf_cm2",
                "--p-discharge",
                "Value of P_d [kgf/cm^2]",
                "inlet pressure-gauge reading",
            ),
            FieldSpec(
                "suction_vacuum_mm_hg",
                "--p-suction",
                "Value of P_s [mm Hg]",
                "outlet vacuum-gauge reading",
            ),
            FieldSpec(
                "manometer_deflection_m",
                "--manometer",
                "Venturimeter manometer deflection R [m of mercury]",
                "mercury-manometer deflection, in metres of mercury",
            ),
            FieldSpec(
                "tight_side_mass_kg",
                "--w1",
                "W1 [kg]",
                "spring-balance reading on the tight side of the brake",
            ),
            FieldSpec(
                "slack_side_mass_kg",
                "--w2",
                "W2 [kg]",
                "spring-balance reading on the slack side of the brake",
            ),
            FieldSpec(
                "speed_rpm",
                "--rpm",
                "Turbine speed N [rev/min]",
                "tachometer reading",
            ),
            FieldSpec(
                "datum_difference_m",
                "--datum",
                "Datum difference z [m]",
                "vertical distance between the two gauge centre-lines",
                default=0.0,
            ),
        ),
        evaluate=francis_turbine.evaluate,
        format_report=francis_turbine.format_report,
        uncertainties=francis_turbine.DEFAULT_UNCERTAINTIES,
    ),
    "orifice-mouthpiece": Experiment(
        key="orifice-mouthpiece",
        title="Orifice / mouthpiece test",
        summary="Discharge coefficients C_d, C_v and C_c",
        readings_factory=orifice_mouthpiece.OrificeMouthpieceReadings,
        fields=(
            FieldSpec(
                "device",
                "--device",
                "Device under test [orifice/mouthpiece]",
                "fitting under test; sets the indicative coefficient ranges",
                parser=OrificeDevice,
                default=OrificeDevice.ORIFICE,
                choices=tuple(device.value for device in OrificeDevice),
            ),
            FieldSpec(
                "time_for_50mm_rise_s",
                "--t-rise",
                "Time for 50 mm rise [s]",
                "time to collect the tank volume in the collecting tank",
            ),
            FieldSpec(
                "head_over_orifice_mm",
                "--head",
                "Head over orifice [mm]",
                "constant head over the device centre",
            ),
            FieldSpec(
                "horizontal_distance_cm",
                "--x",
                "Horizontal distance [cm]",
                "coord_x of a point on the jet trajectory",
            ),
            FieldSpec(
                "vertical_distance_cm",
                "--y",
                "Vertical distance [cm]",
                "coord_y of the same point on the jet trajectory",
            ),
        ),
        evaluate=orifice_mouthpiece.evaluate,
        format_report=orifice_mouthpiece.format_report,
        uncertainties=orifice_mouthpiece.DEFAULT_UNCERTAINTIES,
        trajectory=True,
    ),
}


def _prompt(prompt: str, parser: Callable[[str], object]) -> object:
    """Prompt until the input parses.

    Args:
        prompt: Prompt text, printed without a trailing colon.
        parser: Conversion applied to the entered text.

    Returns:
        The parsed value.

    Raises:
        SystemExit: If standard input is closed or the user interrupts.
    """
    while True:
        try:
            return parser(input(f"{prompt}: ").strip())
        except ValueError:
            print("  please enter a valid value", file=sys.stderr)
        except (EOFError, KeyboardInterrupt):
            print("\naborted", file=sys.stderr)
            raise SystemExit(EXIT_USAGE) from None


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser, deriving one sub-command per experiment.

    The shared flags are registered on both the top-level parser and every
    sub-command with ``default=argparse.SUPPRESS``, so they are accepted on either
    side of the experiment name without the sub-parser's default clobbering them.
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print the results as JSON instead of a formatted table",
    )
    common.add_argument(
        "--csv",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="write the results as CSV to PATH ('-' for standard output)",
    )
    common.add_argument(
        "--series",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="read a series of runs from a CSV whose columns are the reading names",
    )
    common.add_argument(
        "--uncertainty",
        action="store_true",
        default=argparse.SUPPRESS,
        help="also report the propagated standard uncertainty of each result",
    )

    parser = argparse.ArgumentParser(
        prog="fluid-lab",
        description="Compute fluid-mechanics laboratory experiment results.",
        epilog="Run a sub-command with no flags to be prompted for each reading.",
        parents=[common],
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the available experiments and exit",
    )
    subparsers = parser.add_subparsers(dest="experiment", metavar="EXPERIMENT")

    for experiment in EXPERIMENTS.values():
        subparser = subparsers.add_parser(
            experiment.key,
            help=experiment.summary,
            description=f"{experiment.title}. {experiment.summary}.",
            parents=[common],
        )
        for field in experiment.fields:
            help_text = field.help
            if field.default is None:
                help_text = f"{help_text} (prompted for if omitted)"
            subparser.add_argument(
                field.flag,
                dest=field.name,
                default=field.default,
                metavar="VALUE",
                choices=field.choices or None,
                help=help_text,
            )
        if experiment.trajectory:
            subparser.add_argument(
                "--trajectory-file",
                metavar="PATH",
                default=argparse.SUPPRESS,
                help=(
                    "CSV of jet-trajectory points (columns "
                    f"{', '.join(TRAJECTORY_COLUMNS)}) for a least-squares C_v"
                ),
            )
    return parser


def _print_experiment_list(stream: Any = None) -> None:
    """Print the available experiments and their one-line summaries."""
    width = max(len(key) for key in EXPERIMENTS)
    print("Available experiments:", file=stream)
    for key, experiment in EXPERIMENTS.items():
        print(f"  {key:<{width}}  {experiment.summary}", file=stream)


def _readings_series(
    experiment: Experiment[Any, Any],
    arguments: argparse.Namespace,
) -> Iterator[Any]:
    """Yield one readings instance per run, from flags or from ``--series``."""
    series = getattr(arguments, "series", None)
    if series is None:
        yield experiment.build_readings(arguments)
        return
    with Path(series).open(newline="", encoding="utf-8") as stream:
        yield from read_series(stream, experiment.readings_factory, experiment.field_names)


def _trajectory_regression(
    experiment: Experiment[Any, Any],
    arguments: argparse.Namespace,
) -> tuple[int, float] | None:
    """Return ``(point count, C_v)`` for ``--trajectory-file``, or ``None``."""
    path = getattr(arguments, "trajectory_file", None)
    if path is None:
        return None
    if getattr(arguments, "series", None) is not None:
        raise ValueError("--trajectory-file applies to a single run; drop --series")
    head_mm = getattr(arguments, "head_over_orifice_mm", None)
    if head_mm is None:
        raise ValueError("--trajectory-file also needs --head so the head is known")
    with Path(path).open(newline="", encoding="utf-8") as stream:
        points = [
            TrajectoryPoint.from_centimetres(horizontal_cm, vertical_cm)
            for horizontal_cm, vertical_cm in read_pairs(stream, *TRAJECTORY_COLUMNS)
        ]
    coefficient = orifice_mouthpiece.coefficient_of_velocity_from_trajectory(
        points, mm_to_m(float(head_mm))
    )
    return len(points), coefficient


def _format_trajectory_note(point_count: int, coefficient: float) -> str:
    """Render the multi-point ``C_v`` regression as a small table."""
    return format_table(
        "Trajectory regression",
        [
            Quantity(
                "coefficient_of_velocity",
                "C_v",
                f"least-squares fit over {point_count} points",
                coefficient,
                "-",
            )
        ],
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]``.

    Returns:
        A process exit code: 0 on success, 2 on a usage or input error.
    """
    parser = _build_parser()
    arguments = parser.parse_args(argv)

    if arguments.list:
        _print_experiment_list()
        return EXIT_OK

    if arguments.experiment is None:
        parser.print_usage(sys.stderr)
        print(
            f"error: choose an experiment ({', '.join(EXPERIMENTS)}) or use --list",
            file=sys.stderr,
        )
        return EXIT_USAGE

    experiment = EXPERIMENTS[arguments.experiment]
    want_uncertainty = getattr(arguments, "uncertainty", False)

    try:
        regression = _trajectory_regression(experiment, arguments)
        readings_list = list(_readings_series(experiment, arguments))
        results = [experiment.evaluate(readings) for readings in readings_list]
        budgets: list[UncertaintyBudget] | None = (
            [
                propagate(experiment.evaluate, readings, experiment.uncertainties)
                for readings in readings_list
            ]
            if want_uncertainty
            else None
        )
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE

    csv_path = getattr(arguments, "csv", None)
    if csv_path is not None:
        _write_csv(results, budgets, csv_path)
    elif getattr(arguments, "json", False):
        _write_json(results, regression)
    else:
        _write_reports(experiment, results, budgets)
        if regression is not None:
            print()
            print(_format_trajectory_note(*regression))
    return EXIT_OK


def _write_csv(
    results: list[Any],
    budgets: list[UncertaintyBudget] | None,
    destination: str,
) -> None:
    """Write the results as CSV to a path, or to standard output for ``-``."""
    uncertainty_rows = None if budgets is None else [budget.as_columns() for budget in budgets]
    if destination == STDOUT_PATH:
        write_results_csv(results, sys.stdout, uncertainty_rows)
        return
    with Path(destination).open("w", newline="", encoding="utf-8") as stream:
        write_results_csv(results, stream, uncertainty_rows)


def _write_json(results: list[Any], regression: tuple[int, float] | None) -> None:
    """Print the results as JSON, collapsing a single run to a bare object."""
    payload: list[dict[str, Any]] = [asdict(result) for result in results]
    document: Any = payload[0] if len(payload) == 1 else payload
    if regression is not None and isinstance(document, dict):
        note = {"point_count": regression[0], "coefficient_of_velocity": regression[1]}
        document = {**document, "trajectory_regression": note}
    print(json.dumps(document, indent=2))


def _write_reports(
    experiment: Experiment[Any, Any],
    results: list[Any],
    budgets: list[UncertaintyBudget] | None,
) -> None:
    """Print one formatted table per run, with uncertainties when requested."""
    for index, result in enumerate(results):
        if index:
            print()
        budget = None if budgets is None else budgets[index]
        print(experiment.format_report(result, budget))
