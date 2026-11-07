"""Rebuild the figures of the results meeting of 16-Oct-2026 (Paper1-results-meeting-Tulio.pptx).

Steps, each a script run on its own (python -B) with the same --runs / --out:
  1 data      data/build.py, build_for_time.py, guarantee_metrics.py, build_sweeps.py, build_service.py
              raw runs (--runs) -> <out>/data/*.json
  2 figures   figures/fig_3d_criteria.py, fig_3d_service.py --compact      JSON -> <out>/figures/*.png
  3 deck      deck/build_tulio.py                                           JSON + PNGs -> <out>/<deck>.pptx

Without flags all three run and steps 2-3 read the rebuilt <out>/data. Before the data step the raw files are checked
against raw_inputs.sha256 (--no-verify skips that, for other runs). With --figures-only (or --deck-only) the data
step is skipped and the JSONs come from --data, by default the committed results/paper1-fairness-2026-10.

Usage (from the repository root):
  python -B scripts/paper1/figures/meeting_2026_10_16/make_all.py --figures-only
  python -B scripts/paper1/figures/meeting_2026_10_16/make_all.py --runs DIR [--out DIR]
"""
import argparse
import hashlib
import subprocess
import sys
import time
from pathlib import Path

import paths

HERE = Path(__file__).resolve().parent
D2 = "_free_today_a2x4p8fin2_TR4"
GUARANTEE = ["--on", f"N3/_WC_EXPORT{D2}_FairBox1_RollOfferLog1_SCAlpha0",
             "--relaxed", f"N3/_WC_EXPORT{D2}_FairBox1_RollOfferLog1_SCAlpha99",
             "--ref", f"N2/_REF{D2}_FairBox1"]
DATA_STEPS = [("data/build.py", []),                      # muf.json, fair.json, service_T5.json
              ("data/build_for_time.py", []),             # for_time.json (+ for_time.csv)
              ("data/guarantee_metrics.py", GUARANTEE),   # guarantee.json
              ("data/build_sweeps.py", []),               # sweeps.json
              ("data/build_service.py", [])]              # service_requests.json (checked against the four above)
FIGURE_STEPS = [("figures/fig_3d_criteria.py", []),
                ("figures/fig_3d_service.py", ["--compact"])]
DECK_STEPS = [("deck/build_tulio.py", [])]


def run(script, args):
    cmd = [sys.executable, "-B", str(HERE / script), *args]
    print(f"\n=== {script} {' '.join(args)}", flush=True)
    t0 = time.time()
    r = subprocess.run(cmd)
    if r.returncode:
        raise SystemExit(f"make_all: step {script} failed (exit status {r.returncode}); its message is above.")
    print(f"=== {script}: {time.time() - t0:.0f} s", flush=True)


def verify_inputs(runs):
    """The data step must read the raw files the deck was built from: compare them with raw_inputs.sha256."""
    lines = [ln.strip() for ln in paths.MANIFEST.read_text(encoding="ascii").splitlines() if ln.strip()]   # CRLF or LF
    bad = []
    for ln in lines:
        digest, name = ln.split(maxsplit=1)
        f = runs / name.lstrip("*")
        if not f.is_file():
            bad.append(f"missing {name.lstrip('*')}")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != digest.lower():
            bad.append(f"different {name.lstrip('*')}")
    if bad:
        raise SystemExit(f"make_all: {len(bad)} of the {len(lines)} raw inputs in {runs} do not match raw_inputs.sha256 "
                         f"(e.g. {bad[0]}). Use the files of {paths.BUNDLE}, or --no-verify to build from other runs.")
    print(f"raw inputs: the {len(lines)} files match raw_inputs.sha256")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    paths.add_args(ap, runs=True, data=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--figures-only", action="store_true", help="skip the data step: 3-D figures and deck from --data")
    g.add_argument("--deck-only", action="store_true", help="only the deck, from --data and the PNGs in <out>/figures")
    g.add_argument("--data-only", action="store_true", help="only the data step")
    ap.add_argument("--no-verify", action="store_true", help="do not check the raw runs against raw_inputs.sha256")
    a = ap.parse_args()
    paths.use(a)
    out = paths.out_dir()
    loc = ["--out", str(out)]
    if a.figures_only or a.deck_only:
        if a.runs:
            print("note: --runs is ignored with --figures-only / --deck-only (no data step)")
        data = ["--data", str(paths.data_in())]
    else:
        if a.data:
            ap.error("--data is for --figures-only / --deck-only; the full chain reads what it rebuilds")
        data = ["--data", str(paths.data_out())]
        runs_dir = paths.runs_dir()
        print(f"raw runs: {runs_dir} (from {paths.runs_source()[1]})")
        if a.no_verify:
            print("raw inputs: not checked (--no-verify)")
        else:
            verify_inputs(runs_dir)
        runs = ["--runs", str(runs_dir)]
        for script, args in DATA_STEPS:
            run(script, args + runs + loc)
        if a.data_only:
            return
    print("JSON from:", data[1])
    if not a.deck_only:
        for script, args in FIGURE_STEPS:
            run(script, args + data + loc)
    for script, args in DECK_STEPS:
        run(script, args + data + loc)
    print("\noutputs in", out)


if __name__ == "__main__":
    main()
