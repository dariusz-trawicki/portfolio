"""True nonlinear simulation of an optimised pump schedule.

This is NOT what verify.py does.  verify.py substitutes the MILP's own values
into the exact equations and measures the residual.  This module throws the
MILP's flows and heads away, keeps only the *decisions* (the on/off vector
z[t], and the throttle setpoint), and re-solves the nonlinear network from
scratch at every sub-step, integrating the tank level forward.

That answers the operational question: run this schedule on the real network
and what actually happens to pressures, tank level and cost?

Two error sources are separated:
  * linearisation error   - PWL head-loss curves vs exact Hazen-Williams
  * time-discretisation   - the MILP holds the tank level at the value it had
                            at the START of each hour; reality moves it
                            continuously.  Run with --substeps 1 to reproduce
                            the MILP's own assumption and with 12 (5-minute
                            steps) to see the real trajectory.
"""

from __future__ import annotations

import argparse
import math
from typing import Dict, List

import numpy as np
from scipy.optimize import fsolve

import pump_scheduling as ps

HW = ps.HW_EXP
EPS = 1e-8


def flow_from_head(dh: float, R: float) -> float:
    """Invert dh = R q|q|^0.852.  Regularised near dh = 0, where dq/d(dh) -> inf."""
    a = abs(dh)
    if a < EPS:
        return 0.0
    return math.copysign((a / R) ** (1.0 / HW), dh)


def pump_flow(h_up: float, h_dn: float, pump: ps.Pump, R_link: float) -> float:
    """Solve  h_up + h_pump(q) - R q^1.852 = h_dn  for q >= 0 (bisection).

    The left side is strictly decreasing in q, so the root is unique.
    """
    def g(q):
        return h_up + pump.head(q) - R_link * q ** HW - h_dn

    lo, hi = 0.0, pump.q_max_m3h
    if g(lo) <= 0.0:
        return 0.0                       # pump cannot overcome the static head
    if g(hi) >= 0.0:
        return hi                        # would run past its max flow
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if g(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


class Simulator:
    def __init__(self, case: ps.Case):
        self.case = case
        self.pump = case.pump
        self.tank = case.tank
        self.link = case.pump.link
        self.tank_link = case.tank_link
        self.nodes = list(case.junctions)          # unknown heads
        self.R = {j: p.resistance for j, p in case.pipes.items()}

    def _head(self, node, x, y):
        c = self.case
        if node in c.fixed_heads:
            return c.fixed_heads[node]
        if node == self.tank.name:
            return self.tank.bottom_elev_m + y
        return x[self.nodes.index(node)]

    def _pipe_flow(self, j, x, y, z, theta):
        """Flow in pipe j, oriented start -> end, given the head vector."""
        p = self.case.pipes[j]
        hu = self._head(p.start, x, y)
        hd = self._head(p.end, x, y)
        if j == self.link:
            if not z:
                return 0.0
            return pump_flow(hu, hd, self.pump, self.R[j])
        if j == self.tank_link and self.tank_link != self.link and theta > 0.0:
            # altitude valve: dissipates only in the filling direction, and
            # holds shut while the driving head is inside the dead band
            dh = hu - hd
            if dh <= 0.0:
                return flow_from_head(dh, self.R[j])
            if dh <= theta:
                return 0.0
            return flow_from_head(dh - theta, self.R[j])
        return flow_from_head(hu - hd, self.R[j])

    def _residual(self, x, y, z, theta, demand):
        out = np.zeros(len(self.nodes))
        for i, n in enumerate(self.nodes):
            s = 0.0
            for j, p in self.case.pipes.items():
                if p.end == n:
                    s += self._pipe_flow(j, x, y, z, theta)
                elif p.start == n:
                    s -= self._pipe_flow(j, x, y, z, theta)
            out[i] = s - demand[n]
        return out

    def step(self, y, z, theta, demand, x0):
        x, info, ier, msg = fsolve(self._residual, x0,
                                   args=(y, z, theta, demand),
                                   full_output=True, xtol=1e-10)
        if ier != 1:
            raise RuntimeError(f"network solve failed: {msg}")
        flows = {j: self._pipe_flow(j, x, y, z, theta) for j in self.case.pipes}
        return x, flows

    def run(self, z_sched: List[int], theta_sched: List[float], substeps: int):
        c, tank = self.case, self.tank
        dt = c.dt_h / substeps
        y = tank.level_init_m
        x0 = np.array([c.junctions[n].elevation_m + 30.0 for n in self.nodes])

        rows, overflow, deficit, cost, energy = [], 0.0, 0.0, 0.0, 0.0
        worst_margin, worst_at = 1e9, None
        clamped = 0

        for t in range(c.n_periods):
            z, theta = z_sched[t], theta_sched[t]
            demand = {n: c.demand_m3h[n][t] for n in self.nodes}
            d_tank = c.demand_m3h.get(tank.name, [0.0] * c.n_periods)[t]
            q_pump_acc, y_start = 0.0, y

            for _ in range(substeps):
                x, flows = self.step(y, z, theta, demand, x0)
                x0 = x
                for n in self.nodes:
                    m = self._head(n, x, y) - c.junctions[n].min_head_m
                    if m < worst_margin:
                        worst_margin, worst_at = m, (n, t)
                net = (sum(flows[j] for j, p in c.pipes.items()
                           if p.end == tank.name)
                       - sum(flows[j] for j, p in c.pipes.items()
                             if p.start == tank.name) - d_tank)
                y += net * dt / tank.area_m2
                if y > tank.level_max_m:
                    overflow += (y - tank.level_max_m) * tank.area_m2
                    y = tank.level_max_m
                    clamped += 1
                if y < tank.level_min_m:
                    deficit += (tank.level_min_m - y) * tank.area_m2
                    y = tank.level_min_m
                    clamped += 1
                q_pump_acc += flows[self.link] * dt

            q_avg = q_pump_acc / c.dt_h
            p_kw = self.pump.power_kw(q_avg) if (z and q_avg > 1e-6) else 0.0
            energy += p_kw * c.dt_h
            cost += c.tariff[t] * p_kw * c.dt_h
            rows.append(dict(hour=t, z=z, q_pump=q_avg, power=p_kw,
                             y_start=y_start, y_end=y))

        cost += self.pump.start_cost * sum(
            1 for t in range(c.n_periods)
            if z_sched[t] and (t == 0 or z_sched[t - 1] == 0))
        return dict(rows=rows, cost=cost, energy=energy, y_end=y,
                    overflow=overflow, deficit=deficit,
                    worst_margin=worst_margin, worst_at=worst_at,
                    clamped=clamped)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--substeps", type=int, nargs="+", default=[1, 12])
    ap.add_argument("--bp-pipe", type=int, default=5)
    ap.add_argument("--solver", default="appsi_highs")
    ap.add_argument("--time-limit", type=int, default=240)
    args = ap.parse_args()

    import pyomo.environ as pyo
    case = ps.default_case()
    m = ps.build_model(case, n_bp_pipe=args.bp_pipe, sos2_mode="binary")
    ps.solve(m, solver=args.solver, mip_gap=1e-4, time_limit=args.time_limit)

    nT = case.n_periods
    z_sched = [int(round(pyo.value(m.z[t]))) for t in range(nT)]
    theta_sched = [pyo.value(m.throttle[t]) for t in range(nT)]
    model_cost = pyo.value(m.obj)
    model_energy = sum(pyo.value(m.power[t]) for t in range(nT)) * case.dt_h
    model_yend = pyo.value(m.y[nT])
    served = [n for n in case.junctions if case.junctions[n].min_pressure_m > 0]
    model_margin = min(pyo.value(m.H[n, t]) - case.junctions[n].min_head_m
                       for n in served for t in range(nT))

    print(f"\nschedule z = {''.join(map(str, z_sched))}")
    print(f"MILP says      : cost {model_cost:8.2f} {case.currency}   "
          f"energy {model_energy:7.1f} kWh   y_end {model_yend:5.3f} m   "
          f"margin {model_margin:5.2f} m")

    sim = Simulator(case)
    for ss in args.substeps:
        r = sim.run(z_sched, theta_sched, ss)
        lbl = f"sim ({ss:>2d} step{'s' if ss > 1 else ' '}/h)"
        print(f"{lbl:<15}: cost {r['cost']:8.2f} {case.currency}   "
              f"energy {r['energy']:7.1f} kWh   y_end {r['y_end']:5.3f} m   "
              f"margin {r['worst_margin']:5.2f} m"
              + (f"   at {r['worst_at']}" if r['worst_at'] else ""))
        if r["overflow"] > 1e-3:
            print(f"{'':15}  overflow {r['overflow']:.1f} m3")
        if r["deficit"] > 1e-3:
            print(f"{'':15}  TANK RAN DRY: {r['deficit']:.1f} m3 short "
                  f"({r['clamped']} clamped sub-steps)")
        if r["worst_margin"] < 0:
            print(f"{'':15}  PRESSURE VIOLATED by {-r['worst_margin']:.2f} m")


if __name__ == "__main__":
    main()
