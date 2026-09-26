"""Centrifugal-pump test-rig calculations.

Apparatus
---------
A centrifugal pump draws water from a sump and discharges through a Bourdon
pressure gauge; a vacuum gauge is fitted on the suction side.  Discharge is
measured volumetrically from the rise of level in the measuring tank, and the
shaft input power is measured with a single-phase energy meter.

Formulas
--------
=========================  ==================================================
Actual discharge           ``Q_act = A_tank * d_rise / t_rise``
Total head                 ``H = p_discharge / gamma + p_vacuum / gamma + z``
B.P. (water power)         ``B.P. = rho * g * Q_act * H``
I.P. (shaft input power)   ``I.P. = (3600 / K) * (n_pulses / t_pulses)``
Efficiency                 ``eta = (B.P. / I.P.) * 100``
=========================  ==================================================

where ``A_tank`` is the plan area of the measuring tank, ``d_rise`` is the level
rise, ``gamma`` is the specific weight of water (``rho * g = 9.81 kN/m^3``),
``z`` is the vertical distance between the gauge centre-line and the tank water
surface and ``K`` is the energy meter constant in revolutions per kWh.

.. note::
   Up to version 1.0 this module computed ``B.P. = 28 * Q_act * H`` using an
   "equivalent weight of water" of 28 pulled from the lab manual.  That factor is
   dimensionally wrong for ``Q`` in m^3/s and ``H`` in m -- the constant must be
   ``rho * g = 9.81 kN/m^3`` -- and inflated both B.P. and the efficiency by
   about 2.85x.  The hydraulic power is now computed properly via
   :func:`fluid_lab.hydraulics.water_power_kw`.  See the README section
   "Results changed in version 2.0".
"""

from dataclasses import dataclass
from typing import Final

from fluid_lab.constants import SECONDS_PER_HOUR
from fluid_lab.hydraulics import water_power_kw
from fluid_lab.report import Quantity, attach_uncertainties
from fluid_lab.report import format_report as format_table
from fluid_lab.uncertainty import UncertaintyBudget
from fluid_lab.units import gauge_pressure_to_head_m, vacuum_to_head_m
from fluid_lab.validation import require_positive

# --------------------------------------------------------------------------- #
# Rig geometry
# --------------------------------------------------------------------------- #

MEASURING_TANK_LENGTH_M: Final[float] = 0.7
"""Length of the measuring tank [m]."""

MEASURING_TANK_WIDTH_M: Final[float] = 0.4
"""Width of the measuring tank [m]."""

MEASURING_TANK_AREA_M2: Final[float] = MEASURING_TANK_LENGTH_M * MEASURING_TANK_WIDTH_M
"""Plan area of the measuring tank [m^2]."""

MEASURING_TANK_RISE_M: Final[float] = 0.1
"""Level rise used for one discharge measurement [m] (100 mm)."""

PIEZOMETER_LEVEL_DIFFERENCE_M: Final[float] = 0.42
"""Vertical distance between the gauge centre-line and the tank water surface [m].

Called ``x`` in the original script.
"""

ENERGY_METER_CONSTANT_REV_PER_KWH: Final[float] = 1600.0
"""Energy-meter disc constant ``K`` [revolutions per kWh]."""

PULSES_PER_OBSERVATION: Final[float] = 5.0
"""Number of energy-meter pulses timed per observation."""

# --------------------------------------------------------------------------- #
# Assumed instrument uncertainties
# --------------------------------------------------------------------------- #

DEFAULT_UNCERTAINTIES: Final[dict[str, float]] = {
    "time_for_100mm_rise_s": 0.2,  # hand stopwatch: reaction time + scale reading
    "discharge_pressure_kgf_cm2": 0.05,  # 0.1 kgf/cm^2 least count, half a division
    "suction_vacuum_mm_hg": 1.0,  # 2 mm mercury scale, half a division
    "time_for_pulses_s": 0.2,  # hand stopwatch
}
"""Assumed absolute standard uncertainties [same unit as the reading].

These are the instruments' least counts divided by two, which is the usual
laboratory convention.  Replace them with the values from your own instrument
data or calibration certificates before quoting a final uncertainty budget.
"""


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CentrifugalPumpReadings:
    """Raw observations from one run of the centrifugal-pump experiment.

    Attributes:
        time_for_100mm_rise_s: Time for a 100 mm rise in the measuring tank [s].
        discharge_pressure_kgf_cm2: Discharge pressure-gauge reading [kgf/cm^2].
        suction_vacuum_mm_hg: Suction vacuum-gauge reading [mm Hg].
        time_for_pulses_s: Time for the energy-meter disc to complete
            :data:`PULSES_PER_OBSERVATION` pulses [s].
    """

    time_for_100mm_rise_s: float
    discharge_pressure_kgf_cm2: float
    suction_vacuum_mm_hg: float
    time_for_pulses_s: float


@dataclass(frozen=True, slots=True)
class CentrifugalPumpPerformance:
    """Performance computed from :class:`CentrifugalPumpReadings`."""

    actual_discharge_m3_s: float
    """Actual discharge ``Q_act`` [m^3/s]."""

    total_head_m: float
    """Total head ``H`` [m of water]."""

    brake_power_kw: float
    """``B.P.`` [kW] -- the lab manual's name for the hydraulic output power
    ``rho * g * Q_act * H``."""

    indicated_power_kw: float
    """``I.P.`` [kW] -- shaft input power from the energy meter."""

    efficiency_percent: float
    """Overall efficiency ``eta = B.P./I.P. * 100`` [%]."""

    def is_consistent(self) -> bool:
        """Whether the efficiency is physically possible (``<= 100 %``)."""
        return self.efficiency_percent <= 100.0

    def warnings(self) -> tuple[str, ...]:
        """Return human-readable warnings for physically impossible results."""
        if self.is_consistent():
            return ()
        return (
            f"efficiency is {self.efficiency_percent:.3g} %, which exceeds 100 %: "
            "check the head gauges, the tank area and the energy-meter constant",
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
            Quantity("total_head_m", "H", "total head", self.total_head_m, "m"),
            Quantity(
                "brake_power_kw", "B.P.", "brake power (water power)", self.brake_power_kw, "kW"
            ),
            Quantity(
                "indicated_power_kw",
                "I.P.",
                "indicated (input) power",
                self.indicated_power_kw,
                "kW",
            ),
            Quantity("efficiency_percent", "eta", "efficiency", self.efficiency_percent, "%"),
        )


# --------------------------------------------------------------------------- #
# Calculations
# --------------------------------------------------------------------------- #


def actual_discharge(time_for_rise_s: float) -> float:
    """Return the actual discharge [m^3/s] from the measuring-tank rise.

    Args:
        time_for_rise_s: Time for a :data:`MEASURING_TANK_RISE_M` rise [s].

    Returns:
        Volumetric discharge ``Q_act`` [m^3/s].

    Raises:
        ValueError: If ``time_for_rise_s`` is not positive.
    """
    require_positive("time for 100 mm rise", time_for_rise_s)
    return (MEASURING_TANK_AREA_M2 * MEASURING_TANK_RISE_M) / time_for_rise_s


def total_head(discharge_pressure_kgf_cm2: float, suction_vacuum_mm_hg: float) -> float:
    """Return the pump head [m of water] from the two gauge readings.

    Args:
        discharge_pressure_kgf_cm2: Discharge pressure-gauge reading [kgf/cm^2].
        suction_vacuum_mm_hg: Suction vacuum-gauge reading [mm Hg].

    Returns:
        Total head ``H`` [m of water].
    """
    return (
        gauge_pressure_to_head_m(discharge_pressure_kgf_cm2)
        + vacuum_to_head_m(suction_vacuum_mm_hg)
        + PIEZOMETER_LEVEL_DIFFERENCE_M
    )


def brake_power(discharge_m3_s: float, head_m: float) -> float:
    """Return the lab-manual ``B.P.`` [kW] for a discharge and head.

    This is the hydraulic power delivered to the water, ``rho * g * Q * H``.

    Args:
        discharge_m3_s: Actual discharge [m^3/s].
        head_m: Total head [m of water].

    Returns:
        ``B.P.`` [kW].
    """
    return water_power_kw(discharge_m3_s, head_m)


def indicated_power(time_for_pulses_s: float) -> float:
    """Return the shaft input power ``I.P.`` [kW] from the energy meter.

    Args:
        time_for_pulses_s: Time for :data:`PULSES_PER_OBSERVATION` disc
            pulses [s].

    Returns:
        ``I.P.`` [kW].

    Raises:
        ValueError: If ``time_for_pulses_s`` is not positive.
    """
    require_positive(f"time for {PULSES_PER_OBSERVATION:g} energy-meter pulses", time_for_pulses_s)
    energy_meter_factor = SECONDS_PER_HOUR / ENERGY_METER_CONSTANT_REV_PER_KWH
    return energy_meter_factor * (PULSES_PER_OBSERVATION / time_for_pulses_s)


def evaluate(readings: CentrifugalPumpReadings) -> CentrifugalPumpPerformance:
    """Run the full calculation chain for one set of readings.

    Args:
        readings: Raw observations from the experiment.

    Returns:
        Discharge, head, both powers and the efficiency.

    Raises:
        ValueError: If either timed observation is not positive.
    """
    discharge = actual_discharge(readings.time_for_100mm_rise_s)
    head = total_head(readings.discharge_pressure_kgf_cm2, readings.suction_vacuum_mm_hg)
    output_power = brake_power(discharge, head)
    input_power = indicated_power(readings.time_for_pulses_s)
    return CentrifugalPumpPerformance(
        actual_discharge_m3_s=discharge,
        total_head_m=head,
        brake_power_kw=output_power,
        indicated_power_kw=input_power,
        efficiency_percent=(output_power / input_power) * 100.0,
    )


def format_report(
    performance: CentrifugalPumpPerformance,
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
    return format_table("Centrifugal pump test", rows, notes=performance.warnings())
