"""CSV export and multi-run ("series") input.

A single experimental run is one row; a series of runs is a table.  Producing a
table is what turns a handful of readings into a characteristic curve, so both
directions are supported:

* :func:`read_series` -- CSV of readings -> readings dataclass instances;
* :func:`write_results_csv` -- results dataclass instances -> CSV of results.
"""

import csv
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import asdict
from typing import Any, TextIO


def read_series(
    source: TextIO,
    readings_factory: Callable[..., Any],
    field_names: Sequence[str],
) -> Iterator[Any]:
    """Yield readings instances parsed from a CSV of runs.

    Args:
        source: Open text stream containing a header row and one row per run.
        readings_factory: The experiment's readings dataclass.
        field_names: Columns that must be present, in constructor order.

    Yields:
        One readings instance per CSV row.

    Raises:
        ValueError: If the header is missing, a required column is absent, or a
            cell is not a number.  The message names the offending column.
    """
    reader = csv.DictReader(source)
    if reader.fieldnames is None:
        raise ValueError("series file has no header row")

    missing = [name for name in field_names if name not in reader.fieldnames]
    if missing:
        raise ValueError(
            f"series file is missing column(s): {', '.join(missing)}; "
            f"found: {', '.join(reader.fieldnames)}"
        )

    for line_number, row in enumerate(reader, start=2):
        values: dict[str, float] = {}
        for name in field_names:
            raw = row.get(name)
            try:
                values[name] = float(raw)  # type: ignore[arg-type]
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"series file line {line_number}: {name}={raw!r} is not a number"
                ) from error
        yield readings_factory(**values)


def read_pairs(source: TextIO, column_x: str, column_y: str) -> Iterator[tuple[float, float]]:
    """Yield ``(x, y)`` number pairs from a two-column CSV.

    Args:
        source: Open text stream containing a header row.
        column_x: Name of the first numeric column.
        column_y: Name of the second numeric column.

    Yields:
        One ``(float, float)`` tuple per row.

    Raises:
        ValueError: If the header is missing, a required column is absent, or a
            cell is not a number.
    """
    reader = csv.DictReader(source)
    if reader.fieldnames is None:
        raise ValueError("file has no header row")

    missing = [name for name in (column_x, column_y) if name not in reader.fieldnames]
    if missing:
        raise ValueError(
            f"file is missing column(s): {', '.join(missing)}; "
            f"found: {', '.join(reader.fieldnames)}"
        )

    for line_number, row in enumerate(reader, start=2):
        try:
            yield float(row[column_x]), float(row[column_y])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"file line {line_number}: expected two numbers, got {row!r}"
            ) from error


def result_rows(
    results: Iterable[Any],
    uncertainties: Iterable[dict[str, float]] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Convert results to a header plus a list of row mappings.

    Args:
        results: Results dataclass instances.
        uncertainties: Optional per-result ``{u_<field>: value}`` mappings, added
            as extra columns.  Must line up with ``results``.

    Returns:
        ``(fieldnames, rows)``; ``fieldnames`` is empty when there are no results.
    """
    rows = [asdict(result) for result in results]
    if uncertainties is not None:
        for row, extra in zip(rows, uncertainties, strict=True):
            row.update(extra)
    fieldnames = list(rows[0]) if rows else []
    return fieldnames, rows


def write_results_csv(
    results: Iterable[Any],
    destination: TextIO,
    uncertainties: Iterable[dict[str, float]] | None = None,
) -> None:
    """Write results as CSV, one row per run.

    Args:
        results: Results dataclass instances.
        destination: Open text stream to write to.
        uncertainties: Optional per-result ``{u_<field>: value}`` mappings.
    """
    fieldnames, rows = result_rows(results, uncertainties)
    if not fieldnames:
        return
    writer = csv.DictWriter(destination, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
