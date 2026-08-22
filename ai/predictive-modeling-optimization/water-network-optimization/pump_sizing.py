"""How good was the hand-picked pump?

Sweeps the pump head curve  h(q) = h0 - r q^2  and re-solves the schedule for
each candidate.  This is a brute-force study, not an optimisation algorithm:
it exists to check whether the curve chosen by hand in default_case() is
actually near the best, and to show how flat or sharp the optimum is.

Only h0 and r are varied.  Efficiency (eta_bep, q_bep) is held fixed on purpose
- letting it move too would confound "the curve is better matched to the system"
with "the pump is simply a more efficient machine".
"""

from __future__ import annotations

import argparse
import dataclasses

import pyomo.environ as pyo

import pump_scheduling as ps


def evaluate(h0: float, r: float, bp: int, gap: float, tl: int):
    """Solve the schedule for one candidate curve.  Returns a result dict."""
    case = ps.default_case()
    case.pump = dataclasses.replace(case.pump, h0_m=h0, r_curve=r)

    # keep the flow window physical: the curve must still clear the highest
    # tank surface, and the efficiency parabola must stay positive
    h_needed = case.tank.bottom_elev_m + case.tank.level_max_m \
        - max(case.fixed_heads.values())
    q_ceiling = ((h0 - h_needed) / r) ** 0.5 if h0 > h_needed else 0.0
    q_max = min(case.pump.q_max_m3h, 0.98 * q_ceiling)
    if q_max <= case.pump.q_min_m3h + 1.0:
        return dict(h0=h0, r=r, status="curve too weak to reach the tank")
    case.pump = dataclasses.replace(case.pump, q_max_m3h=q_max)

    m = ps.build_model(case, n_bp_pipe=bp, sos2_mode="binary")
    res = ps.solve(m, solver="appsi_highs", mip_gap=gap, time_limit=tl)
    obj = pyo.value(m.obj, exception=False)
    if obj is None:
        return dict(h0=h0, r=r, status=str(res.solver.termination_condition))

    nT = case.n_periods
    on = [t for t in range(nT) if pyo.value(m.z[t]) > 0.5]
    thr = [pyo.value(m.throttle[t]) for t in on]
    energy = sum(pyo.value(m.power[t]) for t in range(nT)) * case.dt_h
    return dict(h0=h0, r=r, status="ok", cost=obj, energy=energy,
                q_max=q_max, run_h=len(on),
                throttle=sum(thr) / max(len(thr), 1),
                duty=sum(pyo.value(m.q[case.pump.link, t]) for t in on)
                     / max(len(on), 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bp-pipe", type=int, default=4)
    ap.add_argument("--gap", type=float, default=2e-3)
    ap.add_argument("--time-limit", type=int, default=110)
    ap.add_argument("--mode", default="h0", choices=["h0", "r"])
    args = ap.parse_args()

    base = ps.default_case().pump
    if args.mode == "h0":
        cands = [(h0, base.r_curve) for h0 in (112, 118, 121, 127, 135)]
        print(f"\nSweeping shut-off head h0 with r = {base.r_curve:g} fixed")
    else:
        cands = [(base.h0_m, r) for r in (3.5e-4, 4.5e-4, 5.5e-4, 7.0e-4, 9.0e-4)]
        print(f"\nSweeping curve steepness r with h0 = {base.h0_m:g} m fixed")

    print(f"(hand-picked: h0={base.h0_m:g} m, r={base.r_curve:g})\n")
    print(f"{'h0':>6} {'r':>9} {'q_max':>7} {'duty q':>7} {'run':>5} "
          f"{'throttle':>9} {'energy':>8} {'cost':>9}")
    print("-" * 70)
    rows = []
    for h0, r in cands:
        d = evaluate(h0, r, args.bp_pipe, args.gap, args.time_limit)
        if d["status"] != "ok":
            print(f"{h0:>6.0f} {r:>9.2e} {'':>7} {'':>7} {'':>5} {'':>9} {'':>8} "
                  f"  {d['status']}")
            continue
        rows.append(d)
        mark = "  <- hand-picked" if (abs(h0 - base.h0_m) < 1e-6
                                      and abs(r - base.r_curve) < 1e-12) else ""
        print(f"{h0:>6.0f} {r:>9.2e} {d['q_max']:>7.0f} {d['duty']:>7.1f} "
              f"{d['run_h']:>5} {d['throttle']:>8.2f}m {d['energy']:>7.0f} "
              f"{d['cost']:>8.2f}{mark}")

    if rows:
        best = min(rows, key=lambda d: d["cost"])
        hand = [d for d in rows if abs(d["h0"] - base.h0_m) < 1e-6
                and abs(d["r"] - base.r_curve) < 1e-12]
        print("-" * 70)
        print(f"best in sweep: h0={best['h0']:.0f}, r={best['r']:.2e}, "
              f"cost {best['cost']:.2f}")
        if hand:
            gap = hand[0]["cost"] - best["cost"]
            print(f"hand-picked leaves {gap:.2f} on the table "
                  f"({100 * gap / hand[0]['cost']:.2f}%)")


if __name__ == "__main__":
    main()
