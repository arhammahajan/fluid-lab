"""Francis-turbine test-rig calculations.

Apparatus
---------
Water from the pump enters the turbine spiral casing and leaves through a draft
tube.  A Bourdon gauge measures the pressure at inlet, a vacuum gauge the
suction at outlet, and a venturimeter in the supply line measures the discharge.
The shaft is loaded with a rope brake: two spring balances read the tight- and
slack-side tensions and the speed is read with a tachometer.

Formulas
--------
=========================  ====================================================
Total head                 ``H = p_discharge / gamma + p_vacuum / gamma + z``
Manometer head             ``h = R * (rho_Hg / rho_w - 1) = 12.6 * R``
Venturimeter discharge     ``Q = 0.97 * A_p * A_t * sqrt(2 g h) / sqrt(A_p^2 - A_t^2)``
Input (water) power        ``E_i = rho * g * Q * H / 1000``
Torque                     ``T = (W1 + m_hanger + m_rope - W2) * g * R_eff``
Output (shaft) power       ``E_o = 2 pi N T / (60 * 1000)``
Efficiency                 ``eta = (E_o / E_i) * 100``
=========================  ====================================================

where ``R_eff = (D_drum + 2 t_rope) / 2`` is the effective brake radius, ``z`` is
the vertical distance between the two gauge centre-lines, and ``R`` is the
mercury-manometer deflection in **metres of mercury**.

.. note::
   Two corrections were made in version 2.0, both documented in the README
   section "Results changed in version 2.0":

   * ``h = 10.33 * R`` was replaced by the standard mercury-U-tube relation
     ``h = (rho_Hg / rho_w - 1) * R = 12.6 R``.  10.33 m is one *atmosphere* of
     water, which is not what a mercury manometer measures.
   * the head had no datum term at all.  It now accepts ``datum_difference_m``,
     matching the pump module, and defaults to zero so that an un-recorded
     datum does not silently change a result.
"""

from dataclasses import dataclass
from math import pi, sqrt
from typing import Final

from fluid_lab.constants import (
    GRAVITY_MS2,
    MERCURY_RELATIVE_DENSITY,
    SECONDS_PER_MINUTE,
)
from fluid_lab.hydraulics import water_power_kw
from fluid_lab.report import Quantity, attach_uncertainties
from fluid_lab.report import format_report as format_table
from fluid_lab.uncertainty import UncertaintyBudget
from fluid_lab.units import gauge_pressure_to_head_m, vacuum_to_head_m
from fluid_lab.validation import require_non_negative, require_positive

# --------------------------------------------------------------------------- #
# Rig geometry
# --------------------------------------------------------------------------- #

PIPE_DIAMETER_M: Final[float] = 0.08
"""Internal diameter of the supply pipe at the pressure tap [m]."""

THROAT_DIAMETER_M: Final[float] = 0.045
"""Internal diameter of the venturimeter throat [m]."""

PIPE_AREA_M2: Final[float] = (pi / 4) * (PIPE_DIAMETER_M**2)
"""Cross-sectional area of the supply pipe ``A_p`` [m^2]."""

THROAT_AREA_M2: Final[float] = (pi / 4) * (THROAT_DIAMETER_M**2)
"""Cross-sectional area of the venturimeter throat ``A_t`` [m^2]."""

VENTURIMETER_DISCHARGE_COEFFICIENT: Final[float] = 0.97
"""Calibrated discharge coefficient of the venturimeter [-]."""

BRAKE_DRUM_DIAMETER_M: Final[float] = 0.2
"""Outer diameter of the brake drum [m]."""

ROPE_DIAMETER_M: Final[float] = 0.012
"""Diameter of the brake rope [m]."""

EFFECTIVE_BRAKE_RADIUS_M: Final[float] = (BRAKE_DRUM_DIAMETER_M + 2 * ROPE_DIAMETER_M) / 2
"""Effective brake radius ``R_eff``, measured to the rope centre-line [m]."""

HANGER_MASS_KG: Final[float] = 0.094
"""Mass of the hanger on the tight side, added to ``W1`` [kg].

Rig-specific: weigh it if the result matters.
"""

ROPE_MASS_KG: Final[float] = 0.093
"""Mass of the rope, added to ``W1`` [kg].  Rig-specific: weigh it."""

MANOMETER_HEAD_FACTOR: Final[float] = MERCURY_RELATIVE_DENSITY - 1.0
"""Head per metre of mercury deflection, ``rho_Hg / rho_w - 1`` [-].

For water flowing through a mercury U-tube the pressure head is
``h = R * (S_Hg - S_w) / S_w``, i.e. ``12.6 R`` for ``R`` in metres of mercury.
The buoyancy of the water column above the mercury is what the ``- 1`` accounts
for; using the mercury column alone would overstate the head.
"""

# --------------------------------------------------------------------------- #
# Assumed instrument uncertainties
# --------------------------------------------------------------------------- #

DEFAULT_UNCERTAINTIES: Final[dict[str, float]] = {
    "discharge_pressure_kgf_cm2": 0.05,  # 0.1 kgf/cm^2 least count, half a division
    "suction_vacuum_mm_hg": 1.0,  # 2 mm mercury scale, half a division
    "manometer_deflection_m": 0.0005,  # 1 mm mercury scale, half a division
    "tight_side_mass_kg": 0.01,  # 0.02 kg spring-balance least count
    "slack_side_mass_kg": 0.01,
    "speed_rpm": 2.0,  # hand tachometer
    "datum_difference_m": 0.002,  # steel rule
}
"""Assumed absolute standard uncertainties [same unit as the reading].

These are the instruments' least counts divided by two, which is the usual
laboratory convention.  Replace them with the values from your own instrument
data before quoting a final uncertainty budget.
"""


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class FrancisTurbineReadings:
    """Raw observations from one run of the Francis-turbine experiment.

    Attributes:
        discharge_pressure_kgf_cm2: Inlet pressure-gauge reading ``P_d`` [kgf/cm^2].
        suction_vacuum_mm_hg: Outlet vacuum-gauge reading ``P_s`` [mm Hg].
        manometer_deflection_m: Venturimeter mercury-manometer deflection ``R``
            [m of mercury].
        tight_side_mass_kg: Spring-balance reading on the tight side ``W1`` [kg].
        slack_side_mass_kg: Spring-balance reading on the slack side ``W2`` [kg].
        speed_rpm: Turbine speed ``N`` [rev/min].
        datum_difference_m: Vertical distance between the two gauge centre-lines
            ``z`` [m].  Defaults to zero, which is what the original script
            implicitly assumed.
    """

    discharge_pressure_kgf_cm2: float
    suction_vacuum_mm_hg: float
    manometer_deflection_m: float
    tight_side_mass_kg: float
    slack_side_mass_kg: float
    speed_rpm: float
    datum_difference_m: float = 0.0


@dataclass(frozen=True, slots=True)
class FrancisTurbinePerformance:
    """Performance computed from :class:`FrancisTurbineReadings`."""

    total_head_m: float
    """Total head ``H`` [m of water]."""

    pipe_area_m2: float
    """Supply-pipe area ``A_p`` [m^2]; a rig constant, reported for the record."""

    throat_area_m2: float
    """Venturimeter throat area ``A_t`` [m^2]; a rig constant."""

    manometer_head_m: float
    """Venturimeter head difference ``h`` [m of water]."""

    discharge_m3_s: float
    """Discharge ``Q`` [m^3/s]."""

    input_power_kw: float
    """Water power available at the turbine inlet ``E_i`` [kW]."""

    torque_nm: float
    """Shaft torque ``T`` [N m]."""

    output_power_kw: float
    """Shaft output power ``E_o`` [kW]."""

    efficiency_percent: float
    """Overall efficiency ``eta = E_o/E_i * 100`` [%]."""

    def warnings(self) -> tuple[str, ...]:
        """Return human-readable warnings for physically impossible results."""
        notes: list[str] = []
        if self.efficiency_percent > 100.0:
            notes.append(
                f"efficiency is {self.efficiency_percent:.3g} %, which exceeds 100 %: "
                "check the brake readings and the energy balance"
            )
        if self.torque_nm <= 0.0:
            notes.append(
                "shaft torque is not positive, so W2 exceeds W1 plus the hanger and "
                "rope masses: the spring balances are probably swapped or misread"
            )
        return tuple(notes)

    def quantities(self) -> tuple[Quantity, ...]:
        """Return the results as displayable rows, in report order."""
        return (
            Quantity("total_head_m", "H", "total head", self.total_head_m, "m"),
            Quantity("pipe_area_m2", "A_p", "supply pipe area", self.pipe_area_m2, "m^2"),
            Quantity(
                "throat_area_m2", "A_t", "venturimeter throat area", self.throat_area_m2, "m^2"
            ),
            Quantity(
                "manometer_head_m", "h", "manometer head difference", self.manometer_head_m, "m"
            ),
            Quantity("discharge_m3_s", "Q", "discharge", self.discharge_m3_s, "m^3/s"),
            Quantity("input_power_kw", "E_i", "input (water) power", self.input_power_kw, "kW"),
            Quantity("torque_nm", "T", "shaft torque", self.torque_nm, "N m"),
            Quantity("output_power_kw", "E_o", "output (shaft) power", self.output_power_kw, "kW"),
            Quantity("efficiency_percent", "eta", "efficiency", self.efficiency_percent, "%"),
        )


# --------------------------------------------------------------------------- #
# Calculations
# --------------------------------------------------------------------------- #


def total_head(
    discharge_pressure_kgf_cm2: float,
    suction_vacuum_mm_hg: float,
    datum_difference_m: float = 0.0,
) -> float:
    """Return the turbine head [m of water] from the gauge readings.

    Args:
        discharge_pressure_kgf_cm2: Inlet pressure-gauge reading [kgf/cm^2].
        suction_vacuum_mm_hg: Outlet vacuum-gauge reading [mm Hg].
        datum_difference_m: Vertical distance between the gauge centre-lines [m].

    Returns:
        Total head ``H`` [m of water].
    """
    return (
        gauge_pressure_to_head_m(discharge_pressure_kgf_cm2)
        + vacuum_to_head_m(suction_vacuum_mm_hg)
        + datum_difference_m
    )


def manometer_head(deflection_m: float) -> float:
    """Return the venturimeter head difference [m of water].

    Args:
        deflection_m: Mercury-manometer deflection ``R`` [m of mercury].

    Returns:
        Head difference ``h`` [m of water].

    Raises:
        ValueError: If ``deflection_m`` is negative.
    """
    require_non_negative("manometer deflection", deflection_m)
    return deflection_m * MANOMETER_HEAD_FACTOR


def discharge(manometer_head_m: float) -> float:
    """Return the venturimeter discharge [m^3/s] for a head difference.

    Args:
        manometer_head_m: Head difference across the venturimeter [m of water].

    Returns:
        Discharge ``Q`` [m^3/s].

    Raises:
        ValueError: If ``manometer_head_m`` is negative.
    """
    require_non_negative("manometer head difference", manometer_head_m)
    numerator = (
        VENTURIMETER_DISCHARGE_COEFFICIENT
        * PIPE_AREA_M2
        * THROAT_AREA_M2
        * sqrt(2 * GRAVITY_MS2 * manometer_head_m)
    )
    return numerator / sqrt(PIPE_AREA_M2**2 - THROAT_AREA_M2**2)


def input_power(discharge_m3_s: float, head_m: float) -> float:
    """Return the water power available at the turbine inlet ``E_i`` [kW].

    Args:
        discharge_m3_s: Discharge [m^3/s].
        head_m: Total head [m of water].

    Returns:
        ``E_i`` [kW].
    """
    return water_power_kw(discharge_m3_s, head_m)


def torque(tight_side_mass_kg: float, slack_side_mass_kg: float) -> float:
    """Return the rope-brake shaft torque [N m].

    Args:
        tight_side_mass_kg: Spring-balance reading on the tight side ``W1`` [kg].
        slack_side_mass_kg: Spring-balance reading on the slack side ``W2`` [kg].

    Returns:
        Torque ``T`` [N m].

    Note:
        The hanger and rope masses are added to the tight side, following the
        lab manual.  A negative result means ``W2`` exceeds
        ``W1 + m_hanger + m_rope``, which is not physically possible for a
        loaded brake; the value is still returned so that the reading error is
        visible downstream (see
        :meth:`FrancisTurbinePerformance.warnings`).
    """
    net_mass_kg = tight_side_mass_kg + HANGER_MASS_KG + ROPE_MASS_KG - slack_side_mass_kg
    return net_mass_kg * GRAVITY_MS2 * EFFECTIVE_BRAKE_RADIUS_M


def output_power(torque_nm: float, speed_rpm: float) -> float:
    """Return the shaft output power ``E_o`` [kW].

    Args:
        torque_nm: Shaft torque [N m].
        speed_rpm: Turbine speed ``N`` [rev/min].

    Returns:
        ``E_o`` [kW].

    Raises:
        ValueError: If ``speed_rpm`` is negative.
    """
    require_non_negative("turbine speed", speed_rpm)
    return (2 * pi * speed_rpm * torque_nm) / (SECONDS_PER_MINUTE * 1000.0)


def evaluate(readings: FrancisTurbineReadings) -> FrancisTurbinePerformance:
    """Run the full calculation chain for one set of readings.

    Args:
        readings: Raw observations from the experiment.

    Returns:
        Head, discharge, both powers, torque and the efficiency.

    Raises:
        ValueError: If a reading makes a formula undefined (zero water power,
            negative speed, negative manometer deflection).
    """
    head_m = total_head(
        readings.discharge_pressure_kgf_cm2,
        readings.suction_vacuum_mm_hg,
        readings.datum_difference_m,
    )
    manometer_head_m = manometer_head(readings.manometer_deflection_m)
    discharge_m3_s = discharge(manometer_head_m)
    input_power_kw = input_power(discharge_m3_s, head_m)
    require_positive("input (water) power E_i", input_power_kw)
    torque_nm = torque(readings.tight_side_mass_kg, readings.slack_side_mass_kg)
    output_power_kw = output_power(torque_nm, readings.speed_rpm)
    return FrancisTurbinePerformance(
        total_head_m=head_m,
        pipe_area_m2=PIPE_AREA_M2,
        throat_area_m2=THROAT_AREA_M2,
        manometer_head_m=manometer_head_m,
        discharge_m3_s=discharge_m3_s,
        input_power_kw=input_power_kw,
        torque_nm=torque_nm,
        output_power_kw=output_power_kw,
        efficiency_percent=(output_power_kw / input_power_kw) * 100.0,
    )


def format_report(
    performance: FrancisTurbinePerformance,
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
    return format_table("Francis turbine test", rows, notes=performance.warnings())
