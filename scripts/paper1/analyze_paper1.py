"""Paper-1 runs: checks and self-consumption metrics for every finished job in the work directory.

Reads <work>/L*/ (jobs whose done file says "Return value = 0"). Each request pattern is compared with the REF run of
the same case, speed, network and extra settings (FairMode=... etc.). Two-day runs (speed ...fin2) are joined with
their day-2 files (*_d2). Definitions:
  extra purchase   a house's purchases outside the requested half-hours, run minus REF (over the simulated days);
  all half-hours   the same including the requested half-hours (meaningful for export requests only: an import
                   request makes houses buy during the service by design);
  service          energy of the requested change from the no-request point (dP < 0: more export; dP > 0: less).
Writes <work>/paper1_runs.csv, <work>/paper1_for.csv (FOR at every half-hour of REF_SWEEP runs) and
<work>/paper1_summary.txt.
Usage: python scripts/paper1/analyze_paper1.py [--work DIR]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SCEN = Path(__file__).resolve().parent / "scenarios"
DT = 0.5
OK = ("Optimal", "LocallyOptimal")
SIDS = sorted((p.stem for p in SCEN.glob("*.json")), key=len, reverse=True)   # longest first: REF_SWEEP before REF


def read(p):
    if p is None or not p.exists() or p.stat().st_size == 0:
        return None
    d = pd.read_csv(p, skipinitialspace=True, encoding="utf-8-sig")
    d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if pd.api.types.is_object_dtype(d[c]) or pd.api.types.is_string_dtype(d[c]):
            d[c] = d[c].astype(str).str.strip()
    return d


def area(P, Q):
    P, Q = np.asarray(P, float), np.asarray(Q, float)
    return 0.5 * abs(np.dot(P, np.roll(Q, -1)) - np.dot(Q, np.roll(P, -1)))


def clock(p):
    m = (int(p) - 1) * 30
    return f"{m // 60 % 24:02d}:{m % 60:02d}"


def parse_tag(tag):
    """_<sid>_<case>_<speed>[_rest] -> (sid, case, speed, rest)"""
    for sid in SIDS:
        if tag.startswith(f"_{sid}_"):
            parts = tag[len(sid) + 2:].split("_")
            case = "_".join(parts[:2])            # free_today
            speed = parts[2] if len(parts) > 2 else ""
            return sid, case, speed, "_".join(parts[3:])
    return None


def info_counts(path):
    d = dict(net_checks=0, net_checks_failed=0, rescues=0, exec_failures=0, kept_infeasible=0, clip_Wh=0.0)
    if path is None or not path.exists():
        return d
    txt = path.read_text(errors="ignore")
    d["exec_failures"] = txt.count("EXECFAIL")
    d["rescues"] = txt.count("NCRESCUE")
    d["clip_Wh"] = sum(float(l.split(" by ", 1)[1].split()[0]) for l in txt.splitlines() if l.startswith("NCCLIP"))
    for l in txt.splitlines():
        if l.startswith("SPEED settings") or l.startswith("DAY 2"):
            d["net_checks"] += int(l.split("network checks ", 1)[1].split()[0])
            d["net_checks_failed"] += int(l.split("failed ", 1)[1].split()[0])
        if (l.startswith("DECISION TEST") or l.startswith("DAY 2")) and "infeasible " in l:
            d["kept_infeasible"] += int(l.split("infeasible ", 1)[1].split()[0])
    return d


def days(lane, tag, two):
    d1 = read(lane / f"SCT_exec{tag}.csv")
    if d1 is None:
        return None
    if not two:
        return d1
    d2 = read(lane / f"SCT_exec{tag}_d2.csv")
    if d2 is None:
        return None
    d2 = d2.copy()
    d2["now"] = d2.now + 48
    return pd.concat([d1, d2], ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=str(REPO.parent / "paper1-runs"))
    work = Path(ap.parse_args().work)
    jobs = read(work / "jobs.csv")
    runs = {}
    for done in sorted(work.glob("L*/done_*.txt")):
        if "Return value = 0" not in done.read_text(errors="ignore"):
            continue
        tag = done.stem[len("done"):]
        p = parse_tag(tag)
        if p:
            runs[tag] = (done.parent, *p)
    rows, frows = [], []
    for tag, (lane, sid, case, speed, rest) in sorted(runs.items(), key=lambda x: (x[1][4], x[1][1])):
        two = speed.endswith("fin2")
        ex = days(lane, tag, two)
        if ex is None:
            continue
        reftag = f"_REF_{case}_{speed}" + (f"_{rest}" if rest else "")
        ref = days(runs[reftag][0], reftag, two) if reftag in runs else None
        spec = json.loads((SCEN / f"{sid}.json").read_text())
        d = dict(network_and_settings=rest or "TR4", pattern=sid, speed=speed, batteries=ex.battery.nunique(),
                 baseline_not_optimal=int((~ex.groupby("now").base_status.first().isin(OK)).sum()),
                 pv_cut_kWh=float((ex.cut1_kWh + ex.zx_cut1_kWh).sum()), n_planned=len(spec["requests"]))
        if jobs is not None and "tag" in jobs:
            j = jobs[(jobs.tag == tag) & (jobs.ok.astype(str) == "1")]
            d["wall_min"] = float(j.wall_min.iloc[-1]) if len(j) else np.nan
        c1 = info_counts(lane / f"SCT_info{tag}.txt")
        c2 = info_counts(lane / f"SCT_info{tag}_d2.txt") if two else {k: 0 for k in c1}
        d.update({k: c1[k] + c2[k] for k in c1})
        fq, fr, sv = read(lane / f"FRQ{tag}.csv"), read(lane / f"FOR_rolling{tag}.csv"), read(lane / f"FOR_rolling_svc{tag}.csv")
        if fr is not None and len(fr):
            d["fors"] = fr.now.nunique()
            d["corners_not_optimal"] = int((~fr.status.isin(OK)).sum())
            d["fors_incomplete"] = int((fr.groupby("now").status.apply(lambda x: (~x.isin(OK)).sum()) > 0).sum())
        if fq is not None and len(fq):
            d.update(n_requests=len(fq), export_more_kWh=DT * (-fq.dP_kW).clip(lower=0).sum(),
                     export_less_kWh=DT * fq.dP_kW.clip(lower=0).sum(), shave_kWh=fq.shave_kWh.sum())
        else:
            d.update(n_requests=0, export_more_kWh=0.0, export_less_kWh=0.0, shave_kWh=0.0)
        if sv is not None and len(sv):
            e = sv[sv.event == "execute"]
            if len(e):
                d["realised_vs_chosen_max_kW"] = 1000 * max((e.real_P - e.req_P).abs().max(), (e.real_Q - e.req_Q).abs().max())
        if ref is not None and sid != "REF":
            svc = set(ex.loc[ex.svc == 1, "now"].unique())
            out = lambda x: x[~x.now.isin(svc)]
            a, b = out(ex).groupby("battery").imp1_kWh.sum(), out(ref).groupby("battery").imp1_kWh.sum()
            diff = (a - b).reindex(b.index).fillna(0)
            allh = (ex.groupby("battery").imp1_kWh.sum() - ref.groupby("battery").imp1_kWh.sum()).reindex(b.index).fillna(0)
            last = ex.now.max()
            d.update(worst_house_Wh=1000 * diff.max(), worst_house=diff.idxmax(), houses_over_10Wh=int((diff > 0.01).sum()),
                     worst_house_all_halfhours_Wh=1000 * allh.max(), fleet_outside_vs_ref_kWh=diff.sum(),
                     exports_outside_vs_ref_kWh=out(ex).exp1_kWh.sum() - out(ref).exp1_kWh.sum(),
                     soc_end_vs_ref_pct=100 * (ex.loc[ex.now == last, "soc_start"].mean() - ref.loc[ref.now == last, "soc_start"].mean()))
        rows.append(d)
        if spec.get("sweep_all") and fr is not None:
            for now, g in fr[fr.status.isin(OK)].groupby("now"):
                g = g.sort_values("angle_deg")
                frows.append(dict(network_and_settings=rest or "TR4", now=now, clock=clock(g.target.iloc[0]), corners=len(g),
                                  area_kWkvar=1e6 * area(g.P, g.Q), P_min_kW=1000 * g.P.min(), P_max_kW=1000 * g.P.max(),
                                  Q_min_kvar=1000 * g.Q.min(), Q_max_kvar=1000 * g.Q.max(), at_vmax=int((g.VmaxTrue >= 1.0999).sum())))
    R, F = pd.DataFrame(rows), pd.DataFrame(frows)
    R.to_csv(work / "paper1_runs.csv", index=False)
    F.to_csv(work / "paper1_for.csv", index=False)
    L = [f"PAPER-1 RUNS in {work}: {len(R)} finished jobs", ""]
    if len(R):
        for col, what in (("baseline_not_optimal", "P1 baselines not optimal"), ("corners_not_optimal", "FOR corners not optimal"),
                          ("fors_incomplete", "FORs with a failed corner"), ("net_checks_failed", "network checks failed"),
                          ("rescues", "rescues after a failed check (NCRESCUE)"), ("exec_failures", "committed services released"),
                          ("kept_infeasible", "kept plans infeasible")):
            if col in R:
                L.append(f"  {what}: {int(R[col].fillna(0).sum())}")
        L.append(f"  PV cut: {R.pv_cut_kWh.sum():.6f} kWh (must be 0); requests planned {int(R.n_planned.sum())}, "
                 f"served {int(R.n_requests.sum())}; energy clipped at rescues {R.clip_Wh.sum():.4f} Wh")
        L += ["", "PER RUN (worst house = extra purchase outside the requested half-hours vs REF)"]
        for t in R.itertuples():
            L.append(f"  {t.network_and_settings:12s} {t.pattern:10s} req {t.n_requests:3.0f}/{t.n_planned:<3d} "
                     f"worst house {getattr(t, 'worst_house_Wh', np.nan):8.2f} Wh (all half-hours {getattr(t, 'worst_house_all_halfhours_Wh', np.nan):8.2f})  "
                     f"fleet {getattr(t, 'fleet_outside_vs_ref_kWh', np.nan):+8.2f} kWh  checks failed {t.net_checks_failed:3d}  "
                     f"rescues {t.rescues:2d}  released {t.exec_failures:2d}  FORs short {np.nan_to_num(getattr(t, 'fors_incomplete', 0)):2.0f}  "
                     f"{getattr(t, 'wall_min', np.nan):7.1f} min")
    if len(F):
        L += ["", "FOR AT EVERY HALF-HOUR (REF_SWEEP)"]
        for net, g in F.groupby("network_and_settings"):
            L.append(f"  {net}: area mean {g.area_kWkvar.mean():8.0f} kW*kvar, min {g.area_kWkvar.min():8.0f} at "
                     f"{g.loc[g.area_kWkvar.idxmin(), 'clock']}, max {g.area_kWkvar.max():8.0f} at {g.loc[g.area_kWkvar.idxmax(), 'clock']}; "
                     f"vertices at 1.10 pu {int(g.at_vmax.sum())} of {int(g.corners.sum())}")
    (work / "paper1_summary.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
