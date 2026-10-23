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
  NAME=VALUE  any further model parameter, e.g. FairCrit=2 FairScope=1 (fairness, docs/paper1-fairness.md) or
              FairBox=0 (this branch without the headroom box), SCAlpha=99 (self-consumption guarantee relaxed:
              the protection-off benchmark); also added to the output tag

Outputs go to the lane folder, named with the tag _<scenario>_<case>_<speed>[_<network>][_<NAME><VALUE>...];
day-2 files end in _d2. A job is skipped when a done file with "Return value = 0" exists in any lane, or when
another lane has claimed it (runs/claims/<tag>.claim; delete the claim to run it again).

Run records (case study, Oct 2026): "prepare" writes prepare_info.json in each lane (Git commit and whether the working
tree had uncommitted changes, SHA-256 of the model and input files as copied); after every job the lane gets
record<tag>.json (job line, scenario, start/end, wall time, return line, computer, AIMMS, the prepare info and every
output file with size and SHA-256). "prepare --strict" refuses to prepare from a working tree with uncommitted changes
(use it for production runs). Inputs from inputs/case-study/ (aggregator mapping) are copied into every lane.
At most one TR6 / TR7 job runs at a time (memory); the other lanes take the next job meanwhile.

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
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCEN = Path(__file__).resolve().parent / "scenarios"
DATA = ("Database.mdb", "Database.dsn", "OpData.xls")
CASE_INPUTS = REPO / "inputs" / "case-study"
CASE_FILES = ("aggregators_case_study.txt",)   # copied into every lane (read by the model when CaseAggMap = 1)
HEAVY = re.compile(r"_(TR6|TR7)(_|$)")          # transformers whose sessions need ~15 GB: one at a time
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


def job_line(sid, case, speed, net, extra):
    return " ".join([sid, case, speed] + ([net] if net else []) + [f"{k}={v}" for k, v in extra.items()])


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def git_info():
    def git(*args):
        r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""
    dirty = [l for l in git("status", "--porcelain", "--untracked-files=no").splitlines() if l.strip()]
    return {"commit": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(dirty), "dirty_files": [l[3:] for l in dirty]}


def computer_info():
    info = {"host": platform.node(), "os": platform.platform(), "logical_cpus": os.cpu_count()}
    try:
        ps = ("$c = Get-CimInstance Win32_Processor | Select-Object -First 1; $m = Get-CimInstance Win32_ComputerSystem; "
              "\"$($c.Name)|$($c.NumberOfCores)|$([math]::Round($m.TotalPhysicalMemory / 1GB, 1))\"")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60).stdout.strip()
        cpu, cores, ram = out.split("|")
        info.update(cpu=cpu.strip(), cores=int(cores), ram_gb=float(ram))
    except Exception:   # the record is still written without these fields
        pass
    return info


def scenario_txt(sid, case, speed, net, extra):
    s = json.loads((SCEN / f"{sid}.json").read_text())
    if s.get("blocked"):   # a scenario whose settings are not decided yet (e.g. the Run B request point)
        raise SystemExit(f"scenario {sid} is blocked: {s['blocked']}")
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


def wait_free(lane_dir):
    """Wait until the previous AIMMS session has released the lane (Access lock Database.ldb), then 15 s more:
    a job started while the lock was still there failed within a minute (Tulio's PC, 9 Oct 2026)."""
    for _ in range(36):
        if not (lane_dir / "Database.ldb").exists():
            break
        time.sleep(5)
    time.sleep(15)


def write_record(lane_dir, lane, job, tag, start, end, mins, return_line, ok):
    """record<tag>.json: everything needed to trace a result back to its code, inputs and computer."""
    sid = job[0]
    prep = lane_dir / "prepare_info.json"
    outputs = []
    for f in sorted(lane_dir.glob(f"*{tag}*")):
        if f.is_file() and not f.name.startswith(("record", "done")):
            outputs.append({"file": f.name, "bytes": f.stat().st_size, "sha256": sha16(f)})
    rec = {
        "tag": tag, "job_line": job_line(*job), "lane": lane, "lane_dir": str(lane_dir),
        "scenario": {"id": sid, "file": f"scripts/paper1/scenarios/{sid}.json", "sha256": sha16(SCEN / f"{sid}.json"),
                     "scenario_txt": (lane_dir / "scenario.txt").read_text()},
        "start": f"{start:%Y-%m-%d %H:%M:%S}", "end": f"{end:%Y-%m-%d %H:%M:%S}", "wall_min": round(mins, 2),
        "return_line": return_line, "ok": bool(ok),
        "computer": computer_info(), "aimms_cmd": aimms_cmd(),
        "prepare_info": json.loads(prep.read_text()) if prep.exists() else None,
        "outputs": outputs,
    }
    (lane_dir / f"record{tag}.json").write_text(json.dumps(rec, indent=1))


def run_job(work, lane_dir, lane, job):
    sid, case, speed, net, extra = job
    tag = job_tag(*job)
    (lane_dir / "scenario.txt").write_text(scenario_txt(*job))
    early = 0
    for attempt in range(1, 41):
        wait_free(lane_dir)
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
        if "Return value = 0" not in text and mins < 3 and early < 2:   # failed while starting: retry after a minute
            early += 1
            if err.exists():
                shutil.copyfile(err, lane_dir / f"aimms_err{tag}_early{early}.txt")
            log(lane_dir, f"{tag}: failed after {mins:.1f} min while starting, retry {early} in 60 s")
            time.sleep(60)
            continue
        if err.exists():   # keep each job's error log: the next job overwrites log/aimms.err
            shutil.copyfile(err, lane_dir / f"aimms_err{tag}.txt")
        end = datetime.now()
        write_record(lane_dir, lane, job, tag, start, end, mins, ret[-1] if ret else "no return line",
                     "Return value = 0" in text)
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


def prepare(work, lanes, project, strict=False):
    missing = [f for f in DATA if not (REPO / f).exists()]
    if missing:
        raise SystemExit(f"input data missing in the repository root: {', '.join(missing)}")
    gi = git_info()
    if strict and (gi["dirty"] or not gi["commit"]):
        raise SystemExit("--strict: the working tree has uncommitted changes to tracked files "
                         f"({', '.join(gi['dirty_files'][:5])}); commit or stash them first")
    for lane in lanes:
        d = work / lane
        d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project, d / "OPF.aimms")
        for f in DATA:
            shutil.copyfile(REPO / f, d / f)
        for f in CASE_FILES:
            if (CASE_INPUTS / f).exists():
                shutil.copyfile(CASE_INPUTS / f, d / f)
        if (d / "MainProject").exists():
            shutil.rmtree(d / "MainProject")
        shutil.copytree(REPO / "MainProject", d / "MainProject",
                        ignore=shutil.ignore_patterns("log", "backup", "PROTemp", "*.aimmslockfile"))
        files = {f: sha16(d / f) for f in ("OPF.aimms", *DATA, *CASE_FILES) if (d / f).exists()}
        files["MainProject/OPF.ams"] = sha16(d / "MainProject" / "OPF.ams")
        other = hashlib.sha256()   # project settings (solver options etc.) besides OPF.ams
        for f in sorted(p for p in (d / "MainProject").rglob("*") if p.is_file() and p.name != "OPF.ams"):
            other.update(f.relative_to(d).as_posix().encode() + bytes.fromhex(sha16(f)))
        files["MainProject/other files"] = other.hexdigest()[:16]
        info = {"prepared": f"{datetime.now():%Y-%m-%d %H:%M:%S}", "repo": str(REPO), "git": gi,
                "project_file": str(Path(project).resolve()), "files_sha256": files,
                "runner_sha256": sha16(Path(__file__)), "strict": strict}
        (d / "prepare_info.json").write_text(json.dumps(info, indent=1))
        print("prepared", d, "(commit", gi["commit"][:7] + (", UNCOMMITTED CHANGES" if gi["dirty"] else "") + ")")


def heavy_running(work):
    """A TR6 / TR7 job is running when its claim exists and no lane has its done file yet."""
    for c in (work / "claims").glob("*.claim"):
        if HEAVY.search(c.stem) and not any(work.glob(f"*/done{c.stem}.txt")):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["prepare", "lane", "show"])
    ap.add_argument("args", nargs="+")
    ap.add_argument("--work", default=str(REPO.parent / "paper1-runs"))
    ap.add_argument("--project", default=str(REPO / "OPF.aimms"))
    ap.add_argument("--strict", action="store_true", help="prepare only: refuse a working tree with uncommitted changes")
    a = ap.parse_args()
    work = Path(a.work).resolve()   # absolute: AimmsCmd runs inside the lane folder, a relative path fails to start
    if a.cmd == "prepare":
        prepare(work, a.args, Path(a.project), a.strict)
    elif a.cmd == "show":   # print the scenario.txt of one job line, nothing is run
        print(scenario_txt(*parse_job(a.args)), end="")
    else:
        lane, qfile = a.args[0], Path(a.args[1])
        d = work / lane
        if not (d / "OPF.aimms").exists():
            raise SystemExit(f"{d} is not prepared: run 'prepare {lane}' first")
        jobs = [parse_job(l.split()) for l in qfile.read_text().splitlines() if l.strip() and not l.startswith("#")]
        for job in jobs:   # fail now, not hours later, on a scenario that does not exist or is blocked
            scenario_txt(*job)
        log(d, f"lane {lane} start: queue {qfile.name}, {len(jobs)} jobs")
        pending = list(jobs)
        while pending:
            started = False
            for job in list(pending):
                tag = job_tag(*job)
                if done_anywhere(work, tag) or (work / "claims" / f"{tag}.claim").exists():
                    pending.remove(job)
                    continue
                if HEAVY.search(tag) and heavy_running(work):   # wait for the other TR6 / TR7 job
                    continue
                pending.remove(job)
                if not claim(work, tag, lane):
                    continue
                log(d, f"start {tag}")
                run_job(work, d, lane, job)
                started = True
                break
            if pending and not started:   # only TR6 / TR7 jobs left, and one is running elsewhere
                time.sleep(300)
        log(d, f"lane {lane} finished queue {qfile.name}")


if __name__ == "__main__":
    main()
