"""Two PV options on TR4: checks, per-run metrics, paired comparisons (2026-10-05).

Reads runs/L*/ (runs whose done_<tag>.txt says "Return value = 0" and whose day reached 48 half-hours; SMOKE runs
are reported separately) and writes to results/:
  pv2_runs.csv       one row per run (pattern x case): PV cut, exports, purchases, service delivered, FOR size,
                     checks, differences with the REF day of the same case
  pv2_requests.csv   one row per request: chosen point, FOR area, battery-only FOR area, PV cut of the usual mix
                     and of the batteries-first mix (option 1)
  pv2_halfhour.csv   per run and half-hour: PV cut, surplus, exports, purchases, battery, mean SOC
  pv2_summary.txt    checks and paired statistics
Cases: exp_today / exp_coord = option 1 (PV exported by default, cut only on TSO request); noexp_today /
noexp_coord = option 2 (no export without agreement, PV refills the batteries).
Usage: python scripts/analyze_pv2.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
RUNS, OUT = ROOT / "runs", ROOT / "results"
OUT.mkdir(exist_ok=True)
DT = 0.5
OK = ("Optimal", "LocallyOptimal")
CASES = ["exp_today", "exp_coord", "noexp_today", "noexp_coord"]
LABEL = {"exp_today": "option 1, today's charging", "exp_coord": "option 1, coordinated charging",
         "noexp_today": "option 2, today's charging", "noexp_coord": "option 2, coordinated charging"}


def read(path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    d = pd.read_csv(path, skipinitialspace=True, encoding="utf-8-sig")
    d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if pd.api.types.is_object_dtype(d[c]) or pd.api.types.is_string_dtype(d[c]):
            d[c] = d[c].astype(str).str.strip()
    return d


def clock(p):
    m = (int(p) - 1) * 30
    return f"{m // 60 % 24:02d}:{m % 60:02d}"


runs = {}
CASES_SEEN = set()
for done in sorted(RUNS.glob("L*/done_*.txt")):
    if "Return value = 0" not in done.read_text(errors="ignore"):
        continue
    tag = done.stem[len("done"):]
    case = next((c for c in CASES if tag.endswith("_" + c)), None)
    if case is None:   # fairness variants: <case>_f<N> (FairMode N), see run_pv2.py
        head, _, n = tag.rpartition("_f")
        base = next((c for c in CASES if head.endswith("_" + c)), None)
        if base is None or not n.isdigit():
            continue
        case = f"{base}_f{n}"
        LABEL.setdefault(case, f"{LABEL[base]}, FairMode {n}")
        CASES_SEEN.add(case)
    sid = tag[1:-len(case) - 1]
    lane = done.parent
    ex = read(lane / f"SCT_exec{tag}.csv")
    if ex is None:
        continue
    spec = json.loads((ROOT / "scenarios" / f"{sid}.json").read_text())
    full = ex.now.max() >= 48
    if not full and sid != "SMOKE":
        continue
    runs[(sid, case)] = dict(ex=ex, fq=read(lane / f"FRQ{tag}.csv"), fr=read(lane / f"FOR_rolling{tag}.csv"),
                             bf=read(lane / f"BF{tag}.csv"), p1=read(lane / f"SRQ_p1{tag}.csv"),
                             svc=read(lane / f"FOR_rolling_svc{tag}.csv"), info=lane / f"SCT_info{tag}.txt", spec=spec)
print(f"finished runs: {len(runs)}")
ALLC = CASES + sorted(CASES_SEEN)   # fairness variants (case_fN) after the four main cases

rows, reqrows, hh = [], [], []
for (sid, case), r in sorted(runs.items()):
    ex, fq, fr, sv, bf, p1 = r["ex"], r["fq"], r["fr"], r["svc"], r["bf"], r["p1"]
    svc_now = set(ex.loc[ex.svc == 1, "now"].unique())
    out = ~ex.now.isin(svc_now)
    cut = ex.cut1_kWh + ex.zx_cut1_kWh          # option 1: cut executed for a request; option 2: surplus cut
    surplus = ex.zx_cap1_kWh if case.startswith("noexp") else None
    d = dict(pattern=sid, family=r["spec"]["family"], case=case, steps=int(ex.now.max()),
             n_requests_planned=len(r["spec"]["requests"]),
             pv_cut_kWh=cut.sum(), exports_kWh=ex.exp1_kWh.sum(),
             exports_agreed_kWh=ex.loc[~out, "exp1_kWh"].sum(), exports_not_requested_kWh=ex.loc[out, "exp1_kWh"].sum(),
             purchases_kWh=ex.imp1_kWh.sum(), purchases_outside_kWh=ex.loc[out, "imp1_kWh"].sum(),
             soc_end_pct=100 * ex.loc[ex.now == ex.now.max(), "soc_start"].mean(),
             baseline_not_optimal=int((~ex.groupby("now").base_status.first().isin(OK)).sum()))
    if surplus is not None:
        d["surplus_kWh"] = surplus.sum()
    if fr is not None and len(fr):
        d["corners_not_optimal"] = int((~fr.status.isin(OK)).sum())
    if p1 is not None and len(p1):
        d["coord_step2_not_optimal"] = int((~p1.stat2.isin(OK)).sum())
    if fq is not None and len(fq):
        d.update(n_requests=len(fq), export_more_kWh=DT * (-fq.dP_kW).clip(lower=0).sum(),
                 export_less_kWh=DT * fq.dP_kW.clip(lower=0).sum(), q_kvarh=DT * fq.dQ_kvar.abs().sum(),
                 netted_max_kW=fq.netted_kW.max(), shave_kWh=fq.shave_kWh.sum(),
                 for_area_mean=fq.for_area_kWkvar.mean(), corners_min=int(fq.n_corners.min()),
                 cut_committed_kWh=DT * fq.cut_kW.sum())
        if bf is not None and len(bf):
            d.update(cut_mix_kWh=DT * bf.cut_mix_kW.sum(), cut_bf_kWh=DT * bf.cut_bf_kW.sum(),
                     bf_rebuilt=int(bf.bf_used.sum()), bf_check_max_kW=max(bf.chk_P_kW.abs().max(), bf.chk_Q_kvar.abs().max()),
                     batt_area_mean=bf.area_batt_kWkvar.mean())
        b = bf.set_index("target") if bf is not None and len(bf) else None
        for q in fq.itertuples():
            row = dict(pattern=sid, case=case, now=q.now, target=q.target, clock=clock(q.target), edge=q.edge,
                       dP_kW=q.dP_kW, dQ_kvar=q.dQ_kvar, chg_kW=q.chg_kW, dis_kW=q.dis_kW, cut_kW=q.cut_kW,
                       batt0_kW=q.batt0_kW, for_area=q.for_area_kWkvar, netted_kW=q.netted_kW, soc_mean_pct=q.soc_mean_pct)
            if b is not None and q.target in b.index:
                x = b.loc[q.target]
                row.update(cut_mix_kW=x.cut_mix_kW, cut_bf_kW=x.cut_bf_kW, bf_used=x.bf_used, batt_area=x.area_batt_kWkvar)
            reqrows.append(row)
    else:
        d.update(n_requests=0, export_more_kWh=0.0, export_less_kWh=0.0)
    if sv is not None and len(sv):
        e = sv[sv.event == "execute"]
        if len(e):
            d["realised_vs_chosen_max_kW"] = 1000 * max((e.real_P - e.req_P).abs().max(), (e.real_Q - e.req_Q).abs().max())
            d["n_executed"] = len(e)
    if r["info"].exists():
        txt = r["info"].read_text(errors="ignore")
        d["exec_failures"] = txt.count("EXECFAIL")
        d["qcp_cplex"] = int("type QCP" in txt and "CPLEX 22.1" in txt and not any(w in txt for w in ("type LP ", "type MIQCP", "type NLP")))
        line = next((l for l in txt.splitlines() if l.startswith("PV2 summary")), "")
        for key, name in (("twins ", "twins"), (" failed ", "twins_failed"), ("step-2 retries ", "step2_retries"), (" fallbacks ", "step2_fallbacks")):
            if key in line:
                try:
                    d[name] = int(float(line.split(key, 1)[1].split()[0].strip(",")))
                except ValueError:
                    pass
    ref = runs.get(("REF", case)) or runs.get(("REF", case.rsplit("_f", 1)[0]))   # REF has no FOR: fairness cannot change it
    if ref is not None and sid not in ("REF", "SMOKE"):
        rex = ref["ex"]
        rcut = rex.cut1_kWh + rex.zx_cut1_kWh
        d["pv_cut_vs_ref_kWh"] = d["pv_cut_kWh"] - rcut.sum()
        a = ex[out].groupby("battery").imp1_kWh.sum()
        bb = rex[~rex.now.isin(svc_now)].groupby("battery").imp1_kWh.sum()
        diff = (a - bb).reindex(bb.index).fillna(0)
        d["extra_purchase_max_house_kWh"] = diff.max()
        d["houses_buying_more"] = int((diff > 0.01).sum())
        d["purchases_outside_vs_ref_kWh"] = a.sum() - bb.sum()
        d["plan_next24h_vs_ref_kWh"] = ex.loc[ex.now == 48, "imp_plan_fut_kWh"].sum() - rex.loc[rex.now == 48, "imp_plan_fut_kWh"].sum()
        d["soc_end_vs_ref_pct"] = d["soc_end_pct"] - 100 * rex.loc[rex.now == 48, "soc_start"].mean()
        d["exports_vs_ref_kWh"] = d["exports_kWh"] - rex.exp1_kWh.sum()
    rows.append(d)
    g = ex.groupby("now")
    h = pd.DataFrame(dict(pv_cut_kWh=(g.cut1_kWh.sum() + g.zx_cut1_kWh.sum()), surplus_kWh=g.zx_cap1_kWh.sum(),
                          exports_kWh=g.exp1_kWh.sum(), purchases_kWh=g.imp1_kWh.sum(), battery_kWh=g.batt1_kWh.sum(),
                          soc_mean_pct=100 * g.soc_start.mean(), svc=g.svc.max())).reset_index()
    h.insert(0, "case", case)
    h.insert(0, "pattern", sid)
    hh.append(h)

R = pd.DataFrame(rows)
R.to_csv(OUT / "pv2_runs.csv", index=False)
Qd = pd.DataFrame(reqrows)
Qd.to_csv(OUT / "pv2_requests.csv", index=False)
H = pd.concat(hh) if hh else pd.DataFrame()
H.to_csv(OUT / "pv2_halfhour.csv", index=False)


def stat_line(x, label):
    x = pd.Series(x).dropna()
    if len(x) < 2:
        return f"  {label}: n = {len(x)}" + (f", value {x.iloc[0]:.3f}" if len(x) else "")
    p = wilcoxon(x).pvalue if (x.abs() > 1e-9).any() else 1.0
    return (f"  {label}: n = {len(x)}, total {x.sum():10.2f}, median {x.median():9.3f}, IQR {x.quantile(.25):8.3f} .. "
            f"{x.quantile(.75):8.3f}, positive in {(x > 0.01).sum()}, negative in {(x < -0.01).sum()}, Wilcoxon p = {p:.2g}")


L = [f"finished runs: {len(R)}  (" + ", ".join(f"{c}: {int((R.case == c).sum())}" for c in ALLC if len(R)) + ")"]
if len(R):
    L += ["", "CHECKS (all runs)"]
    for col, what in (("baseline_not_optimal", "P1 baseline solves not Optimal"), ("corners_not_optimal", "FOR corners not Optimal"),
                      ("coord_step2_not_optimal", "coordinated second steps not Optimal (after retry)"),
                      ("step2_retries", "coordinated second steps that needed the numeric retry"),
                      ("twins_failed", "battery-only twins not Optimal"), ("exec_failures", "committed services not executable")):
        if col in R:
            L.append(f"  {what}: {int(R[col].fillna(0).sum())}")
    if "twins" in R:
        L.append(f"  battery-only twin solves: {int(R.twins.fillna(0).sum())}")
    L.append(f"  requests planned {int(R.n_requests_planned.sum())}, served {int(R.n_requests.sum())}, "
             f"executed {int(R.get('n_executed', pd.Series(dtype=float)).fillna(0).sum())}")
    if "realised_vs_chosen_max_kW" in R:
        L.append(f"  realised vs chosen transformer point, worst: {R.realised_vs_chosen_max_kW.max():.4f} kW")
    if "bf_check_max_kW" in R:
        L.append(f"  batteries-first mix reproduces the chosen point, worst error: {R.bf_check_max_kW.max():.6f} kW")
    n2 = R[R.case.str.startswith("noexp")]
    if len(n2):
        L.append(f"  option 2: exports in half-hours without a request, worst run: {n2.exports_not_requested_kWh.max():.4f} kWh")
    if "extra_purchase_max_house_kWh" in R:
        L.append(f"  worst extra purchase of one house outside the requested half-hours (vs REF of its case): {R.extra_purchase_max_house_kWh.max():.4f} kWh")
        L.append(f"  houses buying more than 10 Wh more (sum over runs): {int(R.houses_buying_more.fillna(0).sum())}")
    if "qcp_cplex" in R:
        L.append(f"  runs with every program QCP + CPLEX 22.1: {int(R.qcp_cplex.sum())} of {len(R)}")

    L += ["", "REFERENCE DAYS (no request)"]
    for c in ALLC:
        t = R[(R.pattern == "REF") & (R.case == c)]
        if len(t):
            t = t.iloc[0]
            L.append(f"  {LABEL[c]:32s} PV cut {t.pv_cut_kWh:7.1f} kWh, exports {t.exports_kWh:7.1f}, purchases {t.purchases_kWh:6.2f}, end SOC {t.soc_end_pct:5.1f} %")

    S = R[~R.pattern.isin(["REF", "SMOKE"])]
    for c in ALLC:
        T = S[S.case == c]
        if not len(T) or "pv_cut_vs_ref_kWh" not in T:
            continue
        L += ["", f"{LABEL[c].upper()} - against its own REF day"]
        L.append(stat_line(T.pv_cut_vs_ref_kWh, "PV cut, run - REF, kWh (negative = PV saved)"))
        L.append(stat_line(T.purchases_outside_vs_ref_kWh, "purchases outside the requests, run - REF, kWh"))
        L.append(stat_line(T.export_more_kWh, "'export more' delivered, kWh"))
        L.append(stat_line(T.export_less_kWh, "'export less / import more' delivered, kWh"))
        if c.startswith("exp") and "cut_mix_kWh" in T:
            L.append(stat_line(T.cut_mix_kWh - T.cut_bf_kWh, "PV cut avoided by batteries-first delivery (usual mix - batteries-first), kWh"))
            sel = T.export_less_kWh > 1
            if sel.any():
                L.append(f"  PV cut per kWh of 'export less': batteries-first {T.loc[sel, 'cut_bf_kWh'].sum() / T.loc[sel, 'export_less_kWh'].sum():.3f}, "
                         f"usual mix {T.loc[sel, 'cut_mix_kWh'].sum() / T.loc[sel, 'export_less_kWh'].sum():.3f} (pooled over {int(sel.sum())} runs)")
        if c.startswith("noexp"):
            sel = T.export_more_kWh > 1
            if sel.any():
                L.append(f"  PV saved per kWh of 'export more': {-T.loc[sel, 'pv_cut_vs_ref_kWh'].sum() / T.loc[sel, 'export_more_kWh'].sum():.3f} (pooled over {int(sel.sum())} runs)")
        for t in T.sort_values("pattern").itertuples():
            L.append(f"    {t.pattern:10s} req {t.n_requests:3.0f}  export-more {t.export_more_kWh:7.1f}  export-less {t.export_less_kWh:7.1f}  "
                     f"PV cut {t.pv_cut_kWh:7.1f} (vs REF {t.pv_cut_vs_ref_kWh:+7.1f})  buy-outside vs REF {t.purchases_outside_vs_ref_kWh:+7.3f}  "
                     f"worst house {t.extra_purchase_max_house_kWh:6.3f}  FOR {getattr(t, 'for_area_mean', float('nan')):8.0f}")

    # paired comparisons, same TSO behaviour (pattern)
    def paired(c1, c2, col):
        a = S[S.case == c1].set_index("pattern")[col] if col in S else pd.Series(dtype=float)
        b = S[S.case == c2].set_index("pattern")[col] if col in S else pd.Series(dtype=float)
        j = a.index.intersection(b.index)
        return a[j], b[j]

    L += ["", "PAIRED, same TSO behaviour (pattern): coordinated - today"]
    for opt in ("exp", "noexp"):
        for col, what in (("for_area_mean", "mean FOR area at the requests, kW x kvar"), ("pv_cut_kWh", "PV cut, kWh"),
                          ("export_more_kWh", "'export more', kWh"), ("export_less_kWh", "'export less', kWh"),
                          ("purchases_kWh", "purchases, kWh")):
            a, b = paired(f"{opt}_coord", f"{opt}_today", col)
            if len(a):
                L.append(stat_line(a - b, f"option {'1' if opt == 'exp' else '2'} {what}"))
        if opt == "exp" and "cut_bf_kWh" in S:
            a, b = paired("exp_coord", "exp_today", "cut_bf_kWh")
            la, lb = paired("exp_coord", "exp_today", "export_less_kWh")
            if len(a) and la.sum() > 1 and lb.sum() > 1:
                L.append(f"  option 1 PV cut per kWh of 'export less' (batteries-first, pooled): today {b.sum() / lb.sum():.3f}, coordinated {a.sum() / la.sum():.3f}")
                ra, rb = (a / la.where(la > 1)), (b / lb.where(lb > 1))
                L.append(stat_line((ra - rb).dropna(), "option 1 PV cut per kWh of 'export less', coordinated - today (per pattern)"))
    L += ["", "PAIRED, same TSO behaviour: option 2 - option 1 (same charging)"]
    for ch in ("today", "coord"):
        for col, what in (("for_area_mean", "mean FOR area at the requests, kW x kvar"), ("pv_cut_kWh", "PV cut over the day, kWh"),
                          ("exports_kWh", "exports over the day, kWh"), ("purchases_kWh", "purchases, kWh")):
            a, b = paired(f"noexp_{ch}", f"exp_{ch}", col)
            if len(a):
                L.append(stat_line(a - b, f"{ch}: {what}"))

    Sm = R[R.pattern == "SMOKE"]
    if len(Sm):
        L += ["", "SMOKE runs (check, up to 14:30)"]
        for t in Sm.itertuples():
            L.append(f"  {t.case:12s} steps {t.steps}, requests {getattr(t, 'n_requests', 0)}, PV cut {t.pv_cut_kWh:.1f} kWh, exports {t.exports_kWh:.1f}, "
                     f"purchases {t.purchases_kWh:.2f}, corners not Optimal {getattr(t, 'corners_not_optimal', float('nan'))}, "
                     f"twins {getattr(t, 'twins', float('nan'))}, usual-mix cut {getattr(t, 'cut_mix_kWh', float('nan')):.2f} kWh, batteries-first cut {getattr(t, 'cut_bf_kWh', float('nan')):.2f} kWh, "
                     f"realised vs chosen {getattr(t, 'realised_vs_chosen_max_kW', float('nan')):.4f} kW")
(OUT / "pv2_summary.txt").write_text("\n".join(L) + "\n")
print("\n".join(L))
