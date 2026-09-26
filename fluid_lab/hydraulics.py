"""Hydraulic power relations shared by the pump and turbine calculations.

The hydraulic power transferred between a machine and a liquid is

    ``P = rho * g * Q * H``

with ``Q`` the volumetric discharge and ``H`` the head.  Both the pump's
``B.P.`` and the turbine's ``E_i`` are this quantity, so it lives here rather
than being duplicated with different unit conventions in each module.
"""

from fluid_lab.constants import GRAVITY_MS2, WATER_DENSITY_KG_M3
from fluid_lab.validation import require_positive


def specific_weight_kn_m3(density_kg_m3: float = WATER_DENSITY_KG_M3) -> float:
    """Return the specific weight ``gamma = rho * g`` [kN/m^3].

    Args:
        density_kg_m3: Liquid density [kg/m^3]; defaults to water at ~4 degrees C.

    Returns:
        Specific weight [kN/m^3].  For water this is ``9.81 kN/m^3``.
    """
    return density_kg_m3 * GRAVITY_MS2 / 1000.0


def water_power_kw(
    discharge_m3_s: float,
    head_m: float,
    density_kg_m3: float = WATER_DENSITY_KG_M3,
) -> float:
    """Return the hydraulic power ``rho * g * Q * H`` [kW].

    Args:
        discharge_m3_s: Volumetric discharge [m^3/s].
        head_m: Head across the machine [m of the working liquid].
        density_kg_m3: Liquid density [kg/m^3]; defaults to water.

    Returns:
        Hydraulic power [kW].

    Raises:
        ValueError: If ``density_kg_m3`` is not positive.
    """
    require_positive("liquid density", density_kg_m3)
    return (density_kg_m3 * GRAVITY_MS2 * discharge_m3_s * head_m) / 1000.0
