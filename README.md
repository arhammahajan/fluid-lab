# fluid-lab

[![CI](https://github.com/arhammahajan/fluid-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/arhammahajan/fluid-lab/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Fluid-mechanics laboratory calculators for three standard undergraduate rigs: a
centrifugal pump test, a Francis turbine test, and an orifice/mouthpiece test.
The package converts raw instrument readings into SI results — discharge, head,
power, efficiency, and the orifice discharge coefficients — behind both a
command-line tool and an importable, fully typed Python API.

## Overview

Each experiment is implemented in its own module following one consistent shape:
a frozen `...Readings` dataclass holds the raw observations, an `evaluate()`
function maps it to a frozen `...Performance` dataclass, and a `format_report()`
function renders the result as an aligned, unit-annotated table.

| Module | Experiment | Principal results |
| --- | --- | --- |
| `fluid_lab.centrifugal_pump` | Centrifugal pump test | `Q_act`, `H`, B.P., I.P., `η` |
| `fluid_lab.francis_turbine` | Francis turbine test | `H`, `Q`, `T`, `E_i`, `E_o`, `η` |
| `fluid_lab.orifice_mouthpiece` | Orifice / mouthpiece test | `Q_act`, `Q_th`, `C_d`, `C_v`, `C_c` |

The calculation functions are pure — no printing, prompting, or global state —
so any run can be scripted, swept in a notebook, or tested directly.

Key properties:

- **No runtime dependencies.** Standard library only.
- **Typed.** Ships a `py.typed` marker and type-checks under `mypy --strict`.
- **Tested.** Unit, regression, and CLI tests, plus doctests, run in CI on every
  push and pull request.
- **Uncertainty-aware.** Measurement uncertainty is propagated to every result
  by differentiating the same `evaluate()` function, so the sensitivity model
  can never drift from the physics.
- **Scriptable.** Every reading has a flag, series of runs can be read from and
  written to CSV, and results are available as tables, JSON, or CSV.

## Requirements

- Python **3.12** or newer.
- No third-party runtime dependencies.

## Installation

Run directly from a checkout without installing:

```console
$ git clone https://github.com/arhammahajan/fluid-lab.git
$ cd fluid-lab
$ python -m fluid_lab --list
Available experiments:
  centrifugal-pump    Pump discharge, head, brake/indicated power and efficiency
  francis-turbine     Turbine head, discharge, torque, input/output power, efficiency
  orifice-mouthpiece  Discharge coefficients C_d, C_v and C_c
```

Or install the package, which also adds a `fluid-lab` console command equivalent
to `python -m fluid_lab`:

```console
# with uv
uv venv && uv pip install -e .

# or with pip
python -m venv .venv && . .venv/bin/activate
pip install -e .
```

Add the `dev` extra (`-e ".[dev]"`) to install the test and lint tooling.

## Quick start

```console
$ fluid-lab centrifugal-pump \
    --t-rise 12.5 --p-discharge 0.5 --vacuum 120 --t-pulses 20

Centrifugal pump test
=====================
Q_act actual discharge                  0.00224 m^3/s
H     total head                          7.052 m
B.P.  brake power (water power)        0.154963 kW
I.P.  indicated (input) power            0.5625 kW
eta   efficiency                        27.5491 %
```

## Command-line interface

### Experiments

| Sub-command | Description |
| --- | --- |
| `centrifugal-pump` | Pump discharge, head, brake/indicated power and efficiency |
| `francis-turbine` | Turbine head, discharge, torque, input/output power, efficiency |
| `orifice-mouthpiece` | Discharge coefficients `C_d`, `C_v` and `C_c` |

Run `fluid-lab --list` to list them, or `fluid-lab <experiment> --help` for the
flags and units of a single experiment.

### Interactive input

Run a sub-command with no flags to be prompted for each reading. A partial
command line prompts only for the values that were not supplied:

```console
$ fluid-lab centrifugal-pump
Time required for 100 mm rise [s]: 12.5
Discharge pressure gauge reading [kgf/cm^2]: 0.5
Suction vacuum gauge reading [mm Hg]: 120
Time required for 5 energy-meter pulses [s]: 20
...
```

### Scripted input

Pass readings as flags to make a run reproducible. Flags may be given before or
after the experiment name.

```console
$ fluid-lab francis-turbine \
    --p-discharge 0.4 --p-suction 100 --manometer 0.35 \
    --w1 5 --w2 1.5 --rpm 900

Francis turbine test
====================
H     total head                           5.36 m
A_p   supply pipe area               0.00502655 m^2
A_t   venturimeter throat area       0.00159043 m^2
h     manometer head difference            4.41 m
Q     discharge                       0.0151273 m^3/s
E_i   input (water) power              0.795418 kW
T     shaft torque                      4.05098 N m
E_o   output (shaft) power             0.381796 kW
eta   efficiency                        47.9994 %
```

Add `--datum 0.25` to the turbine when the two gauge centre-lines are not level.

### Shared options

These options are accepted by every sub-command, on either side of the
experiment name:

| Option | Effect |
| --- | --- |
| `--json` | Print the results as JSON instead of a formatted table. |
| `--csv PATH` | Write the results as CSV. Use `-` for standard output. |
| `--series PATH` | Read a series of runs from a CSV whose columns are the reading names. |
| `--uncertainty` | Also report the propagated standard uncertainty of each result. |

### Output formats

The default output is a human-readable table. `--json` produces a document
suitable for downstream tooling:

```console
$ fluid-lab orifice-mouthpiece \
    --t-rise 18.12 --head 600 --x 47.5 --y 10 --json
{
  "actual_discharge_m3_s": 0.0004828918322295805,
  "theoretical_discharge_m3_s": 0.0007787765230614461,
  "head_over_orifice_m": 0.6,
  "coefficient_of_discharge": 0.6200647014001986,
  "coefficient_of_velocity": 0.9695896898516747,
  "coefficient_of_contraction": 0.6395124740807161,
  "device": "orifice"
}
```

`--csv PATH` writes one row per run, which is what turns a set of runs into a
characteristic curve:

```console
$ fluid-lab centrifugal-pump --t-rise 12.5 --p-discharge 0.5 \
    --vacuum 120 --t-pulses 20 --csv -
actual_discharge_m3_s,total_head_m,brake_power_kw,indicated_power_kw,efficiency_percent
0.00224,7.052,0.15496346879999998,0.5625,27.549061119999998
```

### Series of runs

`--series` reads a CSV whose header names the readings using the attribute names
(the flags without `--`, with `_` instead of `-`). Each row is one run, and a
formatted table is printed per run unless `--csv` is also given:

```console
$ cat runs.csv
time_for_100mm_rise_s,discharge_pressure_kgf_cm2,suction_vacuum_mm_hg,time_for_pulses_s
12.5,0.5,120,20
10.0,0.4,100,22

$ fluid-lab centrifugal-pump --series runs.csv --csv -
actual_discharge_m3_s,total_head_m,brake_power_kw,indicated_power_kw,efficiency_percent
0.00224,7.052,0.15496346879999998,0.5625,27.549061119999998
0.0027999999999999995,5.78,0.15876504,0.5113636363636364,31.0473856
```

With `--uncertainty`, the exported CSV gains one `u_<field>` column per result.

## Experiments

Every reading is expressed in the unit in which the rig instrument is graduated;
the conversions to SI live in `fluid_lab.units`. Inputs may be supplied as flags
or interactively.

### Centrifugal pump

A centrifugal pump draws water from a sump and discharges through a Bourdon
pressure gauge; a vacuum gauge is fitted on the suction side. Discharge is
measured volumetrically from the rise of level in the measuring tank, and the
shaft input power is measured with a single-phase energy meter.

| Option | Reading | Unit |
| --- | --- | --- |
| `--t-rise` | time for a 100 mm rise in the measuring tank | s |
| `--p-discharge` | delivery Bourdon gauge reading | kgf/cm² |
| `--vacuum` | suction vacuum gauge reading | mm Hg |
| `--t-pulses` | time for the timed energy-meter pulses | s |

| Quantity | Formula |
| --- | --- |
| Actual discharge | `Q_act = A_tank · Δh / t_rise` |
| Total head | `H = p_discharge/γ + p_vacuum/γ + z` |
| B.P. (water power) | `B.P. = ρ g Q_act H` |
| I.P. (shaft input power) | `I.P. = (3600 / K) · (n / t_pulses)` |
| Efficiency | `η = (B.P. / I.P.) · 100` |

with `A_tank = 0.7 m × 0.4 m = 0.28 m²`, `Δh = 0.1 m`, `z = 0.42 m`,
`K = 1600 rev/kWh`, `n = 5` pulses, and `ρg = 9.81 kN/m³`. `B.P.` is the lab
manual's label for the hydraulic (water) power delivered to the flow.

### Francis turbine

Water from the pump enters the turbine spiral casing and leaves through a draft
tube. A Bourdon gauge measures the inlet pressure, a vacuum gauge the outlet
suction, and a venturimeter in the supply line the discharge. The shaft is
loaded with a rope brake: two spring balances read the tight- and slack-side
tensions and the speed is read with a tachometer.

| Option | Reading | Unit |
| --- | --- | --- |
| `--p-discharge` | inlet pressure gauge `P_d` | kgf/cm² |
| `--p-suction` | outlet vacuum gauge `P_s` | mm Hg |
| `--manometer` | venturimeter mercury-manometer deflection `R` | m of mercury |
| `--w1` | spring balance, tight side `W1` | kg |
| `--w2` | spring balance, slack side `W2` | kg |
| `--rpm` | turbine speed `N` | rev/min |
| `--datum` | vertical distance between gauge centre-lines `z` (default 0) | m |

| Quantity | Formula |
| --- | --- |
| Total head | `H = p_discharge/γ + p_vacuum/γ + z` |
| Venturimeter head | `h = (ρ_Hg/ρ_w − 1) R = 12.6 R` |
| Discharge | `Q = C_d,venturi · A_p A_t √(2 g h) / √(A_p² − A_t²)` |
| Input (water) power | `E_i = ρ g Q H / 1000` |
| Torque | `T = (W1 + m_hanger + m_rope − W2) · g · R_eff` |
| Output (shaft) power | `E_o = 2π N T / (60 × 1000)` |
| Efficiency | `η = (E_o / E_i) · 100` |

with pipe diameter ⌀80 mm (`A_p`), venturimeter throat ⌀45 mm (`A_t`),
venturimeter coefficient 0.97, `R_eff = (D_drum + 2 t_rope)/2 = 0.112 m`,
`m_hanger = 0.094 kg`, and `m_rope = 0.093 kg`.

The `− 1` in the manometer factor accounts for the water column sitting on the
mercury; using the mercury column alone would overstate the head.

### Orifice and mouthpiece

Water from a constant-head tank discharges through a sharp-edged orifice or an
external mouthpiece into a collecting tank, where the flow rate is measured from
the rise of level. The jet is allowed to fall freely and its trajectory is used
to obtain the velocity at the vena contracta, separating the three coefficients.

| Option | Reading | Unit |
| --- | --- | --- |
| `--device` | `orifice` (default) or `mouthpiece` | – |
| `--t-rise` | time to collect the tank volume | s |
| `--head` | constant head over the device centre `H` | mm |
| `--x` | horizontal trajectory coordinate `x` | cm |
| `--y` | vertical trajectory coordinate `y` | cm |
| `--trajectory-file` | CSV of `x_cm,y_cm` points for the least-squares fit | – |

| Quantity | Formula |
| --- | --- |
| Actual discharge | `Q_act = V_collected / t` |
| Theoretical discharge | `Q_th = a √(2 g H)` |
| Coefficient of discharge | `C_d = Q_act / Q_th` |
| Coefficient of velocity | `C_v = x / √(4 y H)` |
| Coefficient of contraction | `C_c = C_d / C_v` |

with `a` the device area (⌀17 mm) and `V_collected = A_tank · Δh`. `C_v` follows
from the projectile relations `x = v t`, `y = g t²/2` with
`v = C_v √(2 g H)`.

Because those relations imply `y = x² / (4 C_v² H)` — a straight line through
the origin when `y` is plotted against `x²` — several trajectory points can be
combined into a least-squares slope that is far less sensitive to a single
misread coordinate than a single point. `--trajectory-file` accepts a CSV with
`x_cm,y_cm` columns and reports the fitted `C_v` alongside the single-point
value:

```console
$ cat trajectory.csv
x_cm,y_cm
10.0,0.44
20.0,1.77
30.0,3.99
40.0,7.09

$ fluid-lab orifice-mouthpiece --t-rise 18.12 --head 600 \
    --x 47.5 --y 10 --trajectory-file trajectory.csv

Orifice / mouthpiece test (sharp-edged orifice)
===============================================
Q_act actual discharge               0.000482892 m^3/s
Q_th  theoretical discharge          0.000778777 m^3/s
H     head over device                       0.6 m
C_d   coefficient of discharge          0.620065 -
C_v   coefficient of velocity            0.96959 -
C_c   coefficient of contraction        0.639512 -

Trajectory regression
=====================
C_v   least-squares fit over 4 points        0.969675 -
```

A large gap between the fitted and single-point `C_v` indicates a misread
trajectory point. The same fit is available as
`fluid_lab.orifice_mouthpiece.coefficient_of_velocity_from_trajectory`.

`C_c` is derived from `C_d = C_c · C_v` rather than measured independently, so it
carries the error of both other coefficients and serves as a consistency check.

## Sanity checks

Results are checked against physical limits and, where a check fails, a warning
line prefixed with `!` is printed beneath the table instead of raising an error:

- **Any coefficient above 1.0** (orifice/mouthpiece) — not physically possible
  for a real fitting.
- **`C_d` outside the indicative range for the device** — `orifice` 0.60–0.65,
  `mouthpiece` 0.80–0.86.
- **A mouthpiece whose `C_c` is far from 1.0** — the jet from a mouthpiece fills
  the outlet, so its contraction coefficient referred to the outlet is about one.
- **Efficiency above 100 %** (pump and turbine).
- **Non-positive shaft torque** (turbine) — `W2` exceeding `W1` plus the hanging
  masses usually means the spring balances are swapped or misread.

```console
$ fluid-lab orifice-mouthpiece --device mouthpiece \
    --t-rise 18.12 --head 600 --x 47.5 --y 10
Orifice / mouthpiece test (external cylindrical mouthpiece)
===========================================================
...
! C_d = 0.62 is outside the indicative range 0.8-0.86 for the external cylindrical mouthpiece
! the jet from a mouthpiece fills the outlet, so C_c should be about 1.0, but it is 0.64
```

The indicative ranges are order-of-magnitude guidance from standard texts rather
than tolerances, so exceeding one only produces a note.

## Uncertainty

`--uncertainty` propagates the reading uncertainties to every result and prints
each value rounded to the precision implied by its uncertainty:

```console
$ fluid-lab centrifugal-pump --t-rise 12.5 --p-discharge 0.5 \
    --vacuum 120 --t-pulses 20 --uncertainty

Centrifugal pump test
=====================
Q_act actual discharge           0.002240 +/- 0.000036 m^3/s
H     total head                 7.05 +/- 0.50 m
B.P.  brake power (water power)  0.155 +/- 0.011 kW
I.P.  indicated (input) power    0.5625 +/- 0.0056 kW
eta   efficiency                 27.5 +/- 2.0 %
```

`fluid_lab.uncertainty.propagate` combines the contributions as

```text
u(y) = sqrt( Σ_i (∂f/∂x_i)² · u(x_i)² )
```

obtaining the partial derivatives by central finite differences of the existing
`evaluate()` function. Nothing is hand-derived, so editing a formula cannot
silently invalidate a sensitivity expression.

```python
from fluid_lab import CentrifugalPumpReadings, propagate
from fluid_lab.centrifugal_pump import DEFAULT_UNCERTAINTIES, evaluate

readings = CentrifugalPumpReadings(12.5, 0.5, 120.0, 20.0)
budget = propagate(evaluate, readings, DEFAULT_UNCERTAINTIES)

print(budget.standard_uncertainty["efficiency_percent"])  # 2.0219574539524094
print(budget.dominant_source("efficiency_percent"))  # discharge_pressure_kgf_cm2
```

`dominant_source(result_field)` returns the reading that contributes most to a
result, and `UncertaintyBudget.as_columns()` exposes the values as `u_<field>`
keys for export. The defaults in each module's `DEFAULT_UNCERTAINTIES` are the
instruments' least counts halved and are intended as a starting point; replace
them with values from your own instrumentation before quoting a final budget.

The treatment is first-order and assumes independent readings. Correlated
instrument errors (for example one thermometer used for both a head and a
density correction) are not modelled.

## Library API

The package exports the readings and performance dataclasses, the three
`evaluate_*` functions, the shared hydraulic helpers, and the uncertainty
machinery from the top level:

```python
from fluid_lab import CentrifugalPumpReadings, evaluate_centrifugal_pump

readings = CentrifugalPumpReadings(
    time_for_100mm_rise_s=12.5,
    discharge_pressure_kgf_cm2=0.5,
    suction_vacuum_mm_hg=120.0,
    time_for_pulses_s=20.0,
)
performance = evaluate_centrifugal_pump(readings)
print(performance.total_head_m, performance.efficiency_percent)

from fluid_lab.centrifugal_pump import format_report

print(format_report(performance))
```

Because the functions are pure, a sweep of runs is a plain loop:

```python
from fluid_lab.centrifugal_pump import CentrifugalPumpReadings, evaluate

for time_s in (10.0, 12.5, 15.0):
    result = evaluate(CentrifugalPumpReadings(time_s, 0.5, 120.0, 20.0))
    print(f"{time_s:5.1f} s -> Q = {result.actual_discharge_m3_s:.5f} m^3/s")
```

The full public surface is declared in `fluid_lab.__all__`.

## Rig constants

Physical constants and unit conversions shared by every experiment live in
`fluid_lab/constants.py`:

| Constant | Value | Meaning |
| --- | --- | --- |
| `GRAVITY_MS2` | 9.81 | acceleration due to gravity [m/s²] |
| `WATER_DENSITY_KG_M3` | 1000.0 | density of water [kg/m³] |
| `MERCURY_RELATIVE_DENSITY` | 13.6 | relative density of mercury [–] |
| `KGF_CM2_TO_M_OF_WATER` | 10.0 | 1 kgf/cm² ≡ 10 m of water |
| `CM_PER_M`, `MM_PER_M` | 100.0, 1000.0 | metre-rule conversions |

Rig-specific geometry (tank areas, pipe diameters, brake dimensions, energy-meter
constant, hanger and rope masses) lives at the top of the experiment module that
uses it. Rebuilding a rig therefore means editing the geometry constants in one
file and nothing else.

## Model notes

Two relations inherited from the lab manual were dimensionally inconsistent and
are implemented in corrected form; this changes the absolute numbers reported
for those quantities relative to the manual and to pre-2.0 records.

- **Pump brake power is `ρ g Q H`, not `28 Q H`.** The manual's "equivalent
  weight of water" of 28 is not dimensionally consistent with `Q` in m³/s and
  `H` in m; the constant must be `ρg = 9.81 kN/m³`. Because `28 / 9.81 ≈ 2.854`,
  the manual's value overstates both B.P. and the efficiency by that factor.
- **The turbine venturimeter head is `12.6 R`, not `10.33 R`.** `10.33 m` is one
  atmosphere of water, which is not what a differential mercury manometer
  measures; for water flowing through a mercury U-tube the head per metre of
  deflection is `ρ_Hg/ρ_w − 1 = 12.6`. Discharge scales as `√h`, so `Q` is about
  10.4 % higher than the manual's relation implies.

Both conversions are applied consistently: all three experiments share the
single `13.6 / 1000` mercury conversion, the turbine head accepts the same
optional gauge-centre-line datum as the pump (defaulting to zero), and the
collected volumes are expressed as `area × rise` rather than as a bare literal.

## Development

```console
# install the package with its development tools
uv pip install -e ".[dev]"      # or: pip install -e ".[dev]"

pytest                          # unit, regression and CLI tests, plus doctests
mypy                            # strict type checking over fluid_lab and tests
ruff check .                    # lint
ruff format .                   # format
```

CI runs linting, formatting checks, strict type checking, and the full test
suite on Python 3.12 and 3.13 for every push and pull request.

### Project layout

```
fluid_lab/
├── constants.py            physical constants and conversion factors
├── units.py                instrument reading -> SI conversions
├── hydraulics.py           the shared rho g Q H power relation
├── validation.py           input checks with named-quantity error messages
├── uncertainty.py          finite-difference uncertainty propagation
├── export.py               CSV series input and result export
├── report.py               Quantity rows and aligned table rendering
├── centrifugal_pump.py     readings + performance + evaluate()
├── francis_turbine.py      readings + performance + evaluate()
├── orifice_mouthpiece.py   readings + performance + evaluate()
├── cli.py                  argparse front end and experiment registry
└── __main__.py             python -m fluid_lab
tests/                      unit, regression and CLI tests
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
