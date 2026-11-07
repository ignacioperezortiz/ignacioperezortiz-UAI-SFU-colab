"""Self-consumption guarantee metrics for paper-1 two-day runs (TSO export requests vs the no-request run).

Given the run WITH the self-consumption guarantee, optionally the run with the guarantee RELAXED, and the
no-request run (P1 baselines only), it computes for each run:

  export served      sum over the requested flexibility slots of the requested extra export, measured from the
                     P1-baseline point of the same step:  dt * sum(max(0, -(req_P - S0_P)))   [kWh]
                     (FRQ<tag>.csv columns dP_kW = req_P_kW - S0_P_kW; same definition as analyze_paper1.py
                     export_more_kWh). A second, realised figure is also given: the extra export at the interface
                     against the no-request run in the same half-hours, dt * sum(P_noreq - P_run) from
                     FOR_rolling_soc (P_PCC1).
  extra import       per prosumer, grid import of the run minus grid import of the no-request run (SCT_exec
                     imp1_kWh, both days), split into the requested half-hours (rows with svc = 1 in the run) and all
                     other half-hours. Counted "above 1 Wh" when > 0.001 kWh. Totals are fleet sums, worst is the
                     maximum over prosumers.

Run tags are looked up in the lanes <runs>/N1..N3 (--runs, see paths.py; the lane holding
done_<tag>.txt with "Return value = 0"); a lane can be forced with LANE/TAG, e.g. N3/_WC_EXPORT_..._SCAlpha0.
Day-2 files end with _d2; slot index = now (day 1) and now + 48 (day 2).

Usage (writes into <out>/data):
  python guarantee_metrics.py --on TAG [--relaxed TAG] --ref TAG [--runs DIR] [--out DIR]     # guarantee.json
  python guarantee_metrics.py --validate           # reproduces the known figures, writes guarantee_validation.json
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

RUNS = None                                   # folder of the lanes (--runs), set in main()
LANES = ("N1", "N2", "N3")
OUT = None                                    # <out>/data, set in main()
DT = 0.5          # h per slot
ONE_WH = 1e-3     # kWh


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


def finished(lane, tag):
    f = lane / f"done{tag}.txt"
    return f.exists() and "Return value = 0" in f.read_text(errors="ignore")


def locate(spec):
    """'TAG' or 'LANE/TAG' -> (lane Path, tag). Raises if not finished or ambiguous."""
    if "/" in spec or "\\" in spec:
        lane, tag = re.split(r"[\\/]", spec, maxsplit=1)
        lane = RUNS / lane
        if not finished(lane, tag):
            raise SystemExit(f"run {spec} is not finished (no 'Return value = 0' in done{tag}.txt)")
        return lane, tag
    hits = [RUNS / l for l in LANES if finished(RUNS / l, spec)]
    if not hits:
        raise SystemExit(f"run {spec} not finished in any lane {LANES}")
    if len(hits) > 1:
        raise SystemExit(f"run {spec} finished in several lanes {[h.name for h in hits]}: use LANE/TAG")
    return hits[0], spec


def two_days(lane, tag, stem):
    a, b = read(lane / f"{stem}{tag}.csv"), read(lane / f"{stem}{tag}_d2.csv")
    if a is None or b is None:
        raise SystemExit(f"missing {stem}{tag}.csv or its _d2 in {lane}")
    b = b.copy()
    b["now"] = b["now"] + 48
    return pd.concat([a, b], ignore_index=True)


def aggregator_map():
    """battery -> aggregator, from any per-battery offer log (static mapping of the 46 prosumers)."""
    for l in LANES:
        for f in sorted((RUNS / l).glob("FOR_rolling_offer_*.csv")):
            if f.stat().st_size > 1000:
                d = pd.read_csv(f, skipinitialspace=True, encoding="utf-8-sig", usecols=lambda c: c.strip() in ("battery", "aggregator"))
                d.columns = [c.strip() for c in d.columns]
                d = d.apply(lambda s: s.astype(str).str.strip())
                return d.drop_duplicates("battery").set_index("battery")["aggregator"].to_dict()
    return {}


# ---------------------------------------------------------------- metrics
def metrics(run_spec, ref_spec, agg):
    lane, tag = locate(run_spec)
    rlane, rtag = locate(ref_spec)
    ex, ref = two_days(lane, tag, "SCT_exec"), two_days(rlane, rtag, "SCT_exec")
    m = ex.merge(ref[["now", "battery", "imp1_kWh"]], on=["now", "battery"], suffixes=("", "_ref"), validate="one_to_one")
    if len(m) != len(ex) or len(m) != len(ref):
        raise SystemExit(f"SCT_exec rows do not match: run {len(ex)}, ref {len(ref)}, joined {len(m)}")
    m["dimp"] = m["imp1_kWh"] - m["imp1_kWh_ref"]
    inside = m[m["svc"] == 1]
    outside = m[m["svc"] != 1]
    req_slots = sorted(int(x) for x in inside["now"].unique())
    bats = sorted(m["battery"].unique())
    w = inside.groupby("battery")["dimp"].sum().reindex(bats).fillna(0.0)
    o = outside.groupby("battery")["dimp"].sum().reindex(bats).fillna(0.0)

    fq = read(lane / f"FRQ{tag}.csv")
    n_req = 0 if fq is None else len(fq)
    served = 0.0 if fq is None else DT * float((-fq["dP_kW"]).clip(lower=0).sum())

    # realised extra export at the interface vs the no-request run, in the requested half-hours
    soc, rsoc = two_days(lane, tag, "FOR_rolling_soc"), two_days(rlane, rtag, "FOR_rolling_soc")
    pr = soc.groupby("now")["P_PCC1"].first()
    pr0 = rsoc.groupby("now")["P_PCC1"].first()
    realised = DT * 1000 * float((pr0.reindex(req_slots) - pr.reindex(req_slots)).sum())

    info = "\n".join((lane / f"SCT_info{tag}{s}.txt").read_text(errors="ignore")
                     for s in ("", "_d2") if (lane / f"SCT_info{tag}{s}.txt").exists())
    # consistency: before the first request the run must follow the no-request trajectory exactly
    pre = [t for t in range(1, (req_slots[0] if req_slots else 49))]
    a = soc[soc["now"].isin(pre)].set_index(["now", "battery"])["SOC_start"]
    b = rsoc[rsoc["now"].isin(pre)].set_index(["now", "battery"])["SOC_start"]
    pre_gap = float((a - b.reindex(a.index)).abs().max()) if len(a) else float("nan")
    if not pre_gap < 1e-6:
        print(f"WARNING {tag}: before the first request the SOC differs from the no-request run by {pre_gap:.2e}")
    soc_end_d1 = 100 * float(soc.loc[soc["now"] == 48, "SOC_start"].mean())
    soc_end_d1_ref = 100 * float(rsoc.loc[rsoc["now"] == 48, "SOC_start"].mean())

    def block(s):
        return {
            "prosumers_above_1Wh": int((s > ONE_WH).sum()),
            "total_kWh": round(float(s.sum()), 4),
            "worst_kWh": round(float(s.max()), 4),
            "worst_prosumer": str(s.idxmax()),
        }

    return {
        "tag": tag,
        "lane": lane.name,
        "requests_served": n_req,
        "requested_slots": req_slots,
        "export_served_kWh": round(served, 2),
        "export_vs_no_request_realised_kWh": round(realised, 2),
        "extra_import_inside_requested": block(w),
        "extra_import_outside_requested": block(o),
        "released_services_EXECFAIL": info.count("EXECFAIL"),
        "pre_request_max_soc_gap_vs_no_request": pre_gap,
        "mean_soc_end_day1_pct": round(soc_end_d1, 2),
        "mean_soc_end_day1_no_request_pct": round(soc_end_d1_ref, 2),
        "per_prosumer": [
            {"prosumer": b, "aggregator": agg.get(b), "inside_kWh": round(float(w[b]), 5), "outside_kWh": round(float(o[b]), 5)}
            for b in bats
        ],
    }


def provenance(spec):
    lane, tag = locate(spec)
    return {"lane": lane.name, "tag": tag}


def compute(on, relaxed, ref):
    agg = aggregator_map()
    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "definitions": {
            "export_served_kWh": "dt * sum over requested flexibility slots of max(0, -(requested P - P1-baseline P)) [FRQ dP_kW]",
            "export_vs_no_request_realised_kWh": "dt * sum over requested slots of (interface P of the no-request run - interface P of the run)",
            "extra_import": "per prosumer, grid import of the run minus that of the no-request run (SCT_exec imp1_kWh, two days)",
            "inside/outside": "half-hours with a TSO request (svc = 1) / all other half-hours of the two days",
            "above_1Wh": "> 0.001 kWh",
            "units": "kWh; dt = 0.5 h",
        },
        "no_request": provenance(ref),
        "guarantee_on": metrics(on, ref, agg),
    }
    if relaxed:
        out["guarantee_relaxed"] = metrics(relaxed, ref, agg)
    return out


def summary_line(label, r):
    i, o = r["extra_import_inside_requested"], r["extra_import_outside_requested"]
    return (f"{label:28s} served {r['requests_served']:2d} req, export {r['export_served_kWh']:8.1f} kWh "
            f"(realised {r['export_vs_no_request_realised_kWh']:8.1f}) | inside: {i['prosumers_above_1Wh']:2d} >1Wh, "
            f"total {i['total_kWh']:+8.3f}, worst {1000 * i['worst_kWh']:+8.1f} Wh | outside: {o['prosumers_above_1Wh']:2d} >1Wh, "
            f"total {o['total_kWh']:+8.3f}, worst {1000 * o['worst_kWh']:+8.1f} Wh")


# ---------------------------------------------------------------- validation
D2 = "_free_today_a2x4p8fin2_TR4"
VALIDATION = [
    # (label, run, ref, expected export kWh, expected inside count, expected worst outside Wh)
    ("HP intra, guarantee on", "N3/_WC_EXPORT" + D2 + "_FairCrit2_FairScope1_RollOfferLog1",
     "N2/_REF" + D2 + "_FairCrit2_FairScope1", 675.2, None, None),
    ("HP intra, guarantee relaxed", "N3/_WC_EXPORT" + D2 + "_FairCrit2_FairScope1_RollOfferLog1_SCAlpha99",
     "N2/_REF" + D2 + "_FairCrit2_FairScope1", 993.0, None, None),
    ("no criterion (older commit), guarantee on", "N2/_WC_EXPORT" + D2 + "_FairBox1",
     "N2/_REF" + D2 + "_FairBox1", 854.3, 0, 2.2),
]


def validate():
    agg = aggregator_map()
    rows = []
    for label, run, ref, e_exp, n_in, wo in VALIDATION:
        r = metrics(run, ref, agg)
        print(summary_line(label, r))
        rows.append({
            "case": label, "run": run, "no_request": ref,
            "export_served_kWh": {"expected": e_exp, "reproduced": r["export_served_kWh"]},
            "inside_above_1Wh": {"expected": n_in, "reproduced": r["extra_import_inside_requested"]["prosumers_above_1Wh"]},
            "worst_outside_Wh": {"expected": wo, "reproduced": round(1000 * r["extra_import_outside_requested"]["worst_kWh"], 2)},
            "inside_worst_Wh": round(1000 * r["extra_import_inside_requested"]["worst_kWh"], 1),
            "inside_total_kWh": r["extra_import_inside_requested"]["total_kWh"],
        })
    (OUT / "guarantee_validation.json").write_text(json.dumps(rows, indent=1))
    print("written", OUT / "guarantee_validation.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--on", help="run tag with the self-consumption guarantee (LANE/TAG or TAG)")
    ap.add_argument("--relaxed", help="run tag with the guarantee relaxed (optional)")
    ap.add_argument("--ref", help="no-request run tag (P1 baselines only)")
    ap.add_argument("--validate", action="store_true")
    paths.add_args(ap, runs=True)
    a = ap.parse_args()
    global RUNS, OUT
    paths.use(a)
    RUNS, OUT = paths.runs_dir(), paths.data_out()
    if a.validate:
        validate()
        return
    if not (a.on and a.ref):
        ap.error("--on and --ref are required (or --validate)")
    out = compute(a.on, a.relaxed, a.ref)
    print(summary_line("guarantee on", out["guarantee_on"]))
    if "guarantee_relaxed" in out:
        print(summary_line("guarantee relaxed", out["guarantee_relaxed"]))
    (OUT / "guarantee.json").write_text(json.dumps(out, indent=1))
    print("written", OUT / "guarantee.json")


if __name__ == "__main__":
    sys.exit(main())
