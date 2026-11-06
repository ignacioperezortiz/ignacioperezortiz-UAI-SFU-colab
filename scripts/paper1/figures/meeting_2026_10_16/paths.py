"""Where everything lives. Every location outside the package comes from here; every script asks it.

  repository root   from this file (scripts/paper1/figures/meeting_2026_10_16 -> four levels up)
  raw runs          --runs DIR, else environment variable PAPER1_RUNS, else <repo>/../paper1-runs (the same default
                    as scripts/paper1/run_paper1.py --work). The lanes are its subfolders N2 and N3 (N1 optional).
  outputs           --out DIR, else out/ next to this file:
                      <out>/data/*.json   data builders (same file names as results/paper1-fairness-2026-10)
                      <out>/figures/*.png 3-D figures
                      <out>/img/*.png     image extractors
                      <out>/*.pptx        deck
  data for figures  --data DIR, else results/paper1-fairness-2026-10 (the committed JSONs).
                    --data <out>/data points the figures and the deck at a rebuild.
  3-D PNGs for deck --figures DIR, else <out>/figures.
  MML2OMML.XSL      environment variable MML2OMML_XSL, else the usual Microsoft Office folders.
Importing it also switches stdout/stderr to UTF-8: the scripts print μ, Δ, Σ, which a pipe or a file on Windows
(cp1252) cannot take.
"""
import argparse
import os
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3] if len(HERE.parents) > 3 else HERE
PAPER1 = REPO / "scripts" / "paper1"                       # analyze_paper1.py, scenarios/
RESULTS = REPO / "results" / "paper1-fairness-2026-10"     # committed JSONs (default --data)
DECK_PPTX = "Paper1-results-meeting-Tulio.pptx"
BUNDLE = "meeting-2026-10-16_raw_inputs.zip (shared case-study folder CaseStudy/raw/)"
MANIFEST = HERE / "raw_inputs.sha256"                      # the raw files the data step reads, with SHA-256
if not ((PAPER1 / "analyze_paper1.py").is_file() and RESULTS.is_dir()):
    raise SystemExit(f"{REPO} does not look like the repository (no scripts/paper1/analyze_paper1.py or no "
                     "results/paper1-fairness-2026-10): keep this package at scripts/paper1/figures/meeting_2026_10_16 "
                     "inside the repository.")

# the deck read its JSONs from its own folders data\ and data_tulio\; results/paper1-fairness-2026-10 holds the same
# files under these names (two of them were both called service.json)
JSON_NAMES = {
    ("data", "fair.json"): "fair.json",
    ("data", "muf.json"): "muf.json",
    ("data", "service.json"): "service_T5.json",
    ("data", "for_time.json"): "for_time.json",
    ("data", "guarantee.json"): "guarantee.json",
    ("data_tulio", "sweeps.json"): "sweeps.json",
    ("data_tulio", "service.json"): "service_requests.json",
}
FIGURES = ("fig_3d_criteria.png", "fig_3d_service_compact.png")   # the 3-D PNGs the deck places

_args = argparse.Namespace(runs=None, out=None, data=None, figures=None)


# ---------------------------------------------------------------- command line
def add_args(ap, runs=False, data=False, figures=False):
    """Add the location options to a script's own argparse parser."""
    if runs:
        ap.add_argument("--runs", help="folder holding the lanes N2, N3 (default: $PAPER1_RUNS, else <repo>/../paper1-runs)")
    ap.add_argument("--out", help="output folder (default: out/ next to paths.py)")
    if data:
        ap.add_argument("--data", help="folder with the JSONs (default: results/paper1-fairness-2026-10)")
    if figures:
        ap.add_argument("--figures", help="folder with the 3-D PNGs (default: <out>/figures)")
    return ap


def use(args):
    """Take the locations from parsed arguments (missing options keep their defaults)."""
    global _args
    _args = argparse.Namespace(**{k: getattr(args, k, None) for k in ("runs", "out", "data", "figures")})
    return args


def cli(doc, runs=False, data=False, figures=False, flags=()):
    """Parse the command line of a script without its own parser; flags = extra store_true options."""
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    add_args(ap, runs=runs, data=data, figures=figures)
    for f in flags:
        ap.add_argument(f, action="store_true")
    return use(ap.parse_args())


# ---------------------------------------------------------------- inputs
def runs_source():
    """(folder, where it came from) of the raw runs, not checked."""
    if _args.runs:
        return Path(_args.runs).resolve(), "--runs"
    if os.environ.get("PAPER1_RUNS"):
        return Path(os.environ["PAPER1_RUNS"]).resolve(), "the environment variable PAPER1_RUNS"
    return REPO.parent / "paper1-runs", "the default <repo>/../paper1-runs (no --runs, no PAPER1_RUNS)"


_noted = False


def runs_dir():
    """Folder of the raw runs; stops unless it holds the lanes N2 and N3."""
    global _noted
    d, src = runs_source()
    missing = [name for name in ("N2", "N3") if not (d / name).is_dir()]
    if missing:
        sub = " and ".join(missing) + (" subfolders" if len(missing) > 1 else " subfolder")
        raise SystemExit(f"raw runs folder {d} (from {src}) has no {sub}. Unzip {BUNDLE} and pass that folder with "
                         "--runs DIR or PAPER1_RUNS=DIR.")
    if src.startswith("the default") and not _noted:
        _noted = True
        print(f"note: raw runs from {d}, {src}; make_all.py checks them against raw_inputs.sha256", file=sys.stderr)
    return d


def lane(name):
    return runs_dir() / name


def data_in():
    return Path(_args.data).resolve() if _args.data else RESULTS


def deck_json(folder, name):
    """JSON the deck knew as <folder>\\<name> (folder = "data" or "data_tulio"), in the --data folder."""
    return data_in() / JSON_NAMES[(folder, name)]


def figures_in():
    return Path(_args.figures).resolve() if _args.figures else out_dir() / "figures"


# ---------------------------------------------------------------- outputs
def out_dir():
    d = Path(_args.out).resolve() if _args.out else HERE / "out"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sub(name):
    d = out_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_out():
    return _sub("data")


def figures_out():
    return _sub("figures")


def img_out():
    return _sub("img")


# ---------------------------------------------------------------- Office's MathML -> OMML stylesheet
def mml2omml_xsl():
    if os.environ.get("MML2OMML_XSL"):
        p = Path(os.environ["MML2OMML_XSL"])
        if not p.is_file():
            raise SystemExit(f"MML2OMML_XSL points to {p}, which does not exist")
        return p
    roots = [os.environ.get(v) for v in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)")]
    tried = []
    for root in dict.fromkeys(r for r in roots if r):
        for sub in (("root", "Office16"), ("Office16",), ("root", "Office15"), ("Office15",)):
            p = Path(root, "Microsoft Office", *sub, "MML2OMML.XSL")
            if p.is_file():
                return p
            tried.append(str(p))
    raise SystemExit("MML2OMML.XSL (Microsoft Office's MathML-to-OMML stylesheet, needed for the equations of the deck) "
                     "not found. Set the environment variable MML2OMML_XSL to its path. Looked in:\n  " + "\n  ".join(tried))
