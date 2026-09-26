# Fluid Mechanics Experiments

Typed, tested calculators for three undergraduate fluid-mechanics laboratory
experiments:

| Module | Experiment | Computes |
| --- | --- | --- |
| `fluid_lab.centrifugal_pump` | Centrifugal pump test | `Q_act`, `H`, B.P., I.P., efficiency |
| `fluid_lab.francis_turbine` | Francis turbine test | `H`, `Q`, `T`, `E_i`, `E_o`, efficiency |
| `fluid_lab.orifice_mouthpiece` | Orifice / mouthpiece test | `Q_act`, `Q_th`, `C_d`, `C_v`, `C_c` |

The original three scripts (`centrifugal_pump.py`, `francis_turbine.py`,
`orifice_mouthpiece.py`) are superseded by this package.

> **Version 2.0 fixes two physics errors** that changed the reported numbers.
> The pump brake power no longer uses a dimensionally wrong "equivalent weight of
> water" of 28, and the venturimeter head no longer uses `10.33 × R`. Read
> [Results changed in version 2.0](#results-changed-in-version-20) before
> comparing against older records.

---

## Contents

- [Requirements](#requirements) · [Install](#install) · [Usage](#usage)
- [Experiments and formulas](#experiments-and-formulas)
- [Input reference](#input-reference)
- [Uncertainty](#uncertainty)
- [Series and CSV](#series-and-csv)
- [Numerics](#numerics) · [Results changed in version 2.0](#results-changed-in-version-20)
- [Development](#development) · [Open questions](#open-questions) · [License](#license)

---

## Requirements

Python **3.12** or newer. No third-party runtime dependencies.

## Install

### Run it from a checkout (no install needed)

```console
$ git clone <this-repo>
$ cd fluid_mechanics_experiments
$ python -m fluid_lab --list
Available experiments:
  centrifugal-pump    Pump discharge, head, brake/indicated power and efficiency
  francis-turbine     Turbine head, discharge, torque, input/output power, efficiency
  orifice-mouthpiece  Discharge coefficients C_d, C_v and C_c
```

### Install as a package

```console
# with uv (recommended)
uv venv && uv pip install -e ".[dev]"

# or with pip
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

Installing adds a `fluid-lab` console command equivalent to `python -m fluid_lab`.

---

## Usage

### Interactive (same feel as the original scripts)

Run a sub-command with no flags and you are prompted for each reading. A partial
command line prompts only for what is missing.

```console
$ python -m fluid_lab centrifugal-pump
Time required for 100 mm rise [s]: 12.5
Discharge pressure gauge reading [kgf/cm^2]: 0.5
Suction vacuum gauge reading [mm Hg]: 120
Time required for 10 pulses [s]: 20

Centrifugal pump test
=====================
Q_act actual discharge                  0.00224 m^3/s
H     total head                          7.052 m
B.P.  brake power (water power)        0.154963 kW
I.P.  indicated (input) power            0.5625 kW
eta   efficiency                        27.5491 %
```

### Scripted

Every reading can be passed as a flag, which makes a run reproducible:

```console
$ python -m fluid_lab francis-turbine \
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

Add `--datum 0.25` to the turbine if the two gauge centre-lines are not level.

### Shared flags

| Flag | Effect |
| --- | --- |
| `--json` | print results as JSON instead of a table |
| `--csv PATH` | write results as CSV (`-` for standard output) |
| `--series PATH` | read a series of runs from a CSV whose columns are the reading names |
| `--uncertainty` | also report the propagated standard uncertainty of each result |

Each may be given before or after the experiment name.

### Machine-readable output

```console
$ python -m fluid_lab orifice-mouthpiece \
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

### As a library

```python
from fluid_lab import CentrifugalPumpReadings, evaluate_centrifugal_pump

readings = CentrifugalPumpReadings(
    time_for_100mm_rise_s=12.5,
    discharge_pressure_kgf_cm2=0.5,
    suction_vacuum_mm_hg=120.0,
    time_for_10_pulses_s=20.0,
)
performance = evaluate_centrifugal_pump(readings)
print(performance.total_head_m, performance.efficiency_percent)
```

Because the calculation functions are pure, a whole set of runs can be swept in a
loop or a notebook:

```python
from fluid_lab.centrifugal_pump import CentrifugalPumpReadings, evaluate

for time_s in (10.0, 12.5, 15.0):
    result = evaluate(CentrifugalPumpReadings(time_s, 0.5, 120.0, 20.0))
    print(f"{time_s:5.1f} s -> Q={result.actual_discharge_m3_s:.5f} m3/s")
```

---

## Experiments and formulas

### Centrifugal pump

| Quantity | Formula |
| --- | --- |
| Actual discharge | `Q_act = A_tank · Δh_rise / t_rise` |
| Total head | `H = p_discharge/γ + p_vacuum/γ + z` |
| B.P. (water power) | `B.P. = ρ g Q_act H` |
| I.P. (input power) | `I.P. = (3600 / K) · (n_pulses / t_pulses)` |
| Efficiency | `η = (B.P. / I.P.) · 100` |

`A_tank = 0.7 m × 0.4 m`, `Δh_rise = 0.1 m`, `z = 0.42 m`,
`K = 1600 rev/kWh`, `n_pulses = 5`, and `ρg = 9.81 kN/m³`.
`B.P.` is the lab manual's label for the hydraulic (water) power.

### Francis turbine

| Quantity | Formula |
| --- | --- |
| Total head | `H = p_discharge/γ + p_vacuum/γ + z` |
| Venturimeter head | `h = (ρ_Hg/ρ_w − 1) R = 12.6 R` |
| Discharge | `Q = 0.97 A_p A_t √(2 g h) / √(A_p² − A_t²)` |
| Input (water) power | `E_i = ρ g Q H / 1000` |
| Torque | `T = (W1 + m_hanger + m_rope − W2) · g · R_eff` |
| Output (shaft) power | `E_o = 2π N T / (60 × 1000)` |
| Efficiency | `η = (E_o / E_i) · 100` |

`A_p` is the supply pipe (⌀80 mm), `A_t` the venturimeter throat (⌀45 mm),
`R_eff = (D_drum + 2 t_rope)/2 = (0.2 + 2×0.012)/2 = 0.112 m`,
`m_hanger = 0.094 kg`, `m_rope = 0.093 kg`, and `z` is the optional
gauge-centre-line datum (`--datum`, default 0).

The `− 1` in the manometer factor is the buoyancy of the water column sitting on
the mercury; using the mercury column alone would overstate the head.

### Orifice / mouthpiece

| Quantity | Formula |
| --- | --- |
| Actual discharge | `Q_act = V_collected / t` |
| Theoretical discharge | `Q_th = a √(2 g H)` |
| Coefficient of discharge | `C_d = Q_act / Q_th` |
| Coefficient of velocity | `C_v = x / √(4 y H)` |
| Coefficient of contraction | `C_c = C_d / C_v` |

`a` is the device area (⌀17 mm), `V_collected = 0.175 m² × 0.05 m`, and `(x, y)`
are the coordinates of a point on the jet trajectory. `C_v` follows from the
projectile relations `x = v t`, `y = g t²/2` with `v = C_v √(2 g H)`.

Because that implies `y = x²/(4 C_v² H)`, a straight line through the origin when
`y` is plotted against `x²`, several trajectory points can be combined into a
least-squares slope. Pass `--trajectory-file` a CSV with `x_cm,y_cm` columns:

```console
$ python -m fluid_lab orifice-mouthpiece --t-rise 18.12 --head 600 \
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

The regression value sits next to the single-point `C_v` above; a large gap
between them means one of the trajectory readings is off.

Or use `fluid_lab.orifice_mouthpiece.coefficient_of_velocity_from_trajectory`
directly.

### Sanity checks

Every result set is checked, and any problem is printed as a `!` line beneath the
table rather than raising:

- **any coefficient above 1.0** — not physically possible for a real fitting;
- **`C_d` outside the indicative range** for the device (`--device orifice`
  0.60–0.65, `--device mouthpiece` 0.80–0.86);
- **a mouthpiece whose `C_c` is far from 1.0** — the jet from a mouthpiece fills
  the outlet, so the contraction coefficient referred to the outlet is ~1;
- **efficiency above 100 %** (pump and turbine);
- **non-positive shaft torque** — `W2` exceeding `W1` plus the hanging masses
  usually means the spring balances are swapped or misread.

```console
$ python -m fluid_lab orifice-mouthpiece --device mouthpiece \
    --t-rise 18.12 --head 600 --x 47.5 --y 10
Orifice / mouthpiece test (external cylindrical mouthpiece)
===========================================================
...
! C_d = 0.62 is outside the indicative range 0.8-0.86 for the external cylindrical mouthpiece
! the jet from a mouthpiece fills the outlet, so C_c should be about 1.0, but it is 0.64
```

The indicative ranges are order-of-magnitude guidance from standard texts, not
tolerances, so they only ever produce a note.

---

## Uncertainty

`--uncertainty` propagates the reading uncertainties to every result:

```console
$ python -m fluid_lab centrifugal-pump --t-rise 12.5 --p-discharge 0.5 \
    --vacuum 120 --t-pulses 20 --uncertainty

Centrifugal pump test
=====================
Q_act actual discharge           0.002240 +/- 0.000036 m^3/s
H     total head                 7.05 +/- 0.50 m
B.P.  brake power (water power)  0.155 +/- 0.011 kW
I.P.  indicated (input) power    0.5625 +/- 0.0056 kW
eta   efficiency                 27.5 +/- 2.0 %
```

`fluid_lab.uncertainty.propagate` takes the *existing* `evaluate` function and
differentiates it by central finite differences, so a formula change cannot
silently invalidate a hand-derived sensitivity expression:

```python
from fluid_lab import CentrifugalPumpReadings, propagate
from fluid_lab.centrifugal_pump import DEFAULT_UNCERTAINTIES, evaluate

readings = CentrifugalPumpReadings(12.5, 0.5, 120.0, 20.0)
budget = propagate(evaluate, readings, DEFAULT_UNCERTAINTIES)
print(budget.standard_uncertainty["efficiency_percent"])  # 2.02195745
print(budget.dominant_source("efficiency_percent"))  # discharge_pressure_kgf_cm2
```

`dominant_source` answers "what should I improve?", which is normally the first
question asked of an error budget. The defaults in each module's
`DEFAULT_UNCERTAINTIES` are the instruments' least counts halved — replace them
with your own instrument or calibration data.

The treatment is first-order and assumes independent readings; correlated
instrument errors are not modelled.

---

## Series and CSV

A single run is one row; a series of runs is a table. Give `--series` a CSV whose
header names the readings (the same names as the flags, without `--` and with
`_`), and the results come back as a table — that is what turns a set of runs
into a characteristic curve.

```console
$ cat runs.csv
time_for_100mm_rise_s,discharge_pressure_kgf_cm2,suction_vacuum_mm_hg,time_for_10_pulses_s
12.5,0.5,120,20
10.0,0.4,100,22

$ python -m fluid_lab centrifugal-pump --series runs.csv --csv -
actual_discharge_m3_s,total_head_m,brake_power_kw,indicated_power_kw,efficiency_percent
0.00224,7.052,0.15496346879999998,0.5625,27.549061119999998
0.0027999999999999995,5.78,0.15876504,0.5113636363636364,31.0473856
```

With `--uncertainty` the CSV gains `u_<field>` columns. Omitting `--csv` prints
one formatted table per run instead.

---

## Input reference

All readings are in the units the rigs are actually graduated in; the original
scripts' mixed units are preserved deliberately so existing lab records stay
comparable.

### `centrifugal-pump`

| Flag | Quantity | Unit |
| --- | --- | --- |
| `--t-rise` | time for a 100 mm rise in the measuring tank | s |
| `--p-discharge` | delivery Bourdon gauge reading | kgf/cm² |
| `--vacuum` | suction vacuum gauge reading | mm Hg |
| `--t-pulses` | time for 10 energy-meter disc pulses | s |

### `francis-turbine`

| Flag | Quantity | Unit |
| --- | --- | --- |
| `--p-discharge` | inlet pressure gauge `P_d` | kgf/cm² |
| `--p-suction` | outlet vacuum gauge `P_s` | mm Hg |
| `--manometer` | venturimeter mercury-manometer deflection `R` | **m of mercury** |
| `--w1` | spring balance, tight side `W1` | kg |
| `--w2` | spring balance, slack side `W2` | kg |
| `--rpm` | turbine speed `N` | rev/min |
| `--datum` | gauge centre-line datum `z` (default 0) | m |

### `orifice-mouthpiece`

| Flag | Quantity | Unit |
| --- | --- | --- |
| `--device` | `orifice` (default) or `mouthpiece` | – |
| `--t-rise` | time to collect the tank volume | s |
| `--head` | constant head over the device centre | mm |
| `--x` | horizontal trajectory coordinate | cm |
| `--y` | vertical trajectory coordinate | cm |
| `--trajectory-file` | CSV of `x_cm,y_cm` points for the regression | – |

---

## Constants

Physical constants and conversion factors live in `fluid_lab/constants.py`; rig
geometry lives in the experiment module that uses it.

| Constant | Value | Meaning |
| --- | --- | --- |
| `GRAVITY_MS2` | 9.81 | acceleration due to gravity [m/s²] |
| `WATER_DENSITY_KG_M3` | 1000.0 | density of water [kg/m³] |
| `MERCURY_RELATIVE_DENSITY` | 13.6 | relative density of mercury [–] |
| `KGF_CM2_TO_M_OF_WATER` | 10.0 | 1 kgf/cm² ≡ 10 m of water |
| `CM_PER_M`, `MM_PER_M` | 100.0, 1000.0 | metre-rule conversions |

Rebuilding a rig means editing the geometry constants at the top of the relevant
module — nothing else.

---

## Numerics

Validated by capturing the original scripts' output for one input set per
experiment and pinning it in the test suite.

- **Centrifugal pump** — discharge, head and I.P. bit-for-bit identical; B.P. and
  efficiency intentionally changed (see below).
- **Orifice / mouthpiece** — identical to within one ULP. Expressing the
  collected volume as `area × rise` instead of the bare literal `0.00875` moves it
  by ~2 × 10⁻¹⁶ relative.
- **Francis turbine** — head, torque and output power unchanged apart from the
  0.015 % mercury-vacuum unification; discharge and input power intentionally
  changed (see below).

Package-level conversion inconsistencies were also unified: the turbine's vacuum
conversion used `1.033/76` where the pump used `13.6/1000`, and both are the same
physical conversion. All three experiments now share `13.6/1000`.

## Results changed in version 2.0

Two constants were dimensionally wrong and have been fixed. Any absolute figure
copied from an older version will not match.

### 1. Pump `B.P.`: `28 Q H` → `ρ g Q H`

The manual's "equivalent weight of water" of `28` has the wrong units. For `Q` in
m³/s and `H` in m the constant must be `ρg = 9.81 kN/m³` for the product to be a
power in kW. Since `28 / 9.81 = 2.854`, the old B.P. **and the old efficiency**
were inflated by that factor:

| | version 1.0 | version 2.0 |
| --- | --- | --- |
| `B.P.` | 0.44230 kW | **0.15496 kW** |
| `η` | 78.63 % | **27.55 %** |

`I.P. = 0.5625 kW` is unchanged, so the efficiency change follows entirely from the
power fix.

### 2. Turbine venturimeter head: `10.33 R` → `12.6 R`

`10.33 m` is one **atmosphere** of water, which is not what a differential
mercury manometer measures. The standard relation for water flowing through a
mercury U-tube is `h = (ρ_Hg/ρ_w − 1) R = 12.6 R`. The discharge scales as `√h`,
so `Q` rises by 10.4 % and the efficiency falls:

| | version 1.0 | version 2.0 |
| --- | --- | --- |
| `h` | 3.6155 m | **4.41 m** |
| `Q` | 0.013697 m³/s | **0.0151273 m³/s** |
| `E_i` | 0.72011 kW | **0.79542 kW** |
| `η` | 53.02 % | **48.00 %** |

`--manometer` now takes metres of mercury. If your rig reads the deflection in
millimetres or centimetres, convert before passing it.

### Also in 2.0

- Turbine head gained the optional `--datum` term (default 0, i.e. the old
  behaviour) so it can match the pump module.
- The collecting-tank volume is expressed as `area × rise`; the area is marked
  **inferred** from the old literal and should be measured.
- Uncertainty propagation, multi-point `C_v`, CSV/series I/O, orifice-vs-mouthpiece
  device handling, CI and a `LICENSE` were added.

---

## Development

```console
uv pip install -e ".[dev]"

pytest                 # unit + regression tests, plus doctests
mypy                   # strict, covers fluid_lab and tests
ruff check .           # lint
ruff format .          # format
```

CI runs all four on Python 3.12 and 3.13 for every push and pull request.

Layout:

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
tests/                      regression fixtures + unit + CLI tests
```

Each experiment module follows the same shape:

```python
readings = SomeReadings(...)  # frozen dataclass, raw observations
performance = evaluate(readings)  # frozen dataclass, computed results
print(format_report(performance))  # human-readable table
```

---

## Open questions

Real open items, not style preferences. The shipped constants now follow standard
fluid mechanics, but these still need a measurement or a manual to settle.

1. **The collecting-tank area (0.175 m²) is inferred, not measured.** It was
   back-calculated from the original script's hard-coded `0.00875 m³` per 50 mm
   rise. Measure the tank and correct `COLLECTING_TANK_AREA_M2`.
2. **`C_c` is derived, not measured.** `C_c = C_d / C_v` is an identity, so it
   carries the full error of both coefficients. It is a consistency check, not an
   independent result.
3. **The turbine hanger and rope masses (0.094 kg, 0.093 kg) are unverified**, as
   is the direction they are added (to the `W1` side). Weigh them.
4. **The pump flow measurement should be sanity-checked.** With the corrected
   constant the sample run gives `η ≈ 27.5 %`, which is low for a centrifugal
   pump. That may be honest for this rig, but it may also mean the measuring-tank
   area or the 100 mm rise is wrong — worth one independent flow measurement.
5. **Where did `10.33` come from?** If the manual really does specify it, the
   correct fix is instead the *unit* of `R`, and `MANOMETER_HEAD_FACTOR` should be
   revisited. Confirm against the manual.
6. **Fluid properties are constants.** Water and mercury densities are fixed, so
   temperature effects are ignored. Acceptable at lab accuracy, but note it.
7. **Uncertainty defaults are assumed least counts**, and the treatment is
   first-order with independent readings. Replace the defaults and check the
   independence assumption before quoting a final budget.
8. **Mouthpiece theory is only partially modelled.** The device changes the
   indicative ranges and the contraction expectation, but not the geometry
   (a mouthpiece of a different bore needs `ORIFICE_AREA_M2` changed).
9. **No LaTeX or plot export.** CSV is available; characteristic curves still need
   to be plotted externally.
10. **`--trajectory-file` applies to a single run only**, and the regression
    assumes all points were taken at the same head.

## License

MIT — see [LICENSE](LICENSE).
