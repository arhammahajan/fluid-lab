"""Conversions from raw instrument readings to SI quantities.

The rigs are read with a mixture of instruments:

* Bourdon pressure gauges, calibrated in ``kgf/cm^2``;
* mercury U-tube and vacuum manometers, read in ``mm Hg``;
* metre rules, read in ``cm`` or ``mm``.

Every helper converts one instrument reading into metres (of water, for heads),
so that the calculation functions only ever handle SI quantities with units in
their names.

The multiply-then-divide form of the pressure and mercury conversions is
deliberate: it is the operation order used by the original lab scripts, so
results are bit-for-bit reproducible.
"""

from fluid_lab.constants import (
    CM_PER_M,
    KGF_CM2_TO_M_OF_WATER,
    MERCURY_RELATIVE_DENSITY,
    MM_PER_M,
)


def gauge_pressure_to_head_m(reading_kgf_cm2: float) -> float:
    """Convert a Bourdon-gauge pressure reading to an equivalent water head.

    Args:
        reading_kgf_cm2: Gauge pressure in ``kgf/cm^2``.

    Returns:
        Equivalent head [m of water].
    """
    return reading_kgf_cm2 * KGF_CM2_TO_M_OF_WATER


def vacuum_to_head_m(reading_mm_hg: float) -> float:
    """Convert a mercury-column (vacuum) reading to an equivalent water head.

    Uses the mercury relative density from :mod:`fluid_lab.constants`, so all
    three experiments share one value (the original scripts mixed ``13.6/1000``
    with ``1.033/76`` for the same physical conversion).

    Args:
        reading_mm_hg: Manometer or vacuum-gauge reading [mm Hg].

    Returns:
        Equivalent head [m of water].
    """
    return reading_mm_hg * MERCURY_RELATIVE_DENSITY / MM_PER_M


def cm_to_m(value_cm: float) -> float:
    """Convert a centimetre reading to metres."""
    return value_cm / CM_PER_M


def mm_to_m(value_mm: float) -> float:
    """Convert a millimetre reading to metres."""
    return value_mm / MM_PER_M
