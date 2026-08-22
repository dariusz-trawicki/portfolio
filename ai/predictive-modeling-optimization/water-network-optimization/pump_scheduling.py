#!/usr/bin/env python3

"""
Optimal on/off pump scheduling on a looped water network,
with SOS2 piecewise-linearised hydraulics.

Network
-------

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
               T  <- open floating tank, bottom 101 m, level 0.5-5.0 m

The pump feeds the whole network: every cubic metre delivered passes through
it.  T is an ordinary floating tank - it fills while the pump runs and supplies
B and C by gravity while it does not, so the tank level and the service-pressure
limits at B and C are directly coupled.  With A dead-ended during off hours the
loop can circulate C -> A -> B, so every network pipe is reversible and needs a
signed breakpoint grid.

Decision problem
----------------
Choose the hourly on/off state of the pump so that total electricity cost
(hourly tariff) plus start-up cost is minimal, while
  * mass is conserved at every node and in the tank,
  * head losses follow Hazen-Williams,
  * minimum service head is respected at B and C,
  * the tank stays between its level limits and ends the day no lower
    than it started,
  * pump minimum up/down times are respected.

Note that the pump *flow* is not a decision.  The head equation intersects the
pump curve with the system curve and pins the operating point; the only genuine
binary decision is the on/off state z[t].

Nonlinearity handling
---------------------
Head loss  dh(q) = R * q * |q|^0.852  and the pump head / power curves are
replaced by piecewise-linear interpolations built from SOS2 sets of convex
weights (lambda).  Two encodings are provided:
  native  - solver-level SOS2 constraints (CBC, Gurobi, CPLEX, SCIP)
  binary  - explicit interval binaries (works with any MILP solver, HiGHS)

The on/off disjunction reuses the same weights: setting sum(lambda) = z[t]
instead of 1 collapses flow, head and power to zero exactly when the pump is
off, with no big-M on the operating point.

Author: example code, MIT licence.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

import pyomo.environ as pyo

# --------------------------------------------------------------------------
# physical constants
# --------------------------------------------------------------------------
G = 9.81            # m/s^2
RHO = 1000.0        # kg/m^3
HW_EXP = 1.852      # Hazen-Williams flow exponent


# --------------------------------------------------------------------------
# network components
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Pipe:
    """A pipe oriented start -> end.  Positive flow goes start -> end."""
    name: str
    start: str
    end: str
    length_m: float
    diameter_m: float
    hw_c: float                 # Hazen-Williams roughness coefficient
    q_max_m3h: float
    allow_reverse: bool = True

    @property
    def resistance(self) -> float:
        """R in  dh[m] = R * q * |q|^(1.852-1)  with q in m3/h."""
        r_si = 10.67 * self.length_m / (self.hw_c ** HW_EXP * self.diameter_m ** 4.87)
        return r_si * (1.0 / 3600.0) ** HW_EXP     # m3/s -> m3/h

    def headloss(self, q_m3h: float) -> float:
        return math.copysign(self.resistance * abs(q_m3h) ** HW_EXP, q_m3h)


@dataclass(frozen=True)
class Pump:
    """Fixed-speed pump, installed in series on `link`.

    Head curve      h(q) = h0 - r q^2
    Efficiency      eta(q) = eta_bep * (2x - x^2),  x = q / q_bep
    Shaft power     P(q) = rho g (q/3600) h(q) / eta(q)      [kW]
    """
    name: str
    link: str
    h0_m: float
    r_curve: float
    q_min_m3h: float
    q_max_m3h: float
    q_bep_m3h: float
    eta_bep: float
    min_up_h: int = 2
    min_down_h: int = 2
    start_cost: float = 5.0
    initial_on: bool = False

    def head(self, q: float) -> float:
        return self.h0_m - self.r_curve * q * q

    def efficiency(self, q: float) -> float:
        x = q / self.q_bep_m3h
        eta = self.eta_bep * (2.0 * x - x * x)
        if eta <= 1e-3:
            raise ValueError(
                f"pump {self.name}: efficiency is non-positive at q={q:.1f} m3/h. "
                "The operating window must stay inside (0, 2*q_bep); "
                "widen q_bep or narrow [q_min, q_max].")
        return eta

    def power_kw(self, q: float) -> float:
        h = self.head(q)
        if h <= 0.0:
            raise ValueError(
                f"pump {self.name}: head curve reaches zero at q={q:.1f} m3/h. "
                "Reduce q_max or raise h0.")
        return RHO * G * (q / 3600.0) * h / (1000.0 * self.efficiency(q))


@dataclass(frozen=True)
class Tank:
    name: str
    bottom_elev_m: float
    area_m2: float
    level_min_m: float
    level_max_m: float
    level_init_m: float


@dataclass(frozen=True)
class Junction:
    name: str
    elevation_m: float
    min_pressure_m: float = 20.0

    @property
    def min_head_m(self) -> float:
        return self.elevation_m + self.min_pressure_m


@dataclass
class Case:
    name: str
    fixed_heads: Dict[str, float]          # reservoir/source nodes
    junctions: Dict[str, Junction]
    tank: Tank
    pipes: Dict[str, Pipe]
    pump: Pump
    demand_m3h: Dict[str, List[float]]      # node -> hourly demand
    tariff: List[float]                     # currency / kWh, hourly
    dt_h: float = 1.0
    currency: str = "PLN"

    @property
    def n_periods(self) -> int:
        return len(self.tariff)

    pumped_demand_nodes: List[str] = field(default_factory=list)

    @property
    def gravity_pipes(self) -> List[str]:
        return [n for n in self.pipes if n != self.pump.link]

    @property
    def tank_link(self) -> str:
        """The pipe incident to the tank (p4)."""
        for nm, p in self.pipes.items():
            if self.tank.name in (p.start, p.end):
                return nm
        raise ValueError("tank is not connected to any pipe")


# --------------------------------------------------------------------------
# default data set
# --------------------------------------------------------------------------
def _profile(base: float, shape: Sequence[float]) -> List[float]:
    return [round(base * s, 3) for s in shape]


def default_tariff() -> List[float]:
    """Three-zone tariff: night / day / evening peak."""
    out = []
    for h in range(24):
        if 22 <= h or h < 6:
            out.append(0.35)
        elif 17 <= h <= 21:
            out.append(1.10)
        else:
            out.append(0.75)
    return out


# typical diurnal pattern, two peaks (morning / evening)
DIURNAL = [0.45, 0.38, 0.34, 0.33, 0.40, 0.65, 1.10, 1.45, 1.40, 1.20, 1.10, 1.05,
           1.05, 1.00, 0.95, 1.00, 1.15, 1.45, 1.55, 1.40, 1.15, 0.95, 0.75, 0.55]


def default_case() -> Case:
    """The shipped network (see the module docstring)."""
    junctions = {
        "A": Junction("A", elevation_m=20.0, min_pressure_m=0.0),   # pump header
        "B": Junction("B", elevation_m=70.0, min_pressure_m=25.0),
        "C": Junction("C", elevation_m=72.0, min_pressure_m=25.0),
    }
    pipes = {
        "p0": Pipe("p0", "S", "A", 300.0, 0.35, 130.0, 300.0, allow_reverse=False),
        # with a floating tank every network pipe can reverse
        "p1": Pipe("p1", "A", "B", 1200.0, 0.30, 130.0, 250.0, allow_reverse=True),
        "p2": Pipe("p2", "B", "C", 800.0, 0.20, 130.0, 150.0, allow_reverse=True),
        "p3": Pipe("p3", "A", "C", 1500.0, 0.25, 130.0, 250.0, allow_reverse=True),
        "p4": Pipe("p4", "C", "T", 900.0, 0.25, 130.0, 250.0, allow_reverse=True),
    }
    # sized against the system curve: static lift 91.5-96 m (source 10 m to
    # tank surface 101.5-106 m) plus ~5 m of friction at the duty point, so the
    # curve is made to cross ~99 m at ~200 m3/h.  A steeper curve (larger r)
    # self-regulates: the operating point moves instead of the throttle opening.
    pump = Pump("P1", "p0", h0_m=121.0, r_curve=5.5e-4,
                q_min_m3h=100.0, q_max_m3h=240.0,
                q_bep_m3h=200.0, eta_bep=0.80,
                min_up_h=2, min_down_h=2, start_cost=15.0)
    tank = Tank("T", bottom_elev_m=101.0, area_m2=150.0,
                level_min_m=0.5, level_max_m=5.0, level_init_m=3.0)
    demand = {"A": [0.0] * 24,
              "B": _profile(45.0, DIURNAL),
              "C": _profile(70.0, DIURNAL),
              "T": [0.0] * 24}
    return Case(name="network", fixed_heads={"S": 10.0}, junctions=junctions,
                tank=tank, pipes=pipes, pump=pump,
                demand_m3h=demand, tariff=default_tariff(),
                pumped_demand_nodes=["A", "B", "C"])


# --------------------------------------------------------------------------
# breakpoint generation
# --------------------------------------------------------------------------
def signed_breakpoints(q_max: float, n_per_side: int, clustering: float = 1.6
                       ) -> List[float]:
    """Breakpoints on [-q_max, q_max], clustered near zero.

    dh(q) = R q|q|^0.852 has unbounded curvature at q = 0, so the grid is
    refined there:  q_k = q_max * (k/n)^clustering.
    """
    pos = [q_max * (i / n_per_side) ** clustering for i in range(1, n_per_side + 1)]
    return [-p for p in reversed(pos)] + [0.0] + pos


def positive_breakpoints(q_max: float, n: int, clustering: float = 1.6) -> List[float]:
    """Breakpoints on [0, q_max] for a pipe that cannot reverse, clustered near 0."""
    return [0.0] + [q_max * (i / n) ** clustering for i in range(1, n + 1)]


def uniform_breakpoints(q_min: float, q_max: float, n: int) -> List[float]:
    """Uniform grid on the pump operating window [q_min, q_max]."""
    return [q_min + (q_max - q_min) * i / (n - 1) for i in range(n)]


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------
def build_model(case: Case,
                n_bp_pipe: int = 7,
                n_bp_pump: int = 9,
                sos2_mode: str = "native",
                cyclic_tank: bool = True,
                big_m: float = 400.0) -> pyo.ConcreteModel:
    """Build the MILP.  sos2_mode is 'native' or 'binary'."""
    if sos2_mode not in ("native", "binary"):
        raise ValueError("sos2_mode must be 'native' or 'binary'")

    nT = case.n_periods
    dt = case.dt_h
    pump = case.pump
    tank = case.tank
    link = pump.link

    # ---- breakpoint tables -------------------------------------------------
    bp: Dict[str, List[float]] = {}
    loss: Dict[str, List[float]] = {}
    for name, pipe in case.pipes.items():
        if name == link:
            bp[name] = uniform_breakpoints(pump.q_min_m3h, pump.q_max_m3h, n_bp_pump)
        elif pipe.allow_reverse:
            bp[name] = signed_breakpoints(pipe.q_max_m3h, n_bp_pipe)
        else:
            bp[name] = positive_breakpoints(pipe.q_max_m3h, n_bp_pipe)
        loss[name] = [pipe.headloss(q) for q in bp[name]]

    pump_head = [pump.head(q) for q in bp[link]]
    pump_power = [pump.power_kw(q) for q in bp[link]]

    m = pyo.ConcreteModel(name="pump_scheduling_sos2")
    m.case = case
    m.bp, m.loss = bp, loss
    m.pump_head, m.pump_power = pump_head, pump_power

    # ---- sets --------------------------------------------------------------
    m.T = pyo.RangeSet(0, nT - 1)               # periods
    m.TB = pyo.RangeSet(0, nT)                  # tank level time boundaries
    m.J = pyo.Set(initialize=list(case.pipes), ordered=True)
    m.N = pyo.Set(initialize=list(case.junctions), ordered=True)

    lam_idx = [(j, t, k) for j in case.pipes for t in range(nT)
               for k in range(len(bp[j]))]
    m.LAM = pyo.Set(initialize=lam_idx, dimen=3, ordered=True)
    m.JT = pyo.Set(initialize=[(j, t) for j in case.pipes for t in range(nT)],
                   dimen=2, ordered=True)

    # ---- variables ---------------------------------------------------------
    m.lam = pyo.Var(m.LAM, bounds=(0.0, 1.0))
    m.q = pyo.Var(m.JT, domain=pyo.Reals)                    # m3/h
    m.dh = pyo.Var(m.JT, domain=pyo.Reals)                   # m, along orientation
    m.H = pyo.Var(m.N, m.T, domain=pyo.NonNegativeReals)     # nodal head, m
    m.y = pyo.Var(m.TB, bounds=(tank.level_min_m, tank.level_max_m))
    m.HT = pyo.Var(m.T, domain=pyo.NonNegativeReals)         # tank head, m
    m.hp = pyo.Var(m.T, domain=pyo.NonNegativeReals)         # pump head gain, m
    m.power = pyo.Var(m.T, domain=pyo.NonNegativeReals)      # kW
    m.z = pyo.Var(m.T, domain=pyo.Binary)                    # pump on
    m.su = pyo.Var(m.T, domain=pyo.Binary)                   # start-up
    m.sd = pyo.Var(m.T, domain=pyo.Binary)                   # shut-down
    m.link_slack = pyo.Var(m.T, domain=pyo.Reals)            # relaxes pump link when off
    m.spill = pyo.Var(m.T, domain=pyo.NonNegativeReals)      # tank overflow, m3/h
    tank_link = case.tank_link
    # Altitude / throttle valve at the tank inlet.
    #
    # Why it has to be here: a fixed-speed pump has ONE head curve, but the
    # tank surface is a state variable.  Nothing guarantees that the pump
    # curve meets the system curve inside the pump's flow window at every
    # combination of tank level and demand - at high demand with a low tank
    # the pump can be unable to satisfy the head equality at all, and the
    # MILP goes infeasible at a single discrete time step.  Real pumping
    # stations have an altitude or control valve at the tank inlet for
    # exactly this reason, so the model gets one too.
    #
    # It is also a diagnostic: large throttle losses mean the pump is
    # over-sized in head and the schedule is paying for head it destroys.
    # widest head difference the valve could ever have to absorb
    theta_max = (max(case.fixed_heads.values()) + pump.h0_m
                 - (tank.bottom_elev_m + tank.level_min_m))
    theta_max = max(theta_max, 1.0)
    m.theta_max = theta_max
    m.throttle = pyo.Var(m.T, bounds=(0.0, theta_max))
    m.fill = pyo.Var(m.T, domain=pyo.Binary)   # 1 <=> tank link flows into T

    for (j, t) in m.JT:
        pipe = case.pipes[j]
        lo = -pipe.q_max_m3h if (pipe.allow_reverse and j != link) else 0.0
        m.q[j, t].setlb(lo)
        m.q[j, t].setub(pipe.q_max_m3h)

    # ---- SOS2 convex-combination model -------------------------------------
    # gravity pipes: sum(lambda) = 1     (always carrying flow)
    # pump link    : sum(lambda) = z[t]  (vanishes when the pump is off)
    def _lam_sum(m, j, t):
        s = sum(m.lam[j, t, k] for k in range(len(bp[j])))
        return s == (m.z[t] if j == link else 1.0)
    m.lam_sum = pyo.Constraint(m.JT, rule=_lam_sum)

    def _q_def(m, j, t):
        return m.q[j, t] == sum(bp[j][k] * m.lam[j, t, k] for k in range(len(bp[j])))
    m.q_def = pyo.Constraint(m.JT, rule=_q_def)

    def _dh_def(m, j, t):
        return m.dh[j, t] == sum(loss[j][k] * m.lam[j, t, k]
                                 for k in range(len(bp[j])))
    m.dh_def = pyo.Constraint(m.JT, rule=_dh_def)

    def _hp_def(m, t):
        return m.hp[t] == sum(pump_head[k] * m.lam[link, t, k]
                              for k in range(len(bp[link])))
    m.hp_def = pyo.Constraint(m.T, rule=_hp_def)

    def _power_def(m, t):
        return m.power[t] == sum(pump_power[k] * m.lam[link, t, k]
                                 for k in range(len(bp[link])))
    m.power_def = pyo.Constraint(m.T, rule=_power_def)

    # adjacency: at most two consecutive lambdas may be nonzero
    if sos2_mode == "native":
        sos_index = {(j, t): [(j, t, k) for k in range(len(bp[j]))]
                     for (j, t) in m.JT}
        sos_weights = {(j, t, k): k + 1 for (j, t, k) in lam_idx}
        m.sos2 = pyo.SOSConstraint(m.JT, var=m.lam, index=sos_index,
                                   weights=sos_weights, sos=2)
    else:
        w_idx = [(j, t, i) for j in case.pipes for t in range(nT)
                 for i in range(len(bp[j]) - 1)]
        m.W = pyo.Set(initialize=w_idx, dimen=3, ordered=True)
        m.w = pyo.Var(m.W, domain=pyo.Binary)      # active interval selector

        def _w_sum(m, j, t):
            s = sum(m.w[j, t, i] for i in range(len(bp[j]) - 1))
            return s == (m.z[t] if j == link else 1.0)
        m.w_sum = pyo.Constraint(m.JT, rule=_w_sum)

        def _lam_adj(m, j, t, k):
            nb = len(bp[j])
            terms = []
            if k - 1 >= 0:
                terms.append(m.w[j, t, k - 1])
            if k <= nb - 2:
                terms.append(m.w[j, t, k])
            return m.lam[j, t, k] <= sum(terms)
        m.lam_adj = pyo.Constraint(m.LAM, rule=_lam_adj)

    # ---- nodal mass balance -------------------------------------------------
    inflow: Dict[str, List[str]] = {n: [] for n in case.junctions}
    outflow: Dict[str, List[str]] = {n: [] for n in case.junctions}
    for name, pipe in case.pipes.items():
        if pipe.end in inflow:
            inflow[pipe.end].append(name)
        if pipe.start in outflow:
            outflow[pipe.start].append(name)

    def _mass(m, n, t):
        return (sum(m.q[j, t] for j in inflow[n])
                - sum(m.q[j, t] for j in outflow[n])
                == case.demand_m3h[n][t])
    m.mass = pyo.Constraint(m.N, m.T, rule=_mass)

    # ---- head relations -----------------------------------------------------
    def head_of(m, node, t):
        if node in case.fixed_heads:
            return case.fixed_heads[node]
        if node == tank.name:
            return m.HT[t]
        return m.H[node, t]

    def _energy(m, j, t):
        if j == link:
            return pyo.Constraint.Skip
        pipe = case.pipes[j]
        lhs = head_of(m, pipe.start, t) - head_of(m, pipe.end, t)
        if j == tank_link:
            # positive flow enters the tank; throttle only dissipates then
            return lhs == m.dh[j, t] + m.throttle[t]
        return lhs == m.dh[j, t]
    m.energy = pyo.Constraint(m.JT, rule=_energy)

    qcap = case.pipes[tank_link].q_max_m3h
    m.fill_up = pyo.Constraint(
        m.T, rule=lambda m, t: m.q[tank_link, t] <= qcap * m.fill[t])
    m.fill_lo = pyo.Constraint(
        m.T, rule=lambda m, t: m.q[tank_link, t] >= -qcap * (1 - m.fill[t]))
    m.throttle_on = pyo.Constraint(
        m.T, rule=lambda m, t: m.throttle[t] <= theta_max * m.fill[t])

    # Valid inequality: with the pump off the source is disconnected, so
    # the tank is the only supply and must be draining.  Rigorous whenever
    # the network draws anything in that period, and it halves the search
    # over the fill binaries.
    def _fill_needs_pump(m, t):
        total_d = sum(case.demand_m3h[n][t] for n in case.junctions)
        if total_d <= 1e-9:
            return pyo.Constraint.Skip
        return m.fill[t] <= m.z[t]
    m.fill_needs_pump = pyo.Constraint(m.T, rule=_fill_needs_pump)



    # pump link: H_C + h_pump - dh_friction = H_T, enforced only when running.
    # When the pump is off the check valve is shut and the two sides decouple.
    pump_pipe = case.pipes[link]

    def _pump_energy(m, t):
        return (head_of(m, pump_pipe.start, t) + m.hp[t] - m.dh[link, t]
                - head_of(m, pump_pipe.end, t) == m.link_slack[t])
    m.pump_energy = pyo.Constraint(m.T, rule=_pump_energy)

    m.link_slack_up = pyo.Constraint(m.T, rule=lambda m, t: m.link_slack[t] <= big_m * (1 - m.z[t]))
    m.link_slack_lo = pyo.Constraint(m.T, rule=lambda m, t: m.link_slack[t] >= -big_m * (1 - m.z[t]))

    # ---- service pressure ---------------------------------------------------
    def _min_head(m, n, t):
        return m.H[n, t] >= case.junctions[n].min_head_m
    m.min_head = pyo.Constraint(m.N, m.T, rule=_min_head)
    h_ub = max(max(case.fixed_heads.values()) + pump.h0_m,
               tank.bottom_elev_m + tank.level_max_m) + 5.0
    for n in case.junctions:
        for t in range(nT):
            m.H[n, t].setub(h_ub)

    # ---- tank ---------------------------------------------------------------
    m.tank_head = pyo.Constraint(
        m.T, rule=lambda m, t: m.HT[t] == tank.bottom_elev_m + m.y[t])

    tank_in = [nm for nm, p in case.pipes.items() if p.end == tank.name]
    tank_out = [nm for nm, p in case.pipes.items() if p.start == tank.name]

    def _tank_balance(m, t):
        net = (sum(m.q[j, t] for j in tank_in) - sum(m.q[j, t] for j in tank_out)
               - case.demand_m3h.get(tank.name, [0.0] * nT)[t] - m.spill[t])
        return m.y[t + 1] == m.y[t] + net * dt / tank.area_m2
    m.tank_balance = pyo.Constraint(m.T, rule=_tank_balance)

    m.y[0].fix(tank.level_init_m)
    if cyclic_tank:
        m.tank_cycle = pyo.Constraint(expr=m.y[nT] >= tank.level_init_m)

    # ---- unit commitment ----------------------------------------------------
    def _uc_logic(m, t):
        z_prev = m.z[t - 1] if t > 0 else float(pump.initial_on)
        return m.su[t] - m.sd[t] == m.z[t] - z_prev
    m.uc_logic = pyo.Constraint(m.T, rule=_uc_logic)

    def _min_up(m, t):
        lo = max(0, t - pump.min_up_h + 1)
        return sum(m.su[tt] for tt in range(lo, t + 1)) <= m.z[t]
    m.min_up = pyo.Constraint(m.T, rule=_min_up)

    def _min_down(m, t):
        lo = max(0, t - pump.min_down_h + 1)
        return sum(m.sd[tt] for tt in range(lo, t + 1)) <= 1 - m.z[t]
    m.min_down = pyo.Constraint(m.T, rule=_min_down)

    # ---- valid inequality: minimum pumping volume / run time ---------------
    # Everything the tank delivers must have been pumped, plus whatever the
    # end-of-horizon level requires.  Since q4 <= q_max * z, this bounds the
    # number of on-periods from below and tightens the LP relaxation a lot.
    v_required = sum(sum(case.demand_m3h[n][t] for n in case.pumped_demand_nodes)
                     for t in range(nT)) * dt
    if not cyclic_tank:
        # without the cyclic constraint the tank may legitimately finish empty,
        # so that much of the demand need not be pumped.  Forgetting this makes
        # the inequality INVALID and silently cuts off the true optimum.
        v_required -= (tank.level_init_m - tank.level_min_m) * tank.area_m2
    v_required = max(v_required, 0.0)
    m.min_volume = pyo.Constraint(
        expr=sum(m.q[link, t] for t in range(nT)) * dt >= v_required)
    min_on = max(0, math.ceil(v_required / (pump.q_max_m3h * dt) - 1e-9))
    if min_on > 0:
        m.min_runtime = pyo.Constraint(
            expr=sum(m.z[t] for t in range(nT)) >= min_on)

    # ---- objective ----------------------------------------------------------
    m.energy_cost = pyo.Expression(
        expr=sum(case.tariff[t] * m.power[t] * dt for t in range(nT)))
    m.start_cost = pyo.Expression(
        expr=sum(pump.start_cost * m.su[t] for t in range(nT)))
    m.obj = pyo.Objective(expr=m.energy_cost + m.start_cost, sense=pyo.minimize)

    return m


# --------------------------------------------------------------------------
# solve / report
# --------------------------------------------------------------------------
def solve(m: pyo.ConcreteModel, solver: str = "cbc", tee: bool = False,
          mip_gap: float = 1e-4, time_limit: int = 300):
    opt = pyo.SolverFactory(solver)
    if solver in ("cbc",):
        opt.options["ratioGap"] = mip_gap
        opt.options["sec"] = time_limit
        opt.options["threads"] = 4
    elif solver in ("gurobi", "gurobi_direct"):
        opt.options["MIPGap"] = mip_gap
        opt.options["TimeLimit"] = time_limit
    elif solver in ("cplex",):
        opt.options["mipgap"] = mip_gap
        opt.options["timelimit"] = time_limit
    elif solver in ("appsi_highs",):
        opt.config.mip_gap = mip_gap
        opt.config.time_limit = time_limit
    res = opt.solve(m, tee=tee)
    return res


def extract(m: pyo.ConcreteModel) -> List[dict]:
    case: Case = m.case
    link = case.pump.link
    rows = []
    for t in range(case.n_periods):
        row = {
            "hour": t,
            "tariff": case.tariff[t],
            "pump_on": int(round(pyo.value(m.z[t]))),
            "q_pump_m3h": pyo.value(m.q[link, t]),
            "pump_head_m": pyo.value(m.hp[t]),
            "power_kW": pyo.value(m.power[t]),
            "energy_kWh": pyo.value(m.power[t]) * case.dt_h,
            "cost": case.tariff[t] * pyo.value(m.power[t]) * case.dt_h,
            "tank_level_m": pyo.value(m.y[t]),
            "tank_head_m": pyo.value(m.HT[t]),
        }
        for j in case.pipes:
            row[f"q_{j}_m3h"] = pyo.value(m.q[j, t])
        for n in case.junctions:
            row[f"H_{n}_m"] = pyo.value(m.H[n, t])
        for n, d in case.demand_m3h.items():
            row[f"demand_{n}_m3h"] = d[t]
        rows.append(row)
    return rows


def linearisation_error(m: pyo.ConcreteModel) -> dict:
    """Compare PWL head losses against the exact Hazen-Williams values."""
    case: Case = m.case
    worst = {"pipe": None, "hour": None, "dh_pwl": 0.0, "dh_exact": 0.0, "abs_err": 0.0}
    total = 0.0
    n = 0
    for j, pipe in case.pipes.items():
        for t in range(case.n_periods):
            q = pyo.value(m.q[j, t])
            if j == case.pump.link and pyo.value(m.z[t]) < 0.5:
                continue
            dh_pwl = pyo.value(m.dh[j, t])
            dh_exact = pipe.headloss(q)
            err = abs(dh_pwl - dh_exact)
            total += err
            n += 1
            if err > worst["abs_err"]:
                worst = {"pipe": j, "hour": t, "dh_pwl": dh_pwl,
                         "dh_exact": dh_exact, "abs_err": err}
    worst["mean_abs_err"] = total / max(n, 1)
    return worst


def report(m: pyo.ConcreteModel, rows: List[dict]) -> None:
    case: Case = m.case
    cur = case.currency
    tl = case.tank_link
    served = [n for n in case.junctions if case.junctions[n].min_pressure_m > 0]
    print()
    head = ("hour tariff  on   q_pump  h_pump  power  tank_lv  q_tank"
            + "".join(f"   H_{n}" for n in served) + "   margin")
    print(head)
    print("           [-]   [m3/h]     [m]   [kW]      [m]  [m3/h]"
          + "     [m]" * len(served) + "      [m]")
    print("-" * len(head))
    for r in rows:
        margin = min(r[f"H_{n}_m"] - case.junctions[n].min_head_m for n in served)
        print(f"{r['hour']:>4} {r['tariff']:>6.2f}  {r['pump_on']:>2} "
              f"{r['q_pump_m3h']:>8.1f} {r['pump_head_m']:>7.2f} "
              f"{r['power_kW']:>6.1f} {r['tank_level_m']:>8.3f} "
              f"{r[f'q_{tl}_m3h']:>7.1f}"
              + "".join(f" {r[f'H_{n}_m']:>7.2f}" for n in served)
              + f" {margin:>8.2f}")

    nT = case.n_periods
    energy = sum(r["energy_kWh"] for r in rows)
    e_cost = sum(r["cost"] for r in rows)
    s_cost = pyo.value(m.start_cost)
    starts = int(round(sum(pyo.value(m.su[t]) for t in range(nT))))
    run_h = sum(r["pump_on"] for r in rows) * case.dt_h
    pumped = sum(r["q_pump_m3h"] for r in rows) * case.dt_h
    demand = sum(sum(d) for d in case.demand_m3h.values()) * case.dt_h
    spilled = sum(pyo.value(m.spill[t]) for t in range(nT)) * case.dt_h
    served = [n for n in case.junctions if case.junctions[n].min_pressure_m > 0]
    worst_margin = min(r[f"H_{n}_m"] - case.junctions[n].min_head_m
                       for r in rows for n in served)

    print("-" * 104)
    print(f"pump run time            : {run_h:.1f} h  ({starts} start-ups)")
    print(f"volume pumped into network: {pumped:,.1f} m3")
    print(f"total network demand     : {demand:,.1f} m3  "
          f"({100 * pumped / max(demand, 1e-9):.0f}% through the pump)")
    print(f"tightest pressure margin : {worst_margin:.2f} m above the limit")
    if spilled > 1e-6:
        print(f"tank overflow (spill)    : {spilled:,.1f} m3")
    thr = [pyo.value(m.throttle[t]) for t in range(nT)]
    print(f"throttle valve loss      : max {max(thr):.2f} m, "
          f"mean over running hours "
          f"{sum(t_ for t_, r in zip(thr, rows) if r['pump_on']) / max(1, sum(r['pump_on'] for r in rows)):.2f} m")
    print(f"tank level  start / end  : {pyo.value(m.y[0]):.3f} m / "
          f"{pyo.value(m.y[nT]):.3f} m")
    print(f"electrical energy        : {energy:,.2f} kWh")
    if pumped > 0:
        print(f"specific energy          : {energy / pumped:.4f} kWh/m3")
    print(f"energy cost              : {e_cost:,.2f} {cur}")
    print(f"start-up cost            : {s_cost:,.2f} {cur}")
    print(f"TOTAL OBJECTIVE          : {pyo.value(m.obj):,.2f} {cur}")

    flat = sum(case.tariff) / nT
    print(f"(reference) cost of the same energy at the flat average tariff "
          f"{flat:.3f} {cur}/kWh: {energy * flat:,.2f} {cur}")

    err = linearisation_error(m)
    print()
    print("SOS2 linearisation check (PWL vs exact Hazen-Williams):")
    print(f"  mean |error| over active links : {err['mean_abs_err']:.4f} m")
    print(f"  worst link                     : {err['pipe']} at hour {err['hour']}"
          f"  PWL {err['dh_pwl']:.4f} m vs exact {err['dh_exact']:.4f} m"
          f"  (|err| = {err['abs_err']:.4f} m)")


def write_csv(rows: List[dict], path: str) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nresults written to {path}")


def make_plot(m: pyo.ConcreteModel, rows: List[dict], path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    case: Case = m.case
    hours = [r["hour"] for r in rows]
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)

    ax[0].step(hours, [r["tariff"] for r in rows], where="mid", color="tab:red")
    ax[0].set_ylabel(f"tariff [{case.currency}/kWh]")
    ax[0].grid(alpha=.3)

    ax[1].bar(hours, [r["q_pump_m3h"] for r in rows], color="tab:blue", width=.8)
    ax[1].set_ylabel("pump flow [m3/h]")
    ax[1].grid(alpha=.3)

    ax[2].plot(hours + [case.n_periods],
               [pyo.value(m.y[t]) for t in range(case.n_periods + 1)],
               marker="o", color="tab:green")
    ax[2].axhline(case.tank.level_min_m, ls="--", c="grey")
    ax[2].axhline(case.tank.level_max_m, ls="--", c="grey")
    ax[2].set_ylabel("tank level [m]")
    ax[2].set_xlabel("hour")
    ax[2].grid(alpha=.3)

    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print(f"plot written to {path}")


# --------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--solver", default="cbc",
                   help="cbc | appsi_highs | gurobi | cplex | scip")
    p.add_argument("--sos2", default="native", choices=["native", "binary"],
                   help="native SOS2 constraints or explicit binary encoding "
                        "(use 'binary' with solvers lacking SOS2, e.g. HiGHS)")
    p.add_argument("--bp-pipe", type=int, default=7,
                   help="breakpoints per side for gravity pipes (default 7 -> 15)")
    p.add_argument("--bp-pump", type=int, default=9,
                   help="breakpoints on the pump operating window")
    p.add_argument("--gap", type=float, default=1e-4, help="relative MIP gap")
    p.add_argument("--time-limit", type=int, default=300, help="seconds")
    p.add_argument("--no-cycle", action="store_true",
                   help="drop the end-of-horizon tank level constraint")
    p.add_argument("--csv", metavar="PATH", help="write hourly results to CSV")
    p.add_argument("--plot", metavar="PATH", help="write a PNG summary plot")
    p.add_argument("--tee", action="store_true", help="show solver log")
    args = p.parse_args()

    case = default_case()

    print(f"Layout '{case.name}':  fixed heads " +
          ", ".join(f"{k}={v:.1f} m" for k, v in case.fixed_heads.items()) +
          f";  tank {case.tank.name} bottom {case.tank.bottom_elev_m:.1f} m, "
          f"level {case.tank.level_min_m:.1f}-{case.tank.level_max_m:.1f} m, "
          f"A={case.tank.area_m2:.0f} m2")
    print("Pipe data (Hazen-Williams):")
    for name, pipe in case.pipes.items():
        print(f"  {name}: {pipe.start}->{pipe.end}  L={pipe.length_m:6.0f} m  "
              f"D={pipe.diameter_m:.2f} m  C={pipe.hw_c:.0f}  "
              f"R={pipe.resistance:.6e}  "
              f"dh({pipe.q_max_m3h:.0f} m3/h)={pipe.headloss(pipe.q_max_m3h):.2f} m")
    pu = case.pump
    print(f"Pump {pu.name} on {pu.link}: h(q)={pu.h0_m:.1f}-{pu.r_curve:g}q^2, "
          f"q in [{pu.q_min_m3h:.0f},{pu.q_max_m3h:.0f}] m3/h, "
          f"BEP {pu.q_bep_m3h:.0f} m3/h @ eta={pu.eta_bep:.2f}, "
          f"min up/down {pu.min_up_h}/{pu.min_down_h} h")

    m = build_model(case, n_bp_pipe=args.bp_pipe, n_bp_pump=args.bp_pump,
                    sos2_mode=args.sos2, cyclic_tank=not args.no_cycle)

    n_bin = sum(1 for v in m.component_data_objects(pyo.Var)
                if v.domain is pyo.Binary)
    n_var = sum(1 for _ in m.component_data_objects(pyo.Var))
    n_con = sum(1 for _ in m.component_data_objects(pyo.Constraint))
    print(f"\nMILP: {n_var} variables ({n_bin} binary), {n_con} constraints, "
          f"SOS2 mode = {args.sos2}")

    res = solve(m, solver=args.solver, tee=args.tee,
                mip_gap=args.gap, time_limit=args.time_limit)
    status = res.solver.termination_condition
    print(f"solver status: {status}")
    if pyo.value(m.obj, exception=False) is None:
        raise SystemExit("no usable solution found")
    if status is not pyo.TerminationCondition.optimal:
        print("WARNING: solution is an incumbent, not a proven optimum "
              "(time limit / gap reached)")

    rows = extract(m)
    report(m, rows)
    if args.csv:
        write_csv(rows, args.csv)
    if args.plot:
        make_plot(m, rows, args.plot)


if __name__ == "__main__":
    main()
