# Pump scheduling on a looped water network — SOS2 linearisation + MILP

Least-cost on/off scheduling of a fixed-speed pump, on a looped distribution
network with an elevated storage tank. All hydraulic nonlinearities (head loss,
pump head curve, pump power curve) are replaced by
[piecewise-linear interpolations](piecewise-linearisation-demo) built from
**SOS2** sets of convex weights, so the whole problem is a single MILP.

---

## 1. The network

```
    S            low-level source / intake, fixed head 10 m
    |
    p0 + PUMP    pump station (fixed speed, on/off)
    |
    A            discharge header (junction, no demand)
   / \
  p1   p3
  /      \
 B --p2-- C      demand nodes, elevation 70 / 72 m, min pressure 25 m
           \
            p4 + throttle valve
              \
               T   floating tank, bottom 101 m, level 0.5-5.0 m, 150 m2
```

The pump feeds the **whole** network — every cubic metre delivered passes
through it. T is an ordinary floating tank: it fills while the pump runs and
supplies B and C by gravity while it does not, so the tank level and the
service-pressure limits are directly coupled. Drain the tank too far and C
drops below its 25 m minimum.

With A dead-ended during off hours the loop can circulate `C → A → B`, so
**every network pipe is reversible** and needs a signed breakpoint grid. That
is the main reason the MILP is as large as it is.

## 2. Model formulation

Index `t = 0…23` (hourly periods, `Δt = 1 h`), `j` over pipes, `k` over
breakpoints.

### 2.1 Mass balance

At each junction `n`:

```
Σ_{j into n} q[j,t]  −  Σ_{j out of n} q[j,t]  =  d[n,t]
```

Tank (open, constant cross-section `A_T`, `spill ≥ 0` is the overflow of §2.5):

```
y[t+1] = y[t] + ( q_p4[t] − spill[t] ) · Δt / A_T
y_min ≤ y[t] ≤ y_max
y[0] = y[24] = y_init = 2.75 m      (midpoint of the usable 0.5–5.0 m range)
```

The day closes on **exactly** the level it opened on, so consecutive days chain
without drift. Without that constraint the optimiser simply drains the tank and
pumps less than the network consumes. `--no-cycle` relaxes it, but see the
caveat in §2.8.

### 2.2 Energy / head relations

Nodal-head formulation, which enforces loop energy balance automatically
(`Δh_p1 + Δh_p2 = Δh_p3` follows from the p1/p2/p3 head equations, so no
explicit loop equations are needed):

```
H[start(j),t] − H[end(j),t] = Δh[j,t]              for p1, p2, p3
H[C,t] − H[T,t] = Δh[p4,t] + θ[t]                  for the tank link p4
H[S] + h_pump[t] − Δh[p0,t] − H[A,t] = s[t]        for the pump link p0
H[T,t] = 101 m + y[t]                              tank bottom + level
H[S] = 10 m                                        fixed-head source
H[n,t] ≥ elevation[n] + p_min[n]                   n in {A, B, C}
```

The pump sits on `p0`, between the source `S` and the header `A`, so its head
gain enters that equation and **not** the tank link. `s[t]` is the slack that
releases the equation when the pump is off and its check valve shuts (§2.4);
`θ[t]` is the throttle valve at the tank inlet (§2.5).

Head loss is Hazen-Williams, with `q` in m³/h:

```
Δh(q) = R · q · |q|^0.852,    R = 10.67 · L / (C^1.852 · D^4.87) · (1/3600)^1.852
```

### 2.3 SOS2 piecewise linearisation

For every link `j` and period `t`, with breakpoints `Q[j,k]` and tabulated
values `Φ[j,k] = Δh(Q[j,k])`:

```
q[j,t]  = Σ_k Q[j,k] · λ[j,t,k]
Δh[j,t] = Σ_k Φ[j,k] · λ[j,t,k]
Σ_k λ[j,t,k] = 1            (all links except the pump link, see §2.4)
λ[j,t,·] is SOS2            (at most two adjacent weights nonzero)
```

Because `Δh(q) = R q|q|^0.852` is **nonconvex** (convex for `q > 0`, concave for
`q < 0`) and appears in an **equality**, a convex-combination model alone is not
enough — the SOS2 adjacency condition is what forces the weights onto a single
segment of the curve. That is the whole reason SOS2 is the right tool here.

Breakpoint placement is not uniform. The second derivative of `q|q|^0.852`
blows up at `q = 0`, so the grid is refined there:
`Q_k = q_max · (k/n)^1.6`.

#### Demo

- [Piecewise linearization demo](piecewise-linearisation-demo/)

### 2.4 The pump, and the on/off trick

The same λ-set carries four quantities for the pump link `p0`:

```
q_p0[t]   = Σ_k Q_k λ[k]          flow
Δh_p0[t]  = Σ_k Φ_k λ[k]          pipe friction on p0
h_pump[t] = Σ_k h(Q_k) λ[k]       pump head,  h(q) = h0 − r q²
P[t]      = Σ_k P(Q_k) λ[k]       shaft power, P = ρ g q h(q) / η(q)
```

with the efficiency curve `η(q) = η_bep · (2x − x²)`, `x = q/q_bep`.

The on/off disjunction is expressed by changing one right-hand side:

```
Σ_k λ[p0,t,k] = z[t]        instead of  = 1
```

When `z[t] = 0` every weight is zero, so flow, pump head and power all collapse
to zero exactly — no big-M needed for the operating point. Because the
breakpoint grid starts at `q_min` (not at 0), the pump's minimum-flow limit is
enforced for free whenever `z[t] = 1`.

One big-M is still needed, on the pump-link *head* equation. When the pump is
off its check valve shuts and the two sides of `p0` decouple, so the equation
must be released:

```
−M(1 − z[t]) ≤ s[t] ≤ M(1 − z[t])
```

**Note on what is and is not a decision.** The pump flow is *not* free. Given
the demands and the tank level, the head equation
`H_S + h(q) − Δh_p0(q) = H_A` intersects the pump curve with the system curve
and pins `q` to a single value. The only real binary decision is `z[t]`; the
model reports the resulting operating point (in the shipped case ~167–212 m³/h,
falling as the tank fills and the discharge head rises). This is the behaviour
you want from an on/off model, and it is why the pump curve has to be in the
model at all rather than assuming a fixed flow rate.

### 2.5 The floating tank and the throttle valve

Because the tank hangs off the network rather than sitting behind the pump, two
extra pieces are needed.

**Throttle / altitude valve — why it is there.** This was not in the model
originally; it was added because without it the MILP came back *infeasible*,
and the reason turned out to be physical rather than a coding mistake.

A fixed-speed pump has exactly one head curve. The tank surface, however, is a
state variable that moves between 101.5 m and 106 m, and network friction moves
with demand between 52 and 178 m³/h. The operating point is wherever the pump
curve meets the system curve — but nothing guarantees that intersection lies
inside the pump's flow window `[q_min, q_max]` for every combination of level
and demand. The failing case is a **high tank with low demand**: the pump at its
minimum flow of 100 m³/h still produces about 115 m of head, which puts C far
above the tank surface, and the head equality `H_C − H_T = Δh_p4(q_p4)` would
demand a filling flow larger than the pump is delivering. No feasible point
exists, and the MILP reports infeasible at a single discrete time step.

Real pumping stations solve this with an altitude or control valve at the tank
inlet, which throttles to absorb the surplus head. So the model gets one:

```
H_C − H_T = Δh_p4(q_p4) + θ[t],     0 ≤ θ[t] ≤ θ_max · fill[t]
q_p4[t] ≤ q_max · fill[t],          q_p4[t] ≥ −q_max · (1 − fill[t])
```

`fill[t]` is a direction binary; θ may only dissipate in the filling direction,
because allowing it while the tank drains would let the model deliver flow with
less head than physics permits and would *understate* pressure at B and C.

**It is also a diagnostic, and that is arguably its more useful role.** θ is
head the station generates and then destroys, so it is wasted energy. The first
pump fitted to this network (h₀ = 135 m, r = 4.5e-4) ran with a mean θ of
**18.6 m** — a clear signal that it was over-sized in head. Re-fitting the curve
against the actual system curve (static lift 91.5–96 m plus ~5 m friction at the
duty point, so the curve should cross ~99 m at ~200 m³/h) gave h₀ = 121 m,
r = 5.5e-4, which cut θ to about **1 m** and saved **17% of the energy**
(1064 → 882 kWh/day) before any scheduling optimisation at all. A steep curve
self-regulates: the operating point moves instead of the valve opening.

Watch the `throttle valve loss` line in the output. If the mean is more than a
metre or two, fix the pump selection before reading anything into the schedule.

**Overflow.** A `spill[t] ≥ 0` term in the tank balance keeps the model feasible
if the tank would be driven over `y_max`. Spilling is never profitable (the
water was pumped at a cost), so the optimiser avoids it unprompted.

### 2.6 Commitment constraints

```
su[t] − sd[t] = z[t] − z[t−1]
Σ_{τ=t−T_up+1}^{t} su[τ] ≤ z[t]
Σ_{τ=t−T_dn+1}^{t} sd[τ] ≤ 1 − z[t]
```

### 2.7 Objective

```
min  Σ_t  c[t] · P[t] · Δt   +   c_start · Σ_t su[t]
```

with `c[t]` a three-zone tariff (night 0.35, day 0.75, evening peak 1.10) and
`c_start` = 15 PLN per start.

### 2.8 Valid inequalities

The source is the only supply, so everything the network consumes must have
been pumped, and `q_p0 ≤ q_max·z` gives a lower bound on run time:

```
Σ_t q_p0[t]·Δt ≥ V_required
Σ_t z[t]       ≥ ⌈V_required / (q_max·Δt)⌉
```

A second one: with the pump off the source is disconnected, so the tank is the
only supply and must be draining —

```
fill[t] ≤ z[t]        (whenever the network draws anything in period t)
```

Both tighten the LP relaxation and cut solve time.

**Caveat, and it bit this code once.** `V_required` equals the demand only when
the tank is cyclic. Under `--no-cycle` the tank may legitimately finish empty,
so the requirement drops by `(y_init − y_min)·A_T`; omitting that term makes the
inequality *invalid* and silently returns a worse schedule — on an earlier
variant of this case, 73.18 PLN instead of the true 63.06 PLN, a 14% error with
no warning and the solver still reporting "optimal". `verify.py` catches this
class of mistake by re-solving with the cut deactivated and comparing.

## 3. Installation

The project uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

That reads `pyproject.toml` and pins Pyomo, HiGHS, NumPy, SciPy and Matplotlib
into a local `.venv`. Python 3.10 or newer.

Optional, only if you want solver-level SOS2 (see §4):

```bash
sudo apt-get install coinor-cbc
```

## 4. Usage

```bash
# recommended: HiGHS with the explicit binary SOS2 encoding
uv run pump_scheduling.py --solver appsi_highs --sos2 binary --bp-pipe 5

# solver-level SOS2 constraints (CBC, Gurobi, CPLEX, SCIP)
uv run pump_scheduling.py --solver cbc --sos2 native --time-limit 300

# export, and the like-for-like saving figure
uv run pump_scheduling.py --solver appsi_highs --sos2 binary \
       --csv schedule.csv --plot schedule.png --benchmark
```

| flag | meaning |
|---|---|
| `--solver` | `cbc`, `appsi_highs`, `gurobi`, `cplex`, `scip` |
| `--sos2` | `native` (solver SOS2) or `binary` (interval binaries) |
| `--bp-pipe` | breakpoints per side for reversible pipes (default 7) |
| `--bp-pump` | breakpoints across the pump operating window (default 9) |
| `--gap` | relative MIP gap (default 1e-4) |
| `--time-limit` | seconds |
| `--no-cycle` | drop the end-of-day tank level constraint |
| `--benchmark` | also solve a tariff-blind variant, priced at the real tariff |
| `--csv`, `--plot` | write results |
| `--tee` | show the solver log |

### Which SOS2 encoding

`native` produces a far smaller model (96 binaries vs 1248) because the
branching happens inside the solver, but it needs a solver with real SOS2
support, and CBC in particular branches on SOS2 poorly here — it did not close
the gap in 300 s. `binary` writes the adjacency condition out explicitly:

```
Σ_i w[j,t,i] = 1 (or z[t]),      λ[k] ≤ w[k−1] + w[k]
```

which is bigger but works with any MILP solver and, with HiGHS, proves
optimality in a couple of minutes. Use `native` if you have Gurobi or CPLEX.

## 5. Reference result

Produced by `uv run pump_scheduling.py --solver appsi_highs --sos2 binary
--bp-pipe 5`.

![Results](schedule.png)

```
hour tariff  on   q_pump  h_pump  power  tank_lv  q_tank   H_B     H_C   margin
           [-]   [m3/h]     [m]   [kW]      [m]  [m3/h]     [m]     [m]      [m]
-----------------------------------------------------------------------------
   0   0.35   0     -0.0    0.00    0.0    2.750   -51.8  103.28  103.34     6.34
   1   0.35   0     -0.0    0.00    0.0    2.405   -43.7  103.03  103.08     6.08
   2   0.35   0     -0.0    0.00    0.0    2.114   -39.1  102.79  102.84     5.84
   3   0.35   1    199.6   99.06   67.4    1.853   161.6  108.14  106.11     9.11
   4   0.35   1    196.8   99.65   66.9    2.930   150.8  108.73  106.83     9.83
   5   0.35   1    197.4   99.53   67.0    3.936   122.6  108.53  106.91     9.91
   6   0.75   0      0.0    0.00    0.0    4.754  -126.5  103.36  103.65     6.65
   7   0.75   0     -0.0    0.00    0.0    3.910  -166.8  101.04  101.49     4.49
   8   0.75   0     -0.0    0.00    0.0    2.799  -161.0  100.14  100.57     3.57
   9   0.75   0      0.0    0.00    0.0    1.725  -138.0   99.91  100.25     3.25
  10   0.75   1    209.9   96.74   69.4    0.805    83.4  105.54  104.14     7.14
  11   0.75   1    212.1   96.22   69.8    1.361    91.4  105.02  103.54     6.54
  12   0.75   1    209.9   96.73   69.4    1.970    89.2  105.55  104.10     7.10
  13   0.75   1    207.2   97.36   68.9    2.565    92.2  106.21  104.76     7.76
  14   0.75   1    204.4   98.01   68.3    3.180    95.2  106.89  105.44     8.44
  15   0.75   1    202.6   98.41   68.0    3.814    87.6  107.29  105.91     8.91
  16   0.75   1    202.1   98.51   67.9    4.398    69.9  107.36  106.13     9.13
  17   1.10   0      0.0    0.00    0.0    4.864  -166.8  101.99  102.44     5.44
  18   1.10   0      0.0    0.00    0.0    3.752  -178.2  100.41  100.91     3.91
  19   1.10   0      0.0    0.00    0.0    2.564  -161.0   99.90  100.33     3.33
  20   1.10   0      0.0    0.00    0.0    1.491  -132.2   99.89  100.20     3.20
  21   1.10   1    167.0  105.64   61.8    0.609    57.7  114.81  113.92    16.92
  22   0.35   1    209.5   96.83   69.3    0.994   123.2  105.73  103.99     6.99
  23   0.35   1    203.4   98.22   68.1    1.815   140.2  107.22  105.37     8.37
--------------------------------------------------------------------------------------------------------
pump run time            : 13.0 h  (3 start-ups)
--------------------------------------------------------------------------------
pump run time             : 13.0 h  (3 start-ups)
volume pumped into network: 2,622.0 m3   (100% of demand)
tightest pressure margin  : 3.20 m above the limit
throttle valve loss       : max 11.84 m, mean over running hours 1.01 m
tank level  start / end   : 2.750 m / 2.750 m
electrical energy         : 882.13 kWh   (0.3364 kWh/m3)
energy cost               : 547.74 PLN
start-up cost             : 45.00 PLN
TOTAL OBJECTIVE           : 592.74 PLN
  (the same 882 kWh at the flat average tariff 0.690 PLN/kWh would cost
   608.30 PLN in energy -> tariff arbitrage is worth 60.56 PLN.)
```

Things worth reading off this:

* The pump charges the tank to 4.86 m by 17:00 and rides out most of the 1.10
  evening block — but it **cannot skip it entirely**. By 21:00 the tank is at
  0.609 m against a 0.5 m floor, so it is forced to start at peak tariff.
  Storage, not tariff, is the binding resource.
* At 20:00 the pressure margin falls to 3.20 m. The tank cannot be drawn lower
  without violating the 25 m service pressure at C — the level bound and the
  pressure bound become active at nearly the same moment.
* Flow reverses in p4 every cycle (+162 m³/h filling, −178 m³/h supplying),
  which is exactly why that link needs a **signed** breakpoint grid.
* Hour 21 is the odd one out: the pump runs at 167 m³/h instead of ~205, because
  the tank is nearly empty and the discharge head is low, so the operating point
  slides up the curve. Nobody chose that flow — the hydraulics did.

## 6. Linearisation accuracy

Every run ends with a check that recomputes exact Hazen-Williams losses from the
optimised flows and compares them against the PWL values. Accuracy vs cost
(HiGHS, `--sos2 binary`, on this network):

| `--bp-pipe` | binaries | mean err | worst err | wall time | objective |
|---|---|---|---|---|---|
| 4 | 1056 | 0.070 m | 0.219 m | 90 s | 593.03 |
| 5 | 1248 | 0.037 m | 0.117 m | 139 s | 592.74 |

The objective barely moves between the two, so for cost the coarse grid is
already adequate. **Do not conclude the same about pressure** — see §8, where a
0.117 m residual turns into a 0.89 m error in the reported margin.

## 7. Verifying the code

`verify.py` audits a solved model **without reusing any of its constraints**: it
pulls the raw variable values out and re-derives the physics from the `Case`
data. It checks nodal and tank mass balance, the global volume balance, the head
balance against *exact* Hazen-Williams (not the PWL approximation), all bounds,
minimum up/down times, and recomputes the objective from the exact pump curves.

```bash
uv run verify.py
uv run verify.py --no-cycle
```

Typical output:

```
=== audit ===
    nodal mass balance     max residual 1.14e-13 m3/h
    tank balance           max residual 2.02e-14 m
    global volume balance  in 2622.0 = out 2622.0 + stored 0.0 + spill 0.0
    exact head balance     max residual 0.117 m at ('p3', 21)
    on/off runs            offx3, onx3, offx4, onx7, offx4, onx3
    objective              model 592.74 vs recomputed from exact curves (-0.03%)
    all checks passed
```

Mass balances close to machine precision, so the network assembly is right. The
head-balance residual is the linearisation error and nothing else. The objective
recomputed from the exact curves lands within 0.03% of the model's, which is the
useful statement: **the schedule is worth what the model says it is**, even
though the flows it was derived from are approximate.

## 8. `verify.py` vs `simulate.py` — residual check vs real simulation

These answer different questions and it is worth not confusing them.

**`verify.py` does not solve the nonlinear system.** It substitutes the MILP's
own `q`, `H`, `y` into the exact equations and measures the residual. It tells
you whether the model's numbers are self-consistent — which catches sign errors,
missing terms and wrong topology — but it cannot tell you what happens when you
actually run the schedule.

**`simulate.py` throws the MILP's flows and heads away.** It keeps only the
*decisions* (the on/off vector `z[t]` and the throttle setpoint), then re-solves
the nonlinear network with `fsolve` at every sub-step and integrates the tank
level forward. Pipe flows come from inverting `Δh = R q|q|^0.852`; the pump flow
is found by bisecting `H_up + h(q) − R q^1.852 = H_dn`, which is strictly
decreasing in `q` and so has a unique root.

```bash
uv run simulate.py --substeps 1 12 60
```

```
schedule z = 000111000011111110000111
MILP says       : cost 592.74 PLN  energy 882.1 kWh  y_end 2.750 m  margin 3.20 m
sim ( 1 step /h): cost 593.26 PLN  energy 883.0 kWh  y_end 2.793 m  margin 3.33 m
sim (12 steps/h): cost 591.91 PLN  energy 880.5 kWh  y_end 2.706 m  margin 2.38 m
sim (60 steps/h): cost 591.81 PLN  energy 880.3 kWh  y_end 2.700 m  margin 2.31 m
```

Running at `--substeps 1` reproduces the MILP's own assumption (tank level held
at its start-of-hour value), so the difference between that row and the MILP is
pure **linearisation** error. The difference between `1` and `60` is pure
**time-discretisation** error. Separating them matters, because they do not
affect the two outputs equally:

* **Cost is reliable.** 591.81 vs 592.74 PLN, an error of 0.16%.
* **The pressure margin is not.** The model reports 3.20 m; the true value is
  **2.31 m**, so the model is optimistic by 0.89 m — about 28% of the margin,
  and roughly 8× the 0.117 m head-loss residual that `verify.py` reports.

That last point corrects something the residual check appears to say. A 0.117 m
residual looks negligible against a 3.20 m margin, and it is tempting to
conclude the schedule has plenty of room. It does not: errors compound through
the tank trajectory, because a slightly wrong flow gives a slightly wrong level,
which shifts the head at C for every subsequent hour. **Do not size pressure
margins from the residual — simulate.** The values converge by roughly 12
sub-steps per hour, so 5-minute steps are enough to trust.

## 9. What is worth optimising

The shipped pump was chosen **by hand**, not optimised. `pump_sizing.py` checks
that hand-sizing by sweeping the head curve and re-solving the whole schedule
for each candidate:

```bash
uv run pump_sizing.py --mode h0     # sweep shut-off head, r fixed
uv run pump_sizing.py --mode r      # sweep curve steepness, h0 fixed
```

```
 h0 [m]  throttle   energy      cost
    112     0.98m      898    644.86
    118     1.92m      886    623.88
    121     0.78m      881    593.93   <- hand-picked
    127     1.37m      911    622.64
    135     9.25m      990    664.04
```

The hand-picked curve happens to come out best here, but read that as a coarse
grid confirming a back-of-envelope calculation, not as evidence of an optimum —
the spacing is 6–8 m and nothing was searched between the points.

Two things matter more than the winner:

* **Pump selection is at least as big a lever as scheduling.** The spread across
  the sweep is 70 PLN/day; tariff arbitrage against the flat average is worth
  61 PLN/day. Comparable, and both worth doing — but a badly chosen pump cannot
  be scheduled out of trouble.
* **Throttle loss alone is not a sufficient criterion.** The 112 m candidate
  runs at a lower mean throttle (0.98 m) than the 127 m one (1.37 m) yet costs
  22 PLN/day more, because it is too weak to reach a useful duty flow and has to
  run 16 h instead of 12. θ diagnoses over-sizing in head; it says nothing about
  under-sizing.

What this is **not**: a pump selection method. It varies two coefficients of an
idealised parabola, on one day's demand profile, with efficiency held fixed.
Real selection means discrete catalogue curves, NPSH margins, motor frames,
several demand scenarios (summer/winter, fire flow, pipe ageing) and capital
cost. The curve here is fitted to a single profile and would be over-fitted to
it if anyone treated the result as a recommendation.

## 10. Limitations and honest caveats

* **The MILP solves linearised hydraulics, not exact hydraulics.** Use
  `simulate.py` (§8) or EPANET before trusting a schedule operationally. As §8
  shows, that verification is not a formality: it moved the pressure margin by
  28%.
* **Deterministic demand.** No forecast error. A rolling-horizon re-solve every
  hour with updated forecasts and the measured tank level is the usual fix, and
  the model is already set up for it — change `level_init_m` and the
  tariff/demand vectors and re-solve.
* **One pump, fixed speed.** Multiple parallel pumps need a λ-set per unit plus
  a shared discharge head; variable speed needs a second continuous dimension
  (affinity laws) and hence a 2-D PWL, where SOS2 no longer suffices — use a
  triangulated model instead.
* **Big-M on the pump-link head equation** is set to 400 m. Loose but safe for
  this head range; tighten it if you enlarge the network, since a loose big-M
  weakens the relaxation.
* **Water quality, minimum tank turnover and leakage are not modelled.**
  Cost-optimal schedules tend to stratify tanks; a minimum-turnover constraint
  is usually added in practice.
* **The throttle valve is an escape hatch as well as a physical component.** If
  reported throttle losses are large, treat it as a sizing warning rather than a
  result: the schedule is then paying for head it immediately destroys.
* **The tank head equation uses the level at the *start* of each interval.** For
  long steps this is a real approximation and is part of why the throttle is
  necessary. Using the mid-interval level `(y[t]+y[t+1])/2` is a common
  alternative; it is smoother but couples consecutive periods more tightly.

## 11. Adapting to your own data

Everything lives in `default_case()`:

* `Pipe(name, start, end, length_m, diameter_m, hw_c, q_max_m3h, allow_reverse)`
  — `q_max_m3h` also sets the breakpoint span, so keep it realistic; an
  oversized range wastes resolution.
* `Pump(h0_m, r_curve, q_min, q_max, q_bep, eta_bep, min_up_h, min_down_h,
  start_cost, initial_on)` — fit `h0` and `r_curve` to your manufacturer curve
  by least squares on `h = h0 − r q²`.
* `Tank(bottom_elev_m, area_m2, level_min_m, level_max_m, level_init_m)`.
* `demand_m3h` — one list per node, any horizon length; `tariff` sets the number
  of periods, so the two must match.
* Sub-hourly resolution: set `dt_h=0.25` and supply 96-element profiles.

Adding a node or pipe requires no code changes beyond the dictionaries — mass
balance, head equations and breakpoint grids are all built from them.

An EPANET export of this network and schedule is in `network.inp`.

---

MIT licence. Example code, not production software.
