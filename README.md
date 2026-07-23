# OPF Rolling-Horizon Model (AIMMS)

An AIMMS optimal-power-flow (OPF) model for a low-voltage distribution feeder with
customer PV and battery energy storage. The model computes a **rolling-horizon
Feasible Operating Region (FOR)** at the point of common coupling, per transformer
and for the whole feeder.

> **Working on this repository?** Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first. It
> sets out the git workflow we follow, how we split work across the model sections,
> and how input data is versioned as study cases. `MainProject/OPF.ams` is a single
> ~4,200-line file that AIMMS rewrites on save, so the process there is what keeps
> parallel work mergeable.

---

## 1. Requirements

- **AIMMS 26.1.3.1** (x64) or compatible. The project uses the WebUI and
  AimmsXLLibrary system libraries.
- A solver capable of the model's NLP/LP solves (e.g. the solver shipped with AIMMS).
- **Microsoft Access Database Driver** (`*.mdb`, `*.accdb`) — required so AIMMS can
  read `Database.mdb` through the ODBC DSN. On Windows this comes with the
  *Microsoft Access Database Engine* redistributable.

## 2. Input data (shared separately — not in this repo)

Three input files are **not** tracked in Git and are shared over the cloud instead.
Copy them into the **repository root** (next to `OPF.aimms`) before running:

| File           | What it is                                             |
|----------------|--------------------------------------------------------|
| `Database.mdb` | Access database — network, customers, load/PV tables   |
| `Database.dsn` | ODBC data-source pointing at `.\Database.mdb`          |
| `OpData.xls`   | Excel time-series and per-customer load/PV parameters  |

> The model loads these via `Load_data_dsn` (Database + Excel → per-unit at
> Sb = 1 MW, plus flat-start voltages = the linearization point). Without them the
> model will open but cannot run.

## 3. Opening and running

1. Put the three data files (section 2) in the repo root.
2. Open **`OPF.aimms`** in AIMMS.
3. Run `MainInitialization`, then `Load_data_dsn` to load the input data.
4. Run the rolling-horizon FOR:
   - `RunFOR_Rolling` — whole-feeder rolling-horizon FOR.
   - `RunFOR_Rolling_PerTrafo` — per-transformer decomposition (writes
     `FOR_rolling_TR<n>.csv` / `FOR_rolling_soc_TR<n>.csv`).
   - `RunBAU` — business-as-usual dispatch baseline.

Results are written as `FOR_rolling*.csv` in the repo root. These are **git-ignored**
(they regenerate on every run).

## 4. Repository layout

```
.
├── OPF.aimms              # AIMMS project entry point (open this)
├── MainProject/
│   ├── OPF.ams            # Model source (all sections & procedures)
│   ├── Project.xml
│   ├── Settings/          # AIMMS project settings
│   ├── User Files/        # UI bitmaps
│   └── WebUI/             # WebUI resources
├── .gitignore
├── CONTRIBUTING.md        # collaboration workflow — read before contributing
└── README.md
```

### Model source structure (`MainProject/OPF.ams`)

The model is organized into sections: `Configuration`, `InputData`,
`NetworkModel`, `BatteryModel`, `SelfConsumptionOPF`, `FOR_Computation`,
`NetworkReduction`, `RollingHorizonFOR`, `Validation`, and `ResultsOutput`.
The rolling-horizon FOR entry points live in the `RollingHorizonFOR` section.

## 5. Not included

To keep the repo focused on the runnable model, the following are intentionally
left out: experiment outputs (`FOR_rolling*.csv`, `Results/`, plots), AIMMS
auto-backups and logs, and standalone experiment snippets. The input data is
distributed via cloud (section 2).

## 6. Documentation

This repository holds only **general, reproducible** documentation — the kind that
works for anyone who clones it:

- **Root:** `README.md`, `CONTRIBUTING.md`.
- **`docs/`:** longer guides (setup, reproducibility, validation procedures).
- **`scripts/README.md`, `results/README.md`:** next to what they document.

Personal, machine-specific, or session-specific notes (local setup, per-run
runbooks, working logs) are intentionally kept **outside** this repo and are not
committed here. That includes any local `CLAUDE.md` a contributor keeps at the repo
root to guide their own AI agent: it is personal, stays out of version control, and
each contributor is free to document their own way.
