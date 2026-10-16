"""Paper-1 fairness results: check that the runs in the lanes reproduce the reference numbers (October 2026).

The reference numbers are the JSON files in results/paper1-fairness-2026-10/ (its README.md says which run produced each
one). Every reference run found in the lanes is recomputed from its own CSVs and compared:
  one-day sweeps (REF_SWEEP ... a2x4p8fin): FOR_rolling<tag>.csv gives the status of the 576 directional solves, the 12
      boundary points of every step (as deviations from the all-idle exchange stored in sweeps.json), the area (shoelace)
      and the area ratio to the reference run of the same set (_FairEffHead1 for the energy floor, _FairBox1 for the old
      floor and the mu^f runs); FOR_rolling_crit<tag>.csv gives the fleet sums of U_s, D_s and dP^b_s at 0 and 180 deg,
      the solves with simultaneous charging and discharging, the throughput and the mixed HP allocations at 180 deg;
  two-day service runs (WC_EXPORT ... a2x4p8fin2): requests served, export served (FRQ dP_kW), the FOR of every requested
      slot (status, area, points, area ratios), the extra house import inside and outside the requested half-hours
      against the run's no-request REF run, and the state before the first request;
  two-day no-request runs (REF ... a2x4p8fin2): no requests and the day-1 mean SOC (they are the partners above).
The FAIR settings line of SCT_info<tag>.txt is compared too, so a run made with other settings (e.g. the energy floor
under an old-floor tag) is reported as such.

Tolerances: area ratio +-1e-3 (areas: 1e-3 x the reference-run area of the same step), kW and kvar +-0.05, kWh +-0.1,
SOC +-0.05 percentage points, counts exact. Each is widened by half a unit of the decimals the reference was stored
with (e.g. +-0.005 for values kept to 2 dp). Counts of prosumers above 1 Wh (10 Wh) whose reference worst value is
below 10 Wh are numerical noise: a different count is printed as INFO and does not fail.

Old-floor runs (tags without _FairEffHead1) were made with commit 866c053, which has no FairEffHead. The current model
defaults to FairEffHead=1, so they are reproduced by adding FairEffHead=0 at the end of the job line; the tag then ends
in _FairEffHead0 and is accepted for the reference tag without it.

Status per run: PASS (every check passed), PARTIAL (passed, but some checks could not run because a partner run is
missing), DIFF (at least one check differs; the details follow the table). Reference runs not found are listed with the
job line that makes them. Exit code 0 when no run differs, 1 when one does, 2 when no reference run was found.

Usage: python -B scripts/paper1/check_fairness_reference.py [--work DIR] [--lanes N2 N3] [--ref DIR] [--verbose]
  --work     the runs root (default ../paper1-runs, next to the repository)
  --lanes    lane folders under --work (default: every folder with FOR_rolling*.csv)
  --ref      the reference folder (default results/paper1-fairness-2026-10)
  --verbose  print every check, not only the differences
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
QUEUES = Path(__file__).resolve().parent / "queues"
DT = 0.5
OK = ("Optimal", "LocallyOptimal")
TOL = {"ratio": 1e-3, "kW": 0.05, "kWh": 0.1, "pp": 0.05}
NOISE_KWH = 0.01                     # a "> 1 Wh" count is noise when the reference worst value is below 10 Wh
ALIAS = "_FairEffHead0"              # old-floor tags re-run with the current model
DIAGNOSTIC = "_SCAlpha"              # made with a diagnostic copy of PV2_Run: not reproducible from the repository
FIRST_REQUEST = 13                   # first requested slot of WC_EXPORT (06:00)


# ---------------------------------------------------------------- reading
def read(p):
    if p is None or not p.exists() or p.stat().st_size == 0:
        return None
    d = pd.read_csv(p, skipinitialspace=True, encoding="utf-8-sig")
    d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if pd.api.types.is_object_dtype(d[c]) or pd.api.types.is_string_dtype(d[c]):
            d[c] = d[c].astype(str).str.strip()
    return d


def two_days(lane, tag, stem):
    a, b = read(lane / f"{stem}{tag}.csv"), read(lane / f"{stem}{tag}_d2.csv")
    if a is None or b is None:
        return a
    b = b.copy()
    b["now"] = b["now"] + 48
    return pd.concat([a, b], ignore_index=True)


def area(P, Q):
    P, Q = np.asarray(P, float), np.asarray(Q, float)
    return 0.5 * abs(np.dot(P, np.roll(Q, -1)) - np.dot(Q, np.roll(P, -1)))


def finished(lane, tag):
    f = lane / f"done{tag}.txt"
    return f.exists() and "Return value = 0" in f.read_text(errors="ignore")


def fair_settings(text):
    """FAIR settings line -> {field: value}; FairEffHead is 0 when the line has no such field (commit 866c053)."""
    if not text:
        return None
    d = {k: float(v) for k, v in re.findall(r"(\w+)(?: \(\w+\))?\s+(-?[0-9.]+)", text.split(":", 1)[1])}
    d.setdefault("FairEffHead", 0.0)
    return d


def run_settings(lane, tag):
    f = lane / f"SCT_info{tag}.txt"
    if not f.exists():
        return None, None
    line = next((l for l in f.read_text(errors="ignore").splitlines() if l.startswith("FAIR settings")), None)
    return fair_settings(line), line


# ---------------------------------------------------------------- checks
class Checks:
    def __init__(self):
        self.rows = []                # (name, state, detail); state PASS / DIFF / SKIP / INFO

    def add(self, name, state, detail=""):
        self.rows.append((name, state, detail))

    def skip(self, name, why):
        self.add(name, "SKIP", why)

    def num(self, name, got, ref, tol, rnd=0.0, unit="", at=None):
        """max |got - ref| <= tol + rnd over the reference values that are not null (tol may be an array).
        at(k) names the position k of the flattened values in the report (default: #k)."""
        g = np.atleast_1d(np.asarray(got, dtype=float)).ravel()
        r = np.atleast_1d(np.asarray(ref, dtype=float)).ravel()
        if g.shape != r.shape:
            self.add(name, "DIFF", f"{g.size} values, the reference has {r.size}")
            return
        lim = np.broadcast_to(np.asarray(tol, float) + rnd + 1e-9, r.shape)
        m = ~np.isnan(r)
        if (np.isnan(g) & m).any():
            self.add(name, "DIFF", f"{int((np.isnan(g) & m).sum())} values missing")
            return
        d = np.abs(g[m] - r[m])
        if not d.size:
            self.add(name, "PASS", "no reference values")
            return
        i = int(np.argmax(d - lim[m]))
        bad = int((d > lim[m]).sum())
        if r.size == 1:
            detail = f"{g[0]:.4f} vs {r[0]:.4f} {unit} (tol {lim[0]:.3g})"
        else:
            detail = (f"max |diff| {d.max():.3g} {unit} over {d.size} values (tol {lim[m].max():.3g})"
                      + (f"; {bad} outside, worst at {(at or (lambda k: f'#{k}'))(int(np.flatnonzero(m)[i]))}: "
                         f"{g[m][i]:.4f} vs {r[m][i]:.4f}" if bad else ""))
        self.add(name, "DIFF" if bad else "PASS", detail)

    def count(self, name, got, ref, soft=False):
        g, r = np.atleast_1d(np.asarray(got)).ravel(), np.atleast_1d(np.asarray(ref)).ravel()
        same = g.shape == r.shape and bool((g == r).all())
        if r.size <= 3 and g.size <= 3:
            detail = " / ".join(map(str, g.tolist())) + " vs " + " / ".join(map(str, r.tolist()))
        else:
            detail = f"{int((g != r).sum()) if g.shape == r.shape else 'shape'} of {r.size} differ (total {g.sum()} vs {r.sum()})"
        self.add(name, "PASS" if same else ("INFO" if soft else "DIFF"), detail + (" [noise level]" if soft and not same else ""))

    def status(self):
        s = [r[1] for r in self.rows]
        return "DIFF" if "DIFF" in s else ("PARTIAL" if "SKIP" in s else "PASS")


# ---------------------------------------------------------------- lanes and tags
class Lanes:
    def __init__(self, paths):
        self.paths = paths

    def find(self, tag, stem):
        """[(lane, lane tag)] for the tag and its old-floor alias, in lane order."""
        out = []
        for lane in self.paths:
            for t in (tag, tag + ALIAS) if not tag.endswith("_FairEffHead1") else (tag,):
                if (lane / f"{stem}{t}.csv").exists():
                    out.append((lane, t))
        return out

    def partner(self, tag, stem, prefer):
        hits = self.find(tag, stem)
        hits.sort(key=lambda h: h[0] != prefer)
        return hits[0] if hits else (None, None)


def expected_effhead(tag):
    return 1.0 if ("_FairEffHead1" in tag or DIAGNOSTIC in tag) else 0.0


def check_settings(ck, lane, tag, ref_tag, ref_line=None):
    got, line = run_settings(lane, tag)
    if got is None:
        ck.add("FAIR settings line", "DIFF", f"no FAIR settings line in SCT_info{tag}.txt")
        return
    want = fair_settings(ref_line) if ref_line else {"FairEffHead": expected_effhead(ref_tag)}
    bad = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
    if bad:
        hint = ""
        if "FairEffHead" in bad and want["FairEffHead"] == 0:
            hint = " (old-floor reference: re-run with FairEffHead=0 at the end of the job line)"
        ck.add("FAIR settings line", "DIFF", "run vs reference " + ", ".join(f"{k} {a} vs {b}" for k, (a, b) in bad.items()) + hint)
    else:
        ck.add("FAIR settings line", "PASS", f"{len(want)} fields equal")


def job_line(tag):
    """Reference tag -> queue line that makes it with the current model."""
    sid, rest = tag[1:].split("_free_today_", 1)
    parts = rest.split("_")
    out = [sid, "free_today", parts[0]]
    for p in parts[1:]:
        if re.fullmatch(r"TR\d+|ALL", p):
            out.append(p)
            continue
        m = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*?)(-?\d+(?:\.\d+)?)", p)
        out.append(f"{m.group(1)}={m.group(2)}" if m else p)
    if expected_effhead(tag) == 0 and sid != "REF":
        out.append("FairEffHead=0")
    return " ".join(out)


def queue_tags():
    out = {}
    for q in sorted(QUEUES.glob("*.txt")):
        for line in q.read_text().splitlines():
            f = line.split("#", 1)[0].split()
            if len(f) < 3:
                continue
            net, extra = "", ""
            for x in f[3:]:
                if "=" in x:
                    k, v = x.split("=", 1)
                    extra += f"_{k}{v}"
                else:
                    net = "_" + x.replace(",", "")
            out.setdefault(f"_{f[0]}_{f[1]}_{f[2]}{net}{extra}", q.name)
    return out


# ---------------------------------------------------------------- reference files
def load_reference(ref):
    J = lambda n: json.loads((ref / n).read_text(encoding="utf-8"))
    R = {"sweeps": J("sweeps.json"), "muf": J("muf.json"), "fair": J("fair.json"), "t5": J("service_T5.json"),
         "svc": J("service_requests.json"), "guar": J("guarantee.json"), "time": J("for_time.json")}
    sw = R["sweeps"]
    one = {c["source_tag"]: cid for cid, c in sw["cases"].items()}
    two = {}                                     # export tag -> {source: (key, no-request tag)}
    for key, c in R["svc"]["cases"].items():
        if key != "no_request":
            two.setdefault(c["tag"], {})["svc"] = (key, c["extra_import"]["no_request_run"].split("/", 1)[1])
    for c in R["t5"]["cases"]:
        two.setdefault(c["source_tag"], {})["t5"] = (c["id"], c["no_request_tag"])
    for key in ("guarantee_on", "guarantee_relaxed"):
        two.setdefault(R["guar"][key]["tag"], {})["guar"] = (key, R["guar"]["no_request"]["tag"])
    noreq = sorted({p[1] for v in two.values() for p in v.values()})
    return R, one, two, noreq


# ---------------------------------------------------------------- one-day sweeps
def sweep_frame(lane, tag):
    f, c = read(lane / f"FOR_rolling{tag}.csv"), read(lane / f"FOR_rolling_crit{tag}.csv")
    if f is not None:
        f = f.sort_values(["now", "angle_deg"])
    return f, c


def sweep_areas(f, steps):
    return np.array([area(1000 * g.P, 1000 * g.Q) if len(g) else np.nan
                     for g in (f[f.now == n] for n in steps)])


def check_sweep(ck, lanes, lane, tag, ref_tag, R, cid):
    sw = R["sweeps"]
    steps = list(range(1, len(sw["time"]) + 1))
    case, pc, cr = sw["cases"][cid], sw["per_case"][cid], sw["crit"][cid]
    ck.add("finished", "PASS" if finished(lane, tag) else "DIFF", "done file with Return value = 0")
    check_settings(ck, lane, tag, ref_tag, case.get("FAIR_settings_line"))
    f, c = sweep_frame(lane, tag)
    ok = f.status.isin(OK)
    ck.count("directional solves / optimal", [len(f), int(ok.sum())], [12 * len(steps)] * 2)
    full = f.groupby("now").angle_deg.count().reindex(steps).fillna(0).eq(12).all()
    if not full:
        ck.add("12 directions at every step", "DIFF", "incomplete FOR")
        return
    # boundary points as deviations from the all-idle exchange of the reference
    idle = sw["idle_exchange"]
    dP = 1000 * f.P.to_numpy().reshape(len(steps), 12) - np.asarray(idle["P_kW"], float)[:, None]
    dQ = 1000 * f.Q.to_numpy().reshape(len(steps), 12) - np.asarray(idle["Q_kvar"], float)[:, None]
    poly = np.asarray(pc["polygons"], float)
    at_pt = lambda k: f"{sw['time'][k // 12]} (step {k // 12 + 1}), {30 * (k % 12)} deg"
    at_st = lambda k: f"{sw['time'][k]} (step {k + 1})"
    ck.num("boundary points dP (12 x 48)", dP, poly[:, :, 0], TOL["kW"], 0.01, "kW", at_pt)
    ck.num("boundary points dQ (12 x 48)", dQ, poly[:, :, 1], TOL["kW"], 0.01, "kvar", at_pt)
    A = sweep_areas(f, steps)
    ref_area = np.asarray(sw["per_case"]["ref"]["area_kWkvar"], float)
    ck.num("FOR area per step", A, pc["area_kWkvar"], TOL["ratio"] * ref_area, 0.05, "kW*kvar", at_st)
    # area ratio to the reference run of the same set, found in the lanes
    for key, den_cid, stats in (("area_ratio", "ref", "area_ratio_stats"),
                                ("area_ratio_vs_ref_oldfloor", "ref_oldfloor", "area_ratio_stats_vs_ref_oldfloor")):
        if key not in pc:
            continue
        den_tag = sw["cases"][den_cid]["source_tag"]
        dl, dt = lanes.partner(den_tag, "FOR_rolling", lane)
        name = f"area ratio vs {den_tag[len('_REF_SWEEP_free_today_a2x4p8fin_TR4'):]}"
        if dl is None:
            ck.skip(name, f"{den_tag} not in the lanes")
            continue
        df, _ = sweep_frame(dl, dt)
        ratio = A / sweep_areas(df, steps)
        ck.num(name + " per step", ratio, pc[key], TOL["ratio"], at=at_st)
        ck.num(name + " mean", np.nanmean(ratio), sw["summary"][stats][cid]["mean"], TOL["ratio"], 5e-5)
    if c is None:
        ck.add("FOR_rolling_crit", "DIFF", "file missing")
        return
    ck.count("crit rows optimal", int(c.status.isin(OK).sum()), len(c))
    for ang in (0, 180):
        x = c[c.angle_deg.round() == ang].groupby("now")[["sum_dP_kW", "sum_U_kW", "sum_D_kW"]].sum().reindex(steps)
        for col, lab in (("sum_U_kW", "sum U"), ("sum_D_kW", "sum D"), ("sum_dP_kW", "sum dP^b")):
            ck.num(f"fleet {lab} at {ang} deg", x[col], cr[f"deg{ang}"]["fleet"][col], TOL["kW"], 5e-4, "kW", at_st)
    s = c.groupby(["now", "angle_deg"]).agg(n_cyc=("n_cyc", "sum"), cyc=("cyc_kW", "sum"), thr=("thr_kW", "sum"),
                                            up=("box_up_viol_kW", "max"), dn=("box_dn_viol_kW", "max")).reset_index()
    simul = s.groupby("now").n_cyc.apply(lambda v: int((v > 0).sum())).reindex(steps).fillna(0).astype(int)
    muf = {m["source_tag"]: m["id"] for m in R["muf"]["cases"]}
    if ref_tag in muf:
        ps = R["muf"]["per_step"][muf[ref_tag]]
        ck.count("simultaneous charge/discharge solves per step", simul.to_numpy(), np.asarray(ps["simultaneous_solves"]))
        ck.num("throughput per step (mean of 12 solves)", s.groupby("now").thr.mean().reindex(steps), ps["throughput_kW_mean"],
               TOL["kW"], 0.005, "kW", at_st)
    ml = sw["summary"]["muf_limits"].get(cid)
    if ml:
        ck.count("simultaneous charge/discharge solves", int(simul.sum()), ml["simultaneous_solves"])
        ck.num("largest simultaneous power", s.cyc.max(), ml["simultaneous_kW_max"], TOL["kW"], 0.005, "kW")
        ck.num("mean throughput", s.thr.mean(), ml["throughput_kW_mean"], TOL["kW"], 0.005, "kW")
        ck.count("solves exceeding the limits by > 1 W", int(((s.up > 1e-3) | (s.dn > 1e-3)).sum()),
                 ml["solves_exceeding_limits_by_1W"])
    for fl, m in R["t5"]["mixing_180deg"]["one_day_FOR"].items():
        if m["source_tag"] == ref_tag:
            a = c[c.status.isin(OK) & (c.angle_deg.round() == 180)]
            ck.count("HP groups mixed at 180 deg (> 1e-3) / of", [int(((a.zu > 1e-3) & (a.zd > 1e-3)).sum()), len(a)],
                     [m["mixed"], m["of"]])
            ck.count("HP groups mixed at 180 deg (> 1e-6)", int(((a.zu > 1e-6) & (a.zd > 1e-6)).sum()), m["count_at_1e-6"],
                     soft=True)


# ---------------------------------------------------------------- two-day service runs
def for_slots(lane, tag, slots):
    """FOR_rolling of a run -> {slot: frame of 12 directions}; slot = target (+48 when built the day before)."""
    f = read(lane / f"FOR_rolling{tag}.csv")
    if f is None:
        return {}
    f["slot"] = np.where(f.target < f.now, f.target + 48, f.target)
    return {int(s): g.sort_values("angle_deg") for s, g in f.groupby("slot") if int(s) in slots}


def import_blocks(lane, tag, plane, ptag):
    ex, rf = two_days(lane, tag, "SCT_exec"), two_days(plane, ptag, "SCT_exec")
    m = ex.merge(rf[["now", "battery", "imp1_kWh"]], on=["now", "battery"], suffixes=("", "_ref"))
    if len(m) != len(ex) or len(m) != len(rf):
        return None
    m["dimp"] = m.imp1_kWh - m.imp1_kWh_ref
    bats = sorted(m.battery.unique())
    side = lambda x: x.groupby("battery").dimp.sum().reindex(bats).fillna(0.0)
    return side(m[m.svc == 1]), side(m[m.svc != 1])


def block_checks(ck, label, s, ref, keys):
    """keys: (count >1 Wh, count >10 Wh, fleet kWh, worst kWh, worst Wh) field names of the reference block (None = absent)."""
    c1, c10, tot, worst_kwh, worst_wh = keys
    worst = ref[worst_kwh] if worst_kwh and ref.get(worst_kwh) is not None else \
        (ref[worst_wh] / 1000 if worst_wh and ref.get(worst_wh) is not None else None)
    soft = worst is not None and worst < NOISE_KWH
    if c1:
        ck.count(f"{label}: prosumers > 1 Wh", int((s > 1e-3).sum()), ref[c1], soft=soft)
    if c10:
        ck.count(f"{label}: prosumers > 10 Wh", int((s > 1e-2).sum()), ref[c10], soft=soft)
    if tot and ref.get(tot) is not None:
        ck.num(f"{label}: fleet total", s.sum(), ref[tot], TOL["kWh"], 0.0005, "kWh")
    if worst is not None:
        ck.num(f"{label}: worst prosumer", s.max(), worst, TOL["kWh"], 0.0005, "kWh")


def check_service(ck, lanes, lane, tag, ref_tag, R, src):
    svc, t5, g = R["svc"], R["t5"], R["guar"]
    ck.add("finished", "PASS" if finished(lane, tag) else "DIFF", "done file with Return value = 0")
    check_settings(ck, lane, tag, ref_tag)
    fq = read(lane / f"FRQ{tag}.csv")
    if fq is None:
        ck.add("FRQ file", "DIFF", "missing")
        return
    fq = fq.sort_values("target")
    served = DT * float((-fq.dP_kW).clip(lower=0).sum())
    sv = read(lane / f"FOR_rolling_svc{tag}.csv")
    executed = 0 if sv is None else int((sv.event == "execute").sum())
    sc = svc["cases"][src["svc"][0]] if "svc" in src else None
    tc = t5["summary"][src["t5"][0]] if "t5" in src else None
    gc = g[src["guar"][0]] if "guar" in src else None
    for nm, ref in (("service_requests.json", sc), ("service_T5.json", tc), ("guarantee.json", gc)):
        if ref is None:
            continue
        n_ref = ref.get("requests", ref.get("requests_served"))
        ck.count(f"requests served [{nm}]", len(fq), n_ref)
        e_ref = ref["export_served_kWh"]
        ck.num(f"export served [{nm}]", served, e_ref, TOL["kWh"], 0.005 if nm == "guarantee.json" else 0.05, "kWh")
    at_rq = lambda k: f"request {k + 1} (slot {int(fq.target.iloc[k])})"
    if sc:
        ck.count("requests executed", executed, sc["requests_executed"])
        ck.num("requested dP from the P1 baseline per request", fq.dP_kW, [p[0] for p in sc["service_vs_p1_baseline"]],
               TOL["kW"], 0.005, "kW", at_rq)
    if "t5" in src:
        ck.num("requested dP per request [service_T5.json]", fq.dP_kW, t5["per_request"][src["t5"][0]]["dP_kW"], TOL["kW"],
               0.005, "kW", at_rq)
    # FOR of the requested slots
    if sc:
        slots = svc["slots"]
        F = for_slots(lane, tag, slots)
        if sorted(F) != slots or any(len(x) != 12 for x in F.values()):
            ck.add("FOR at every requested slot (12 directions)", "DIFF", f"slots found {sorted(F)}")
        else:
            ck.count("FOR solves not optimal", sum(int((~x.status.isin(OK)).sum()) for x in F.values()), sc["non_optimal_solves"])
            A = np.array([area(1000 * F[t].P, 1000 * F[t].Q) for t in slots])
            at_sl = lambda k: f"slot {slots[k]} ({svc['times'][k]})"
            at_pt = lambda k: f"slot {slots[k // 12]} ({svc['times'][k // 12]}), {30 * (k % 12)} deg"
            ck.num("FOR area per requested slot", A, sc["area"], TOL["ratio"] * np.asarray(sc["area"], float), 0.5, "kW*kvar", at_sl)
            idle = R["time"]["slots"]
            BP = np.array([idle[t - 1]["idle_exchange_kW"] for t in slots])[:, None]
            BQ = np.array([idle[t - 1]["idle_exchange_kvar"] for t in slots])[:, None]
            poly = np.asarray(sc["polygons"], float)
            dP = np.array([1000 * F[t].P.to_numpy() for t in slots]) - BP
            dQ = np.array([1000 * F[t].Q.to_numpy() for t in slots]) - BQ
            ck.num("boundary points dP (12 x 28)", dP, poly[:, :, 0], TOL["kW"], 0.1, "kW", at_pt)
            ck.num("boundary points dQ (12 x 28)", dQ, poly[:, :, 1], TOL["kW"], 0.1, "kvar", at_pt)
            for key, ar in svc["area_ratios"].items():
                if ar["numerator"] != src["svc"][0]:
                    continue
                den = svc["cases"][ar["denominator"]]
                dtag = den.get("tag") or den["for_run"].split("/", 1)[1]
                dl, dt = lanes.partner(dtag, "FOR_rolling", lane)
                name = f"FOR area ratio vs {ar['denominator']} (%)"
                if dl is None:
                    ck.skip(name, f"{dtag} not in the lanes")
                    continue
                D = for_slots(dl, dt, slots)
                if sorted(D) != slots:
                    ck.skip(name, f"{dtag} has no FOR at every requested slot")
                    continue
                pct = 100 * A / np.array([area(1000 * D[t].P, 1000 * D[t].Q) for t in slots])
                ck.num(name + " per slot", pct, ar["pct"], 100 * TOL["ratio"], 0.005, at=at_sl)
                ck.num(name + " mean", pct.mean(), ar["mean_pct"], 100 * TOL["ratio"], 0.005)
        soc = read(lane / f"FOR_rolling_soc{tag}.csv")
        m = soc.groupby("now").SOC_start.mean().reindex(range(1, 49))
        ck.num("mean SOC at the start of each day-1 slot", 100 * m, sc["soc_mean_pct_day1"], TOL["pp"], 0.005, "%")
    # extra house import against the no-request run
    ptags = {p[1] for p in src.values()}
    for ptag in sorted(ptags):
        pl, pt = lanes.partner(ptag, "SCT_exec", lane)
        if pl is None:
            ck.skip(f"extra import vs {ptag}", "no-request run not in the lanes")
            continue
        blocks = import_blocks(lane, tag, pl, pt)
        if blocks is None:
            ck.add(f"extra import vs {ptag}", "DIFF", "SCT_exec rows do not match the no-request run")
            continue
        w, o = blocks
        s_run, s_ref = two_days(lane, tag, "FOR_rolling_soc"), two_days(pl, pt, "FOR_rolling_soc")
        pre = lambda s: s[s.now < FIRST_REQUEST].set_index(["now", "battery"]).SOC_start
        gap = float((pre(s_run) - pre(s_ref).reindex(pre(s_run).index)).abs().max())
        ck.num("SOC before the first request vs the no-request run", gap, 0.0, 1e-6)
        for nm, (key, p) in src.items():
            if p != ptag:
                continue
            if nm == "svc":
                ei = svc["cases"][key]["extra_import"]
                k = ("prosumers_above_1Wh", "prosumers_above_10Wh", "fleet_total_kWh", "worst_kWh", None)
                block_checks(ck, "inside requested half-hours [service_requests.json]", w, ei["inside_requested_halfhours"], k)
                block_checks(ck, "outside requested half-hours [service_requests.json]", o, ei["outside_requested_halfhours"], k)
            elif nm == "t5":
                sm = t5["summary"][key]
                ck.count("requested half-hours in SCT_exec", int(two_days(lane, tag, "SCT_exec").query("svc == 1").now.nunique()),
                         sm["requested_halfhours_in_exec_log"])
                block_checks(ck, "inside requested half-hours [service_T5.json]", w, sm,
                             ("prosumers_buying_more_inside", "prosumers_buying_more_inside_by_10Wh",
                              "fleet_extra_purchase_inside_kWh", "worst_prosumer_inside_kWh", None))
                block_checks(ck, "outside requested half-hours [service_T5.json]", o, sm,
                             (None, None, "fleet_extra_purchase_outside_kWh", None, "worst_prosumer_outside_Wh"))
            else:
                gk = g[key]
                k = ("prosumers_above_1Wh", None, "total_kWh", "worst_kWh", None)
                block_checks(ck, "inside requested half-hours [guarantee.json]", w, gk["extra_import_inside_requested"], k)
                block_checks(ck, "outside requested half-hours [guarantee.json]", o, gk["extra_import_outside_requested"], k)
                req = sorted(int(x) for x in two_days(lane, tag, "SCT_exec").query("svc == 1").now.unique())
                p_run = s_run.groupby("now").P_PCC1.first().reindex(req)
                p_ref = s_ref.groupby("now").P_PCC1.first().reindex(req)
                ck.num("realised extra export vs the no-request run", DT * 1000 * float((p_ref - p_run).sum()),
                       gk["export_vs_no_request_realised_kWh"], TOL["kWh"], 0.005, "kWh")
                ck.num("mean SOC at the start of day-1 23:30", 100 * s_run.loc[s_run.now == 48, "SOC_start"].mean(),
                       gk["mean_soc_end_day1_pct"], TOL["pp"], 0.005, "%")
    for fl, m in t5["mixing_180deg"]["two_day_service"].items():
        if m["source_tag"] == ref_tag:
            c = read(lane / f"FOR_rolling_crit{tag}.csv")
            a = c[c.status.isin(OK) & (c.angle_deg.round() == 180)]
            ck.count("HP groups mixed at 180 deg (> 1e-3) / of", [int(((a.zu > 1e-3) & (a.zd > 1e-3)).sum()), len(a)],
                     [m["mixed"], m["of"]])
            ck.count("HP groups mixed at 180 deg (> 1e-6)", int(((a.zu > 1e-6) & (a.zd > 1e-6)).sum()), m["count_at_1e-6"],
                     soft=True)


def check_noreq(ck, lane, tag, ref_tag, R):
    ck.add("finished", "PASS" if finished(lane, tag) else "DIFF", "done file with Return value = 0")
    fq = read(lane / f"FRQ{tag}.csv")
    ck.count("requests", 0 if fq is None else len(fq), 0)
    nr = R["svc"]["cases"]["no_request"]
    if nr["trajectory_run"].split("/", 1)[1] == ref_tag:
        soc = read(lane / f"FOR_rolling_soc{tag}.csv")
        m = soc.groupby("now").SOC_start.mean().reindex(range(1, 49))
        ck.num("mean SOC at the start of each day-1 slot", 100 * m, nr["soc_mean_pct_day1"], TOL["pp"], 0.005, "%")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=str(REPO.parent / "paper1-runs"))
    ap.add_argument("--lanes", nargs="*")
    ap.add_argument("--ref", default=str(REPO / "results" / "paper1-fairness-2026-10"))
    ap.add_argument("--verbose", "-v", action="store_true")
    a = ap.parse_args()
    work, ref = Path(a.work), Path(a.ref)
    paths = [work / l for l in a.lanes] if a.lanes else sorted(p for p in work.iterdir() if p.is_dir() and any(p.glob("FOR_rolling*.csv")))
    lanes = Lanes(paths)
    R, one, two, noreq = load_reference(ref)
    print(f"REFERENCE {ref}: {len(one)} one-day sweeps, {len(two)} service runs, {len(noreq)} no-request runs")
    print(f"LANES     {work}: {', '.join(p.name for p in paths) or 'none'}\n")
    results, missing = [], []
    jobs = [(t, "1-day", "FOR_rolling") for t in one] + [(t, "service", "SCT_exec") for t in two] + \
           [(t, "no-request", "SCT_exec") for t in noreq]
    for ref_tag, kind, stem in jobs:
        hits = lanes.find(ref_tag, stem)
        if not hits:
            missing.append((ref_tag, kind))
            continue
        for lane, tag in hits:
            ck = Checks()
            try:
                if kind == "1-day":
                    check_sweep(ck, lanes, lane, tag, ref_tag, R, one[ref_tag])
                elif kind == "service":
                    check_service(ck, lanes, lane, tag, ref_tag, R, two[ref_tag])
                else:
                    check_noreq(ck, lane, tag, ref_tag, R)
            except Exception as e:            # a malformed or partial run must not hide the others
                ck.add("reading the run", "DIFF", f"{type(e).__name__}: {e}")
            results.append((lane.name, kind, tag, ck))
    if not results:
        print("No reference run found in the lanes.")
    else:
        print(f"{'lane':6s} {'kind':10s} {'status':8s} {'checks':>7s}  run tag")
        for ln, kind, tag, ck in results:
            n_ok = sum(r[1] == "PASS" for r in ck.rows)
            n = sum(r[1] in ("PASS", "DIFF") for r in ck.rows)
            print(f"{ln:6s} {kind:10s} {ck.status():8s} {n_ok:3d}/{n:<3d}  {tag}")
    for ln, kind, tag, ck in results:
        rows = ck.rows if a.verbose else [r for r in ck.rows if r[1] != "PASS"]
        if rows:
            print(f"\n{ln} {tag}")
            for name, state, detail in rows:
                print(f"  {state:5s} {name}: {detail}")
    if missing:
        qt = queue_tags()
        print("\nMISSING (reference runs not found in the lanes; the queue line that makes them with the current model):")
        for t, kind in missing:
            if DIAGNOSTIC in t:
                note = "made with a diagnostic copy of PV2_Run (SCAlpha read from scenario.txt): not reproducible from the repository"
            else:
                q = qt.get(t) or qt.get(t + ALIAS)
                note = (f"in {q}" if q else "in no queue") + f"; run: {job_line(t)}"
                if q and expected_effhead(t) == 0 and not t.startswith("_REF_free"):
                    note += "  (FairEffHead=0 added: the queue line predates the energy-floor default)"
            print(f"  {kind:10s} {t}\n             {note}")
    n_diff = sum(ck.status() == "DIFF" for *_, ck in results)
    print(f"\n{len(results)} runs checked: {sum(ck.status() == 'PASS' for *_, ck in results)} PASS, "
          f"{sum(ck.status() == 'PARTIAL' for *_, ck in results)} PARTIAL, {n_diff} DIFF; {len(missing)} reference runs missing")
    return 2 if not results else (1 if n_diff else 0)


if __name__ == "__main__":
    sys.exit(main())
