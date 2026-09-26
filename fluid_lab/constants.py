"""Shared physical constants.

Only quantities that are identical for every rig live here.  Rig-specific
geometry (tank areas, pipe diameters, brake-drum dimensions, ...) belongs to the
experiment module that uses it, so that a re-built rig only requires editing one
file.

Units are encoded in the constant name, so a unit error is visible at the call
site (``MM_PER_M`` rather than a bare ``1000``).
"""

from typing import Final

# --------------------------------------------------------------------------- #
# Physical constants
# --------------------------------------------------------------------------- #

GRAVITY_MS2: Final[float] = 9.81
"""Acceleration due to gravity [m/s^2] (the value used by the lab manual)."""

WATER_DENSITY_KG_M3: Final[float] = 1000.0
"""Density of water [kg/m^3]."""

MERCURY_RELATIVE_DENSITY: Final[float] = 13.6
"""Relative density of mercury [-], used for U-tube and vacuum manometers."""

# --------------------------------------------------------------------------- #
# Unit conversion factors
# --------------------------------------------------------------------------- #

SECONDS_PER_MINUTE: Final[float] = 60.0
"""Seconds in one minute."""

SECONDS_PER_HOUR: Final[float] = 3600.0
"""Seconds in one hour (energy-meter input-power formula)."""

CM_PER_M: Final[float] = 100.0
"""Centimetres in one metre (metre-rule readings)."""

MM_PER_M: Final[float] = 1000.0
"""Millimetres in one metre (metre-rule and manometer readings)."""

KGF_CM2_TO_M_OF_WATER: Final[float] = 10.0
"""Bourdon gauge [kgf/cm^2] to water column [m]: 1 kgf/cm^2 == 10 m H2O."""
