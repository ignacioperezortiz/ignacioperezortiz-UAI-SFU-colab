"""Paper-1 runs: one AIMMS session per lane, jobs taken from a queue file (headless, AimmsCmd).

Each lane is a full copy of the model (OPF.aimms, MainProject/ and the three input files from the repository root)
in its own folder under the work directory, so several sessions can run at once (one licence seat each). A job is
one simulation: procedure PV2_Run, which reads the scenario.txt this script writes into the lane folder.

Job line (queue file):   <scenario> <case> <speed> [network] [NAME=VALUE ...]
  scenario  a file in scripts/paper1/scenarios/ without .json (REF, R04_sun, EDGE_SUN, WC_EXPORT, WC_IMPORT, ...)
  case      free_today (paper 1: PV always exported, never curtailed)
  speed     a<K>x<T>p<P>fin[2][d][s], e.g. a2x4p8fin2:
              K = FOR directions solved in parallel (RollAsyncK; 0 = one after the other),
              T = CPLEX threads per direction (RollAsyncThreads), P = CPLEX threads for P1 and the network check
              (SPD_P1Threads), fin = the paper-1 settings, fin2 = the same over two days (day 2 without requests),
              d / s = rescue / sweep diagnostics (off in production)
  network   TR1 ... TR9 (that transformer in detail, the others lumped as passive load; default TR4),
            a comma list (TR3,TR4), or ALL = the whole feeder, no reduction, every battery
  NAME=VALUE  any further model parameter, e.g. FairMode=2 (also added to the output tag)

Outputs go to the lane folder, named with the tag _<scenario>_<case>_<speed>[_<network>][_<NAME><VALUE>...];
day-2 files end in _d2. A job is skipped when a done file with "Return value = 0" exists in any lane, or when
another lane has claimed it (runs/claims/<tag>.claim; delete the claim to run it again).

Usage (from the repository root):
  python scripts/paper1/run_paper1.py prepare L1 L2 L3            # copy the model into <work>/L1 ...
  python scripts/paper1/run_paper1.py lane L1 scripts/paper1/queues/tr_by_tr.txt
Options: --work DIR (default ../paper1-runs, outside the repository), environment AIMMS_CMD = path of AimmsCmd.exe,
--project FILE (prepare only): the OPF.aimms to copy into the lanes (default the repository's). With an AIMMS newer than
the version in OPF.aimms, AimmsCmd can crash on exit after the run (no "Return value" line): open the project once in
that AIMMS so it updates the library versions, save that OPF.aimms outside Git and pass it with --project.
Re-run "prepare" after changing the model: it refreshes MainProject/ in every lane given.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCEN = Path(__file__).resolve().parent / "scenarios"
DATA = ("Database.mdb", "Database.dsn", "OpData.xls")
COMMON = {"ZX_GMP": 1, "SCTight": 1, "SPD_TimeLog": 1, "EnableRollDiag": 0}
CASES = {"free_today": {"PV2_Regime": 0, "SRQ_Coord": 0, "FRQ_BF": 0}}   # paper 1: rule (i), PV never cut
FINAL = {"SPD_P1NoNet": 1, "SPD_P1Q0": 1, "SPD_S0FOR": 0, "SPD_NCAll": 1, "SPD_FixSlotK": 1, "SPD_CornersOnly": 1}
ALL_TRAFOS = "ALL"


def aimms_cmd():
    if os.environ.get("AIMMS_CMD"):
        return os.environ["AIMMS_CMD"]
    found = sorted(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\AIMMS\IFA\Aimms\*\Bin\AimmsCmd.exe")))
    if not found:
        raise SystemExit("AimmsCmd.exe not found: set AIMMS_CMD to its full path")
    return found[-1]


def speed_settings(speed):
    m = re.fullmatch(r"a(\d+)x(\d+)p(\d+)(fin2|fin)(d?)(s?)", speed)
    if not m:
        raise SystemExit(f"speed '{speed}' not understood (expected e.g. a2x4p8fin2)")
    k, t, p, fin, d, s = m.groups()
    out = {"RollAsyncK": int(k), "RollAsyncThreads": int(t), "SPD_P1Threads": int(p), **FINAL,
           "SPD_TwoDays": int(fin == "fin2")}
    if d:
        out["SPD_RescDiag"] = 1
    if s:
        out["SPD_SweepDiag"] = 1
    return out


def parse_job(fields):
    sid, case, speed = fields[:3]
    net, extra = "", {}
    for f in fields[3:]:
        if "=" in f:
            k, v = f.split("=", 1)
            extra[k] = v
        else:
            net = f
    return sid, case, speed, net, extra


def job_tag(sid, case, speed, net, extra):
    tag = f"_{sid}_{case}_{speed}" + (f"_{net.replace(',', '')}" if net else "")
    return tag + "".join(f"_{k}{v}" for k, v in extra.items())


def scenario_txt(sid, case, speed, net, extra):
    s = json.loads((SCEN / f"{sid}.json").read_text())
    req = {int(p): v for p, v in s["requests"].items()}
    ps = sorted(req)
    lines = [f'SRQ_Tag := "{job_tag(sid, case, speed, net, extra)}" ;', f"SRQ_MaxPer := {int(s.get('max_per', 0))} ;",
             f"FRQ_SweepAll := {int(s.get('sweep_all', 0))} ;", "FRQ_PlanLog := 0 ;",
             f'SRQ_Periods := "{",".join(str(p) for p in ps)}" ;']
    settings = {**COMMON, **CASES[case], **speed_settings(speed), **extra}
    lines += [f"{k} := {v} ;" for k, v in settings.items()]
    if net:
        lines.append(f'SPD_Trafo := "{net}" ;')
    if ps:
        for k, name in enumerate(("FRQ_U1", "FRQ_U2", "FRQ_U3", "FRQ_Edge")):
            lines.append(name + " := DATA { " + ", ".join(f"{p} : {req[p][k]}" for p in ps) + " } ;")
    return "\n".join(lines) + "\n"


def log(lane_dir, msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    with open(lane_dir / "lane.log", "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def done_anywhere(work, tag):
    return any("Return value = 0" in f.read_text(errors="ignore") for f in work.glob(f"*/done{tag}.txt"))


def claim(work, tag, lane):
    d = work / "claims"
    d.mkdir(exist_ok=True)
    try:
        fd = os.open(d / f"{tag}.claim", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, f"{lane} {datetime.now():%Y-%m-%d %H:%M:%S}\n".encode())
    os.close(fd)
    return True


def run_job(work, lane_dir, lane, job):
    sid, case, speed, net, extra = job
    tag = job_tag(*job)
    (lane_dir / "scenario.txt").write_text(scenario_txt(*job))
    for attempt in range(1, 41):
        t0, start = time.time(), datetime.now()
        out = lane_dir / f"stdout{tag}.txt"
        with open(out, "w") as fo:
            subprocess.run([aimms_cmd(), "--run-only", "PV2_Run", str(lane_dir / "OPF.aimms")], cwd=lane_dir,
                           stdin=subprocess.DEVNULL, stdout=fo, stderr=subprocess.STDOUT)
        text = out.read_text(errors="ignore")
        err = lane_dir / "log" / "aimms.err"
        errtext = err.read_text(errors="ignore") if err.exists() and err.stat().st_mtime >= t0 else ""
        if "initialization error" in text and "Semantic error" not in text + errtext:
            log(lane_dir, f"{tag}: AIMMS did not start, licence seat busy? (try {attempt}; a compile error would be in log/aimms.err)")
            time.sleep(180)
            continue
        ret = [l for l in text.splitlines() if "Return value" in l or "Error" in l]
        mins = (time.time() - t0) / 60
        (lane_dir / f"done{tag}.txt").write_text((ret[-1] if ret else "no return line") + "\n")
        log(lane_dir, f"done {tag} in {mins:.1f} min: {ret[-1] if ret else 'no return line'}")
        jobs = work / "jobs.csv"
        new = not jobs.exists()
        with open(jobs, "a") as f:
            if new:
                f.write("lane,tag,start,end,wall_min,ok\n")
            f.write(f"{lane},{tag},{start:%Y-%m-%d %H:%M:%S},{datetime.now():%Y-%m-%d %H:%M:%S},{mins:.2f},"
                    f"{int('Return value = 0' in text)}\n")
        return
    log(lane_dir, f"{tag}: gave up after 40 tries")


def prepare(work, lanes, project):
    missing = [f for f in DATA if not (REPO / f).exists()]
    if missing:
        raise SystemExit(f"input data missing in the repository root: {', '.join(missing)}")
    for lane in lanes:
        d = work / lane
        d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project, d / "OPF.aimms")
        for f in DATA:
            shutil.copyfile(REPO / f, d / f)
        if (d / "MainProject").exists():
            shutil.rmtree(d / "MainProject")
        shutil.copytree(REPO / "MainProject", d / "MainProject",
                        ignore=shutil.ignore_patterns("log", "backup", "PROTemp", "*.aimmslockfile"))
        print("prepared", d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["prepare", "lane", "show"])
    ap.add_argument("args", nargs="+")
    ap.add_argument("--work", default=str(REPO.parent / "paper1-runs"))
    ap.add_argument("--project", default=str(REPO / "OPF.aimms"))
    a = ap.parse_args()
    work = Path(a.work)
    if a.cmd == "prepare":
        prepare(work, a.args, Path(a.project))
    elif a.cmd == "show":   # print the scenario.txt of one job line, nothing is run
        print(scenario_txt(*parse_job(a.args)), end="")
    else:
        lane, qfile = a.args[0], Path(a.args[1])
        d = work / lane
        if not (d / "OPF.aimms").exists():
            raise SystemExit(f"{d} is not prepared: run 'prepare {lane}' first")
        jobs = [parse_job(l.split()) for l in qfile.read_text().splitlines() if l.strip() and not l.startswith("#")]
        log(d, f"lane {lane} start: queue {qfile.name}, {len(jobs)} jobs")
        for job in jobs:
            tag = job_tag(*job)
            if done_anywhere(work, tag) or not claim(work, tag, lane):
                continue
            log(d, f"start {tag}")
            run_job(work, d, lane, job)
        log(d, f"lane {lane} finished queue {qfile.name}")


if __name__ == "__main__":
    main()
