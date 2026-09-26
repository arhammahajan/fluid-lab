"""Tests for the shared hydraulic power relation."""

import pytest
from fluid_lab.constants import WATER_DENSITY_KG_M3
from fluid_lab.hydraulics import specific_weight_kn_m3, water_power_kw


def test_specific_weight_of_water_is_9_81_kn_per_m3() -> None:
    assert specific_weight_kn_m3() == 9.81
    assert specific_weight_kn_m3(WATER_DENSITY_KG_M3) == 9.81


def test_specific_weight_scales_with_density() -> None:
    assert specific_weight_kn_m3(13600.0) == pytest.approx(133.416)


def test_water_power_is_rho_g_q_h() -> None:
    """1 m^3/s at 1 m of head is 9.81 kW for water."""
    assert water_power_kw(1.0, 1.0) == pytest.approx(9.81)
    assert water_power_kw(0.00224, 7.052) == pytest.approx(1000.0 * 9.81 * 0.00224 * 7.052 / 1000.0)


def test_water_power_is_linear_in_both_arguments() -> None:
    assert water_power_kw(2.0, 3.0) == pytest.approx(2 * water_power_kw(1.0, 3.0))
    assert water_power_kw(2.0, 3.0) == pytest.approx(3 * water_power_kw(2.0, 1.0))


def test_zero_discharge_or_head_gives_no_power() -> None:
    assert water_power_kw(0.0, 5.0) == 0.0
    assert water_power_kw(0.5, 0.0) == 0.0


@pytest.mark.parametrize("density", [0.0, -1000.0])
def test_rejects_non_positive_density(density: float) -> None:
    with pytest.raises(ValueError, match="liquid density"):
        water_power_kw(0.5, 5.0, density)
