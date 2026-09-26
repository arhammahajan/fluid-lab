"""Input validation helpers shared by the experiment modules.

The lab scripts silently produced ``ZeroDivisionError``, ``nan`` or ``inf`` when
a reading was nonsense.  Failing loudly with the *name* of the offending
quantity makes a mistyped reading obvious instead of producing a plausible
looking wrong number in a lab report.
"""

import math


def require_finite(name: str, value: float) -> float:
    """Return ``value`` unchanged if it is a finite number.

    Args:
        name: Human-readable quantity name, used in the error message.
        value: Value to check.

    Returns:
        The validated ``value``.

    Raises:
        ValueError: If ``value`` is ``nan`` or infinite.
    """
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return value


def require_positive(name: str, value: float) -> float:
    """Return ``value`` unchanged if it is finite and strictly positive.

    Args:
        name: Human-readable quantity name, used in the error message.
        value: Value to check.

    Returns:
        The validated ``value``.

    Raises:
        ValueError: If ``value`` is not finite or is less than or equal to zero.
    """
    require_finite(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return value


def require_non_negative(name: str, value: float) -> float:
    """Return ``value`` unchanged if it is finite and not negative.

    Args:
        name: Human-readable quantity name, used in the error message.
        value: Value to check.

    Returns:
        The validated ``value``.

    Raises:
        ValueError: If ``value`` is not finite or is negative.
    """
    require_finite(name, value)
    if value < 0.0:
        raise ValueError(f"{name} must not be negative, got {value!r}")
    return value
