"""Orifice and mouthpiece test-rig calculations.

Apparatus
---------
Water from a constant-head tank discharges through the orifice (or mouthpiece)
under test into a collecting tank, where the flow rate is measured from the rise
of level.  The jet is allowed to fall freely and its trajectory is used to obtain
the velocity at the vena contracta, so that the three coefficients can be
separated:

* ``C_d`` -- coefficient of discharge, from the measured and theoretical flow;
* ``C_v`` -- coefficient of velocity, from the jet trajectory;
* ``C_c`` -- coefficient of contraction, from ``C_d = C_c * C_v``.

Formulas
--------
=========================  ====================================================
Actual discharge           ``Q_act = A_tank * d_rise / t``
Theoretical discharge      ``Q_th = a * sqrt(2 g H)``
Coefficient of discharge   ``C_d = Q_act / Q_th``
Coefficient of velocity    ``C_v = x / sqrt(4 y H)``
Coefficient of contraction ``C_c = C_d / C_v``
=========================  ====================================================

where ``a`` is the device area, ``H`` the head over the device, and ``x``, ``y``
the horizontal and vertical coordinates of a point on the jet trajectory.
``C_v`` follows from the projectile relations ``x = v t`` and ``y = g t^2 / 2``
with ``v = C_v sqrt(2 g H)``.

Since that relation implies ``y = x^2 / (4 C_v^2 H)`` -- a straight line through
the origin when ``y`` is plotted against ``x^2`` -- several trajectory points can
be combined into a least-squares slope, which is far less sensitive to a single
misread coordinate than :func:`coefficient_of_velocity`.  Use
:func:`coefficient_of_velocity_from_trajectory` for that.
"""

from dataclasses import dataclass
from enum import StrEnum
from math import pi, sqrt
from typing import Final

from fluid_lab.constants import GRAVITY_MS2
from fluid_lab.report import Quantity, attach_uncertainties
from fluid_lab.report import format_report as format_table
from fluid_lab.uncertainty import UncertaintyBudget
from fluid_lab.units import cm_to_m, mm_to_m
from fluid_lab.validation import require_positive

# --------------------------------------------------------------------------- #
# Rig geometry
# --------------------------------------------------------------------------- #

COLLECTING_TANK_AREA_M2: Final[float] = 0.175
"""Plan area of the collecting tank [m^2].

**Inferred, not measured.**  The original script hard-coded a collected volume of
``0.00875 m^3`` per 50 mm rise, which corresponds to this area.  Measure the tank
and correct this constant if it disagrees.
"""

COLLECTING_TANK_RISE_M: Final[float] = 0.05
"""Level rise used for one discharge measurement [m] (50 mm)."""

COLLECTING_TANK_VOLUME_M3: Final[float] = COLLECTING_TANK_AREA_M2 * COLLECTING_TANK_RISE_M
"""Volume collected per measurement [m^3]."""

ORIFICE_DIAMETER_M: Final[float] = 0.017
"""Diameter of the sharp-edged orifice under test [m]."""

ORIFICE_AREA_M2: Final[float] = (pi / 4) * (ORIFICE_DIAMETER_M**2)
"""Area of the orifice ``a`` [m^2]."""

MOUTHPIECE_CONTRACTION_TOLERANCE: Final[float] = 0.10
"""How far ``C_c`` may sit from 1.0 for a mouthpiece before it is flagged."""

# --------------------------------------------------------------------------- #
# Assumed instrument uncertainties
# --------------------------------------------------------------------------- #

DEFAULT_UNCERTAINTIES: Final[dict[str, float]] = {
    "time_for_50mm_rise_s": 0.2,  # hand stopwatch
    "head_over_orifice_mm": 0.5,  # hook/piezometer gauge, half a division
    "horizontal_distance_cm": 0.05,  # metre rule on the trajectory, 0.5 mm
    "vertical_distance_cm": 0.05,
}
"""Assumed absolute standard uncertainties [same unit as the reading].

These are the instruments' least counts divided by two, which is the usual
laboratory convention.  Replace them with the values from your own instrument
data before quoting a final uncertainty budget.
"""


class OrificeDevice(StrEnum):
    """The fitting under test.

    The theoretical discharge uses the device's own area, so the formula is
    shared, but the *expected* coefficients differ: a sharp-edged orifice forms a
    contracted vena contracta well inside the plate, whereas the jet from an
    external mouthpiece fills the outlet, giving it a coefficient of contraction
    of about one.
    """

    ORIFICE = "orifice"
    MOUTHPIECE = "mouthpiece"


@dataclass(frozen=True, slots=True)
class DeviceCharacteristics:
    """Indicative behaviour of a :class:`OrificeDevice`."""

    description: str
    """Human-readable name of the fitting."""

    typical_discharge_coefficient: tuple[float, float]
    """Indicative ``C_d`` range from standard texts [-]; not a tolerance."""

    contraction_is_unity: bool
    """Whether the jet is expected to fill the outlet, so ``C_c`` is about 1."""


DEVICE_CHARACTERISTICS: Final[dict[OrificeDevice, DeviceCharacteristics]] = {
    OrificeDevice.ORIFICE: DeviceCharacteristics(
        description="sharp-edged orifice",
        typical_discharge_coefficient=(0.60, 0.65),
        contraction_is_unity=False,
    ),
    OrificeDevice.MOUTHPIECE: DeviceCharacteristics(
        description="external cylindrical mouthpiece",
        typical_discharge_coefficient=(0.80, 0.86),
        contraction_is_unity=True,
    ),
}
"""Indicative characteristics for the guard checks below.

These ranges are order-of-magnitude guidance taken from standard fluid-mechanics
texts; a real rig may legitimately sit outside them.  Exceeding one produces a
note, never an error.
"""


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TrajectoryPoint:
    """One measured point on the free jet trajectory.

    Attributes:
        horizontal_m: Horizontal distance from the vena contracta ``x`` [m].
        vertical_m: Vertical drop from the vena contracta ``y`` [m].
    """

    horizontal_m: float
    vertical_m: float

    @classmethod
    def from_centimetres(cls, horizontal_cm: float, vertical_cm: float) -> "TrajectoryPoint":
        """Build a point from centimetre readings, as taken on the rig."""
        return cls(horizontal_m=cm_to_m(horizontal_cm), vertical_m=cm_to_m(vertical_cm))


@dataclass(frozen=True, slots=True)
class OrificeMouthpieceReadings:
    """Raw observations from one run of the orifice/mouthpiece experiment.

    Attributes:
        time_for_50mm_rise_s: Time to collect
            :data:`COLLECTING_TANK_VOLUME_M3` in the tank [s].
        head_over_orifice_mm: Constant head over the device centre [mm].
        horizontal_distance_cm: Horizontal coordinate ``x`` of a point on the
            jet trajectory, from the vena contracta [cm].
        vertical_distance_cm: Vertical coordinate ``y`` of the same point [cm].
        device: The fitting under test.
    """

    time_for_50mm_rise_s: float
    head_over_orifice_mm: float
    horizontal_distance_cm: float
    vertical_distance_cm: float
    device: OrificeDevice = OrificeDevice.ORIFICE


@dataclass(frozen=True, slots=True)
class OrificeMouthpiecePerformance:
    """Performance computed from :class:`OrificeMouthpieceReadings`."""

    actual_discharge_m3_s: float
    """Actual discharge ``Q_act`` [m^3/s]."""

    theoretical_discharge_m3_s: float
    """Theoretical discharge ``Q_th`` [m^3/s]."""

    head_over_orifice_m: float
    """Head over the device ``H`` [m]."""

    coefficient_of_discharge: float
    """``C_d = Q_act / Q_th`` [-]."""

    coefficient_of_velocity: float
    """``C_v`` from the jet trajectory [-]."""

    coefficient_of_contraction: float
    """``C_c = C_d / C_v`` [-].

    Computed rather than measured, so it carries the error of both ``C_d`` and
    ``C_v``.  It is a consistency check on the other two, not an independent
    measurement.
    """

    device: OrificeDevice = OrificeDevice.ORIFICE
    """The fitting these coefficients describe."""

    @property
    def is_consistent(self) -> bool:
        """Whether all three coefficients are physically possible (``<= 1``).

        A coefficient above one means the measured discharge (or jet velocity)
        exceeds the ideal value, which cannot happen for a real fitting.  It
        signals a reading error, a wrong ``H``, or a wrong tank area.
        """
        return (
            max(
                self.coefficient_of_discharge,
                self.coefficient_of_velocity,
                self.coefficient_of_contraction,
            )
            <= 1.0
        )

    def quantities(self) -> tuple[Quantity, ...]:
        """Return the results as displayable rows, in report order."""
        return (
            Quantity(
                "actual_discharge_m3_s",
                "Q_act",
                "actual discharge",
                self.actual_discharge_m3_s,
                "m^3/s",
            ),
            Quantity(
                "theoretical_discharge_m3_s",
                "Q_th",
                "theoretical discharge",
                self.theoretical_discharge_m3_s,
                "m^3/s",
            ),
            Quantity("head_over_orifice_m", "H", "head over device", self.head_over_orifice_m, "m"),
            Quantity(
                "coefficient_of_discharge",
                "C_d",
                "coefficient of discharge",
                self.coefficient_of_discharge,
                "-",
            ),
            Quantity(
                "coefficient_of_velocity",
                "C_v",
                "coefficient of velocity",
                self.coefficient_of_velocity,
                "-",
            ),
            Quantity(
                "coefficient_of_contraction",
                "C_c",
                "coefficient of contraction",
                self.coefficient_of_contraction,
                "-",
            ),
        )

    def warnings(self) -> tuple[str, ...]:
        """Return human-readable warnings for physically impossible results."""
        characteristics = DEVICE_CHARACTERISTICS[self.device]
        notes: list[str] = []

        if not self.is_consistent:
            notes.append(
                "one or more coefficients exceed 1.0, which is not physically "
                "possible: check the head, the tank area and the trajectory readings"
            )

        low, high = characteristics.typical_discharge_coefficient
        if not low <= self.coefficient_of_discharge <= high:
            notes.append(
                f"C_d = {self.coefficient_of_discharge:.3g} is outside the indicative "
                f"range {low}-{high} for the {characteristics.description}"
            )

        if (
            characteristics.contraction_is_unity
            and abs(self.coefficient_of_contraction - 1.0) > MOUTHPIECE_CONTRACTION_TOLERANCE
        ):
            notes.append(
                "the jet from a mouthpiece fills the outlet, so C_c should be about "
                f"1.0, but it is {self.coefficient_of_contraction:.3g}"
            )

        return tuple(notes)


# --------------------------------------------------------------------------- #
# Calculations
# --------------------------------------------------------------------------- #


def actual_discharge(time_for_rise_s: float) -> float:
    """Return the actual discharge [m^3/s] from the collecting-tank rise.

    Args:
        time_for_rise_s: Time for a :data:`COLLECTING_TANK_RISE_M` rise [s].

    Returns:
        Actual discharge ``Q_act`` [m^3/s].

    Raises:
        ValueError: If ``time_for_rise_s`` is not positive.
    """
    require_positive("time for 50 mm rise", time_for_rise_s)
    return COLLECTING_TANK_VOLUME_M3 / time_for_rise_s


def theoretical_discharge(head_over_orifice_m: float) -> float:
    """Return the theoretical (frictionless) discharge [m^3/s].

    Args:
        head_over_orifice_m: Constant head over the device centre [m].

    Returns:
        Theoretical discharge ``Q_th`` [m^3/s].

    Raises:
        ValueError: If ``head_over_orifice_m`` is not positive.
    """
    require_positive("head over orifice", head_over_orifice_m)
    return ORIFICE_AREA_M2 * sqrt(2 * GRAVITY_MS2 * head_over_orifice_m)


def coefficient_of_velocity(
    horizontal_distance_m: float,
    vertical_distance_m: float,
    head_over_orifice_m: float,
) -> float:
    """Return ``C_v`` from a single jet-trajectory point.

    Args:
        horizontal_distance_m: Horizontal coordinate ``x`` of the point [m].
        vertical_distance_m: Vertical coordinate ``y`` of the point [m].
        head_over_orifice_m: Head over the device centre [m].

    Returns:
        Coefficient of velocity ``C_v`` [-].

    Raises:
        ValueError: If ``y`` or ``H`` is not positive.
    """
    require_positive("vertical distance", vertical_distance_m)
    require_positive("head over orifice", head_over_orifice_m)
    return horizontal_distance_m / sqrt(4 * vertical_distance_m * head_over_orifice_m)


def coefficient_of_velocity_from_trajectory(
    points: "list[TrajectoryPoint] | tuple[TrajectoryPoint, ...]",
    head_over_orifice_m: float,
) -> float:
    """Return ``C_v`` from a least-squares fit of ``y = k x^2`` through the origin.

    Because ``y = x^2 / (4 C_v^2 H)``, the fitted slope is ``k = 1/(4 C_v^2 H)``
    and therefore ``C_v = 1 / (2 sqrt(k H))``.  Fitting several points averages
    out the coordinate reading errors instead of propagating one bad pair.

    Args:
        points: At least two trajectory points, all at the same head.
        head_over_orifice_m: Head over the device centre [m].

    Returns:
        Coefficient of velocity ``C_v`` [-].

    Raises:
        ValueError: If fewer than two points are given, if ``H`` is not positive,
            if every point has ``x = 0``, or if the points do not describe a
            downward-curving jet (fitted slope not positive).  Individual
            coordinates are not rejected: averaging out one bad pair is exactly
            what the fit is for.
    """
    require_positive("head over orifice", head_over_orifice_m)
    if len(points) < 2:
        raise ValueError(f"at least two trajectory points are required, got {len(points)}")

    denominator = sum(point.horizontal_m**4 for point in points)
    if denominator == 0.0:
        raise ValueError("every trajectory point has x = 0; the jet has no slope")

    slope = sum(point.vertical_m * point.horizontal_m**2 for point in points) / denominator
    if slope <= 0.0:
        raise ValueError("trajectory points give a non-positive slope; check the readings")
    return 1.0 / (2.0 * sqrt(slope * head_over_orifice_m))


def evaluate(readings: OrificeMouthpieceReadings) -> OrificeMouthpiecePerformance:
    """Run the full calculation chain for one set of readings.

    Args:
        readings: Raw observations from the experiment.

    Returns:
        Flow rates and the three coefficients.

    Raises:
        ValueError: If a reading makes a formula undefined (non-positive time,
            head or vertical distance).
    """
    head_over_orifice_m = mm_to_m(readings.head_over_orifice_mm)
    actual_discharge_m3_s = actual_discharge(readings.time_for_50mm_rise_s)
    theoretical_discharge_m3_s = theoretical_discharge(head_over_orifice_m)
    coefficient_of_discharge = actual_discharge_m3_s / theoretical_discharge_m3_s
    velocity_coefficient = coefficient_of_velocity(
        cm_to_m(readings.horizontal_distance_cm),
        cm_to_m(readings.vertical_distance_cm),
        head_over_orifice_m,
    )
    return OrificeMouthpiecePerformance(
        actual_discharge_m3_s=actual_discharge_m3_s,
        theoretical_discharge_m3_s=theoretical_discharge_m3_s,
        head_over_orifice_m=head_over_orifice_m,
        coefficient_of_discharge=coefficient_of_discharge,
        coefficient_of_velocity=velocity_coefficient,
        coefficient_of_contraction=coefficient_of_discharge / velocity_coefficient,
        device=readings.device,
    )


def format_report(
    performance: OrificeMouthpiecePerformance,
    uncertainty: UncertaintyBudget | None = None,
) -> str:
    """Render ``performance`` as a human-readable table with units.

    Args:
        performance: The evaluated run.
        uncertainty: Optional budget from :func:`fluid_lab.uncertainty.propagate`;
            when given, each value is printed with its standard uncertainty.
    """
    rows = performance.quantities()
    if uncertainty is not None:
        rows = attach_uncertainties(rows, uncertainty.standard_uncertainty)
    title = f"Orifice / mouthpiece test ({DEVICE_CHARACTERISTICS[performance.device].description})"
    return format_table(title, rows, notes=performance.warnings())
