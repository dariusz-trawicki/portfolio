"""Independent audit of a solved model.

Deliberately does NOT reuse the model's constraints: it pulls out the raw
variable values and re-derives every physical relation from the Case data.
If build_model has a sign error or a missing term, this should catch it.
"""
import sys
import pyomo.environ as pyo
import pump_scheduling as ps


def audit(case, m, tol_mass=1e-4, tol_head=0.25):
    nT, dt = case.n_periods, case.dt_h
    link, tl = case.pump.link, case.tank_link
    tank = case.tank
    fails, notes = [], []

    q = {(j, t): pyo.value(m.q[j, t]) for j in case.pipes for t in range(nT)}
    z = {t: round(pyo.value(m.z[t])) for t in range(nT)}
    y = {t: pyo.value(m.y[t]) for t in range(nT + 1)}
    spill = {t: pyo.value(m.spill[t]) for t in range(nT)}
    thr = ({t: pyo.value(m.throttle[t]) for t in range(nT)}
           if hasattr(m, "throttle") else {t: 0.0 for t in range(nT)})

    def head(n, t):
        if n in case.fixed_heads:
            return case.fixed_heads[n]
        if n == tank.name:
            return tank.bottom_elev_m + y[t]
        return pyo.value(m.H[n, t])

    # 1. nodal mass balance -------------------------------------------------
    worst = 0.0
    for n in case.junctions:
        for t in range(nT):
            inflow = sum(q[j, t] for j, p in case.pipes.items() if p.end == n)
            outflow = sum(q[j, t] for j, p in case.pipes.items() if p.start == n)
            r = inflow - outflow - case.demand_m3h[n][t]
            worst = max(worst, abs(r))
    if worst > tol_mass:
        fails.append(f"nodal mass balance residual {worst:.2e} m3/h")
    notes.append(f"nodal mass balance     max residual {worst:.2e} m3/h")

    # 2. tank balance -------------------------------------------------------
    worst = 0.0
    for t in range(nT):
        net = (sum(q[j, t] for j, p in case.pipes.items() if p.end == tank.name)
               - sum(q[j, t] for j, p in case.pipes.items() if p.start == tank.name)
               - case.demand_m3h.get(tank.name, [0.0] * nT)[t] - spill[t])
        worst = max(worst, abs(y[t + 1] - y[t] - net * dt / tank.area_m2))
    if worst > tol_mass:
        fails.append(f"tank balance residual {worst:.2e} m")
    notes.append(f"tank balance           max residual {worst:.2e} m")

    # 3. global volume balance ---------------------------------------------
    supplied = sum(q[j, t] for j, p in case.pipes.items()
                   if p.start in case.fixed_heads for t in range(nT)) * dt
    consumed = sum(sum(d) for d in case.demand_m3h.values()) * dt
    stored = (y[nT] - y[0]) * tank.area_m2
    spilled = sum(spill.values()) * dt
    gap = supplied - consumed - stored - spilled
    if abs(gap) > 1e-3:
        fails.append(f"global volume balance off by {gap:.3f} m3")
    notes.append(f"global volume balance  in {supplied:.1f} = out {consumed:.1f} "
                 f"+ stored {stored:.1f} + spill {spilled:.1f}  (gap {gap:.2e})")

    # 4. EXACT hydraulics: recompute head loss from flow, no PWL -----------
    worst, worst_id = 0.0, None
    for j, pipe in case.pipes.items():
        for t in range(nT):
            if j == link and z[t] == 0:
                continue                      # check valve shut, link decoupled
            lhs = head(pipe.start, t) - head(pipe.end, t)
            rhs = pipe.headloss(q[j, t])
            if j == link:
                rhs -= case.pump.head(q[j, t])
            if j == tl and tl != link:
                rhs += thr[t]
            if abs(lhs - rhs) > worst:
                worst, worst_id = abs(lhs - rhs), (j, t)
    if worst > tol_head:
        fails.append(f"EXACT head balance off by {worst:.3f} m at {worst_id}")
    notes.append(f"exact head balance     max residual {worst:.3f} m at {worst_id}")

    # 5. bounds -------------------------------------------------------------
    for n, jn in case.junctions.items():
        for t in range(nT):
            if head(n, t) < jn.min_head_m - 1e-6:
                fails.append(f"pressure violated at {n} h{t}")
    for t in range(nT + 1):
        if not (tank.level_min_m - 1e-6 <= y[t] <= tank.level_max_m + 1e-6):
            fails.append(f"tank level out of bounds at h{t}: {y[t]:.3f}")
    for t in range(nT):
        if z[t] and not (case.pump.q_min_m3h - 1e-4 <= q[link, t]
                         <= case.pump.q_max_m3h + 1e-4):
            fails.append(f"pump flow {q[link,t]:.1f} outside window at h{t}")
        if not z[t] and abs(q[link, t]) > 1e-4:
            fails.append(f"flow {q[link,t]:.3f} through a stopped pump at h{t}")

    # 6. min up/down --------------------------------------------------------
    from itertools import groupby
    runs = [(k, len(list(g))) for k, g in groupby(z[t] for t in range(nT))]
    # the first and last runs are truncated by the horizon, so they are exempt
    for state, length in runs[1:-1]:
        need = case.pump.min_up_h if state else case.pump.min_down_h
        if length < need:
            fails.append(f"min {'up' if state else 'down'} time violated: "
                         f"run of {length} h (need {need})")
    notes.append("on/off runs            " + ", ".join(
        f"{'on' if k else 'off'}x{n}" for k, n in runs))

    # 7. objective ----------------------------------------------------------
    recomputed = sum(case.tariff[t] * case.pump.power_kw(q[link, t]) * dt
                     for t in range(nT) if z[t])
    recomputed += case.pump.start_cost * sum(
        1 for t in range(nT) if z[t] and (t == 0 or z[t - 1] == 0))
    reported = pyo.value(m.obj)
    notes.append(f"objective              model {reported:.2f} vs recomputed "
                 f"from exact curves {recomputed:.2f} "
                 f"({100*(recomputed-reported)/reported:+.2f}%)")
    return fails, notes


def run(extra=None):
    case = ps.default_case()
    m = ps.build_model(case, n_bp_pipe=5, sos2_mode="binary",
                       cyclic_tank=(extra != "no-cycle"))
    ps.solve(m, solver="appsi_highs", mip_gap=1e-4, time_limit=240)
    fails, notes = audit(case, m)
    print(f"\n=== audit{' [' + extra + ']' if extra else ''} ===")
    for n in notes:
        print("   ", n)
    if fails:
        print("    FAILURES:")
        for f in fails:
            print("      !!", f)
    else:
        print("    all checks passed")
    return pyo.value(m.obj), fails


if __name__ == "__main__":
    run("no-cycle" if "--no-cycle" in sys.argv else None)
