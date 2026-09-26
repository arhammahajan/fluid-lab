"""Fluid-mechanics laboratory experiment calculators.

Three experiments are implemented, each in its own module:

* :mod:`fluid_lab.centrifugal_pump` -- discharge, head, power and efficiency;
* :mod:`fluid_lab.francis_turbine` -- head, discharge, torque, power, efficiency;
* :mod:`fluid_lab.orifice_mouthpiece` -- ``C_d``, ``C_v`` and ``C_c``.

Every module exposes a frozen ``...Readings`` input dataclass, a frozen
``...Performance`` result dataclass and an ``evaluate()`` function that maps one
to the other.  The calculation functions are pure: no printing, no prompting and
no global state, so they are directly testable and reusable from a notebook.

Supporting modules:

* :mod:`fluid_lab.hydraulics` -- the shared ``rho g Q H`` power relation;
* :mod:`fluid_lab.units` -- instrument reading to SI conversions;
* :mod:`fluid_lab.uncertainty` -- propagation of measurement uncertainty;
* :mod:`fluid_lab.export` -- CSV import of runs and export of results;
* :mod:`fluid_lab.report` -- aligned, unit-annotated output.

Example:
    >>> from fluid_lab import CentrifugalPumpReadings, evaluate_centrifugal_pump
    >>> readings = CentrifugalPumpReadings(
    ...     time_for_100mm_rise_s=12.5,
    ...     discharge_pressure_kgf_cm2=0.5,
    ...     suction_vacuum_mm_hg=120.0,
    ...     time_for_10_pulses_s=20.0,
    ... )
    >>> performance = evaluate_centrifugal_pump(readings)
    >>> round(performance.total_head_m, 3)
    7.052
    >>> round(performance.efficiency_percent, 2)
    27.55
"""

from importlib.metadata import PackageNotFoundError, version

from fluid_lab.centrifugal_pump import (
    CentrifugalPumpPerformance,
    CentrifugalPumpReadings,
)
from fluid_lab.centrifugal_pump import evaluate as evaluate_centrifugal_pump
from fluid_lab.francis_turbine import (
    FrancisTurbinePerformance,
    FrancisTurbineReadings,
)
from fluid_lab.francis_turbine import evaluate as evaluate_francis_turbine
from fluid_lab.hydraulics import specific_weight_kn_m3, water_power_kw
from fluid_lab.orifice_mouthpiece import (
    OrificeDevice,
    OrificeMouthpiecePerformance,
    OrificeMouthpieceReadings,
    TrajectoryPoint,
)
from fluid_lab.orifice_mouthpiece import evaluate as evaluate_orifice_mouthpiece
from fluid_lab.uncertainty import UncertaintyBudget, propagate

try:
    __version__: str = version("fluid-lab")
except PackageNotFoundError:  # running from a source checkout that is not installed
    __version__ = "0.0.0+source"

__all__ = [
    "CentrifugalPumpPerformance",
    "CentrifugalPumpReadings",
    "FrancisTurbinePerformance",
    "FrancisTurbineReadings",
    "OrificeDevice",
    "OrificeMouthpiecePerformance",
    "OrificeMouthpieceReadings",
    "TrajectoryPoint",
    "UncertaintyBudget",
    "__version__",
    "evaluate_centrifugal_pump",
    "evaluate_francis_turbine",
    "evaluate_orifice_mouthpiece",
    "propagate",
    "specific_weight_kn_m3",
    "water_power_kw",
]
