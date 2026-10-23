"""Record one finished case-study run in the repository (and zip its raw outputs for the shared cloud folder).

For a job that ran with scripts/paper1/run_paper1.py (lane folder with record<tag>.json):
  results/case-study/records/<run_id>.json   the run record (code commit, input hashes, settings, computer, times,
                                             output hashes) + who collected it + the raw zip's name and SHA-256
  results/case-study/summary/<run_id>/       compact files for the figures (see SUMMARY below)
  <raw-dir>/<run_id>.zip                     every output file of the job, for the shared cloud folder (NOT in Git)
  results/case-study/runs.csv                the register, rebuilt from all records (never edited by hand)

Run id: CS-<run>-<network>-<variant>-r<n>, derived from the tag unless --run-id is given, e.g. CS-A-TR4-REF-r1,
CS-A-ALL-HPi-r1 (HP within each aggregator), CS-A-TR9-HPn-r1 (HP network-wide), CS-B25-TR4-REF-r1. A new run of the same
case gets the next r<n>: nothing is ever overwritten.

Usage (from the repository root):
  python scripts/paper1/case_study/collect_run.py <lane folder> <tag> --who Tulio [--raw-dir DIR] [--note "..."]
  python scripts/paper1/case_study/collect_run.py --all <work folder> --who Tulio      # every finished job not yet collected
  python scripts/paper1/case_study/collect_run.py --rebuild-register
A run made from a working tree with uncommitted changes is refused unless --allow-dirty (then flagged in the register).
"""
import argparse
import csv
import hashlib
import json

import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RES = REPO / "results" / "case-study"
REC, SUM = RES / "records", RES / "summary"
SUMMARY = {   # output stem in the lane -> file in summary/<run_id>/ (copied as is: small)
    "FOR_rolling": "for_corners.csv", "FOR_rolling_crit": "fairness_criteria.csv", "FOR_rolling_fair": "fairness_groups.csv",
    "FRQ": "requests.csv", "FOR_rolling_svc": "service.csv", "SPDtime": "time_per_step.csv",
}


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def rd(p):
    d = pd.read_csv(p, skipinitialspace=True, encoding="utf-8-sig")
    d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if pd.api.types.is_object_dtype(d[c]) or pd.api.types.is_string_dtype(d[c]):
            d[c] = d[c].astype(str).str.strip()
    return d


def variant(extra):
    crit = {"0": "REF", "1": "CP", "2": "HP", "3": "HB"}[extra.get("FairCrit", "0")]
    v = crit if crit == "REF" else crit + {"1": "i", "2": "n"}[extra.get("FairScope", "1")]
    if crit == "HB":
        v += "e" + extra.get("FairEps", "0").replace(".", "")
    if float(extra.get("SCAlpha", "0")) > 0:
        v += "-noSC"
    if extra.get("ACAudit", "0") == "1":
        v += "-ac"
    return v


def default_run_id(rec):
    f = rec["job_line"].split()
    sid, net = f[0], next((x for x in f[3:] if "=" not in x), "TR4")
    extra = dict(x.split("=", 1) for x in f[3:] if "=" in x)
    run = {"CS_A": "A"}.get(sid) or (("B" + sid.split("_t")[1]) if sid.startswith("CS_B_t") else sid.replace("_", ""))
    base = f"CS-{run}-{net.replace(',', '')}-{variant(extra)}"
    n = 1
    while (REC / f"{base}-r{n}.json").exists():
        n += 1
    return f"{base}-r{n}"


def summarize(lane, tag, out):
    out.mkdir(parents=True, exist_ok=True)
    for stem, name in SUMMARY.items():
        f = lane / f"{stem}{tag}.csv"
        if f.exists() and f.stat().st_size > 0 and len(f.read_text(errors="ignore").splitlines()) > 1:
            out.joinpath(name).write_bytes(f.read_bytes())
    ex = lane / f"SCT_exec{tag}.csv"
    if ex.exists():
        e = rd(ex)
        for c in ("now", "svc", "soc_start", "imp1_kWh", "exp1_kWh", "batt1_kWh", "pv1_kWh"):
            if c in e:
                e[c] = pd.to_numeric(e[c], errors="coerce")
        fleet = e.groupby("now").agg(batteries=("battery", "size"), soc_mean=("soc_start", "mean"),
                                     imports_kWh=("imp1_kWh", "sum"), exports_kWh=("exp1_kWh", "sum"),
                                     battery_kWh=("batt1_kWh", "sum"), pv_kWh=("pv1_kWh", "sum"),
                                     service=("svc", "max")).reset_index()
        soc = lane / f"FOR_rolling_soc{tag}.csv"
        if soc.exists():
            s = rd(soc)
            pcc = s.groupby(s.now.astype(int))[["P_PCC1", "Q_PCC1"]].first().astype(float) * 1000
            fleet = fleet.merge(pcc.rename(columns={"P_PCC1": "pcc_P_kW", "Q_PCC1": "pcc_Q_kvar"}), left_on="now",
                                right_index=True, how="left")
        fleet.to_csv(out / "fleet_by_step.csv", index=False, float_format="%.6f")
        pro = e.groupby("battery").agg(imports_kWh=("imp1_kWh", "sum"), exports_kWh=("exp1_kWh", "sum"),
                                       soc_first=("soc_start", "first"), soc_last=("soc_start", "last")).reset_index()
        pro.to_csv(out / "prosumer_day.csv", index=False, float_format="%.6f")
    info = lane / f"SCT_info{tag}.txt"
    if info.exists():
        out.joinpath("info.txt").write_bytes(info.read_bytes())


def collect(lane, tag, who, raw_dir, note, run_id=None, allow_dirty=False):
    rec_file = lane / f"record{tag}.json"
    if not rec_file.exists():
        sys.exit(f"{rec_file} not found: was the job run with the case-study runner?")
    rec = json.loads(rec_file.read_text())
    if not rec["ok"]:
        sys.exit(f"{tag}: the run did not end with 'Return value = 0' ({rec['return_line']}); not collected")
    dirty = bool((rec.get("prepare_info") or {}).get("git", {}).get("dirty", True))
    if dirty and not allow_dirty:
        sys.exit(f"{tag}: prepared from a working tree with uncommitted changes (or without prepare_info); "
                 "re-run from a clean commit, or pass --allow-dirty (flagged in the register)")
    for old in REC.glob("*.json"):
        o = json.loads(old.read_text())
        if o.get("tag") == tag and o.get("start") == rec["start"]:
            sys.exit(f"{tag} (started {rec['start']}) is already collected as {old.stem}")
    run_id = run_id or default_run_id(rec)
    if (REC / f"{run_id}.json").exists():
        sys.exit(f"{run_id} exists: nothing is overwritten; use the next r<n>")
    raw_dir.mkdir(parents=True, exist_ok=True)
    zpath = raw_dir / f"{run_id}.zip"
    files = sorted(set(lane.glob(f"*{tag}*")) | {lane / "prepare_info.json"})
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if f.is_file():
                z.write(f, f.name)
    summarize(lane, tag, SUM / run_id)
    rec.update(run_id=run_id, collected_by=who, collected=f"{datetime.now():%Y-%m-%d %H:%M:%S}", note=note,
               raw_zip={"file": zpath.name, "sha256": sha16(zpath), "bytes": zpath.stat().st_size},
               summary_files=sorted(p.name for p in (SUM / run_id).iterdir()))
    REC.mkdir(parents=True, exist_ok=True)
    (REC / f"{run_id}.json").write_text(json.dumps(rec, indent=1))
    print(f"collected {tag} as {run_id}; raw outputs -> {zpath} ({zpath.stat().st_size / 1e6:.1f} MB): upload it to the "
          f"shared folder CaseStudy/raw/")
    return run_id


def rebuild_register():
    rows = []
    for f in sorted(REC.glob("*.json")):
        r = json.loads(f.read_text())
        g = (r.get("prepare_info") or {}).get("git", {})
        c = r.get("computer", {})
        rows.append({"run_id": r["run_id"], "collected_by": r.get("collected_by", ""), "job_line": r["job_line"],
                     "commit": g.get("commit", "")[:10], "dirty": int(bool(g.get("dirty", True))),
                     "model_sha256": (r.get("prepare_info") or {}).get("files_sha256", {}).get("MainProject/OPF.ams", ""),
                     "start": r["start"], "end": r["end"], "wall_min": r["wall_min"], "ok": int(r["ok"]),
                     "host": c.get("host", ""), "cpu": c.get("cpu", ""), "ram_gb": c.get("ram_gb", ""),
                     "raw_zip": r.get("raw_zip", {}).get("file", ""), "raw_sha256": r.get("raw_zip", {}).get("sha256", ""),
                     "note": r.get("note", "")})
    RES.mkdir(parents=True, exist_ok=True)
    with open(RES / "runs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["run_id"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"register: {len(rows)} runs -> {RES / 'runs.csv'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lane", nargs="?")
    ap.add_argument("tag", nargs="?")
    ap.add_argument("--who")
    ap.add_argument("--run-id")
    ap.add_argument("--note", default="")
    ap.add_argument("--raw-dir", default=str(REPO.parent / "case-study-raw"))
    ap.add_argument("--all", metavar="WORK", help="collect every finished job in the lanes of this work folder")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--rebuild-register", action="store_true")
    ap.add_argument("--results", help="results folder (default results/case-study; another folder for tests)")
    a = ap.parse_args()
    if a.results:
        global RES, REC, SUM
        RES = Path(a.results)
        REC, SUM = RES / "records", RES / "summary"
    if not a.rebuild_register:
        if not a.who:
            sys.exit("--who is required (Tulio or Nacho)")
        if a.all:
            done = {json.loads(f.read_text()).get("tag") + json.loads(f.read_text()).get("start", "") for f in REC.glob("*.json")}
            for rf in sorted(Path(a.all).glob("*/record_*.json")):
                r = json.loads(rf.read_text())
                if r["ok"] and r["tag"] + r["start"] not in done:
                    collect(rf.parent, r["tag"], a.who, Path(a.raw_dir), a.note, allow_dirty=a.allow_dirty)
        else:
            if not (a.lane and a.tag):
                sys.exit("give <lane folder> <tag>, or --all <work folder>")
            collect(Path(a.lane), a.tag, a.who, Path(a.raw_dir), a.note, a.run_id, a.allow_dirty)
    rebuild_register()


if __name__ == "__main__":
    main()
