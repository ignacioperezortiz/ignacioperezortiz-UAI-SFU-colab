"""Run the two-PV-options patterns on TR4 (PV2_Run), one AIMMS session per lane, lanes share one queue.

Each lane is its own copy of model/ under runs/<lane>/. Lanes read the same queue file in order; a job is taken
by creating runs/claims/<tag>.claim (atomic), so two lanes never run the same job and a free lane always takes
the next job in priority order. For every job the lane writes scenario.txt, runs PV2_Run headless and writes
done_<tag>.txt with the AIMMS return line. A job already done in any lane ("Return value = 0") is skipped. A
start that loses the license seat ("Program initialization error") is retried every 3 min.

Cases (all: exact QCP + CPLEX, GMP sweep, self-consumption rule with the 0.01 W slack):
  exp_today    option 1 - PV exported by default, surplus cut only on TSO request; today's charging; batteries-first
  exp_coord    option 1, coordinated charging
  noexp_today  option 2 - no export without agreement, PV refills the batteries; today's charging
  noexp_coord  option 2, coordinated charging
Fairness: add _f<N> to any case name to set FairMode := N (1-4), e.g. exp_coord_f2. FairMode acts only in the
directional FOR solves (see README.md, section "Fairness").

Usage:
  python scripts/run_pv2.py prepare L1 L2 L3
  python scripts/run_pv2.py lane L1 runs/queue_main.txt      # one job per line: <scenario id> <case>
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
# AimmsCmd.exe: set the environment variable AIMMS_CMD to your own installation; otherwise this default is used
AIMMS = os.environ.get("AIMMS_CMD", r"C:\Users\thc22\AppData\Local\AIMMS\IFA\Aimms\26.3.2.1-x64-VS2022_v2\Bin\AimmsCmd.exe")
COMMON = {"ZX_GMP": 1, "SCTight": 1}
CASES = {"exp_today":   {"PV2_Regime": 1, "SRQ_Coord": 0, "FRQ_BF": 1},
         "exp_coord":   {"PV2_Regime": 1, "SRQ_Coord": 1, "FRQ_BF": 1},
         "noexp_today": {"PV2_Regime": 2, "SRQ_Coord": 0, "FRQ_BF": 0},
         "noexp_coord": {"PV2_Regime": 2, "SRQ_Coord": 1, "FRQ_BF": 0}}


def log(lane_dir, msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    with open(lane_dir / "lane.log", "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def split_case(case):
    """'exp_coord_f2' -> ('exp_coord', 2); 'exp_coord' -> ('exp_coord', None)."""
    base, _, tail = case.rpartition("_f")
    if base in CASES and tail.isdigit():
        return base, int(tail)
    return case, None


def scenario_txt(sid, case):
    s = json.loads((ROOT / "scenarios" / f"{sid}.json").read_text())
    req = {int(p): v for p, v in s["requests"].items()}
    ps = sorted(req)
    lines = [f'SRQ_Tag := "_{sid}_{case}" ;', f"SRQ_MaxPer := {int(s.get('max_per', 0))} ;",
             f"FRQ_SweepAll := {int(s.get('sweep_all', 0))} ;", "FRQ_PlanLog := 0 ;",
             f'SRQ_Periods := "{",".join(str(p) for p in ps)}" ;']
    base, fair = split_case(case)
    settings = {**COMMON, **CASES[base]}
    if fair is not None:
        settings["FairMode"] = fair
    lines += [f"{k} := {v} ;" for k, v in settings.items()]
    if ps:
        for k, name in enumerate(("FRQ_U1", "FRQ_U2", "FRQ_U3", "FRQ_Edge")):
            lines.append(name + " := DATA { " + ", ".join(f"{p} : {req[p][k]}" for p in ps) + " } ;")
    return "\n".join(lines) + "\n"


def done_anywhere(tag):
    for f in RUNS.glob(f"*/done{tag}.txt"):
        if "Return value = 0" in f.read_text(errors="ignore"):
            return True
    return False


def claim(tag, lane):
    d = RUNS / "claims"
    d.mkdir(exist_ok=True)
    try:
        fd = os.open(d / f"{tag}.claim", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, f"{lane} {datetime.now():%Y-%m-%d %H:%M:%S}\n".encode())
    os.close(fd)
    return True


def run_job(lane_dir, sid, case):
    tag = f"_{sid}_{case}"
    (lane_dir / "scenario.txt").write_text(scenario_txt(sid, case))
    for attempt in range(1, 41):
        t0 = time.time()
        out = lane_dir / f"stdout{tag}.txt"
        with open(out, "w") as fo:
            subprocess.run([AIMMS, "--run-only", "PV2_Run", str(lane_dir / "OPF.aimms")], cwd=lane_dir,
                           stdin=subprocess.DEVNULL, stdout=fo, stderr=subprocess.STDOUT)
        text = out.read_text(errors="ignore")
        if "initialization error" in text:
            log(lane_dir, f"{tag}: license busy (try {attempt})")
            time.sleep(180)
            continue
        ret = [l for l in text.splitlines() if "Return value" in l or "Error" in l]
        (lane_dir / f"done{tag}.txt").write_text((ret[-1] if ret else "no return line") + "\n")
        log(lane_dir, f"done {tag} in {(time.time() - t0) / 60:.1f} min: {ret[-1] if ret else 'no return line'}")
        return "Return value = 0" in text
    log(lane_dir, f"{tag}: gave up after 40 license retries")
    return False


def main():
    cmd = sys.argv[1]
    if cmd == "prepare":
        for lane in sys.argv[2:]:
            d = RUNS / lane
            if not d.exists():
                shutil.copytree(ROOT / "model", d)
                print("prepared", d)
    elif cmd == "lane":
        lane, qfile = sys.argv[2], Path(sys.argv[3])
        d = RUNS / lane
        jobs = [l.split() for l in qfile.read_text().splitlines() if l.strip() and not l.startswith("#")]
        log(d, f"lane {lane} start: queue {qfile.name}, {len(jobs)} jobs")
        for sid, case in jobs:
            tag = f"_{sid}_{case}"
            if done_anywhere(tag) or not claim(tag, lane):
                continue
            log(d, f"start {tag}")
            run_job(d, sid, case)
        log(d, f"lane {lane} finished queue {qfile.name}")


if __name__ == "__main__":
    main()
