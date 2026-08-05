# Contributing — collaboration guide

Working agreement for the UAI–SFU collaboration on this repository.

The central constraint that shapes everything below:

> **`MainProject/OPF.ams` is a single ~5,900-line file, and AIMMS rewrites it wholesale
> on save.** A three-line edit can produce a several-hundred-line diff. Two people
> editing it on long-lived parallel branches will produce a merge that is painful at
> best and unresolvable at worst.

Every rule here exists to keep that from happening.

---

## 1. The workflow, step by step

This is the cycle for **every** piece of work, however small. Follow it in order.

### Step 1 — Say what you are about to do

Before touching anything, tell the other person which model sections you intend to
edit and roughly for how long.

This is not a formality. With one monolithic model file, human coordination prevents
more conflicts than any merge tool can resolve. A thirty-second message avoids hours
of untangling later. **If you skip only one step in this list, do not let it be this
one.**

### Step 2 — Start from an up-to-date `main`

```bash
git checkout main
git pull origin main
```

Never branch from a stale `main`. Everything you do afterwards inherits that staleness.

### Step 3 — Create a branch for the work

```bash
git checkout -b feature/<short-description>
```

Naming: `feature/<topic>`, `fix/<topic>`, `docs/<topic>`, `exp/<topic>` for throwaway
experiments. One branch = one idea.

### Step 4 — Absorb the AIMMS reformat before editing

Open `OPF.aimms` in AIMMS, save immediately **without changing anything**, close, then:

```bash
git diff --stat
```

If AIMMS rewrote the file, commit that noise on its own **before** making any real
change:

```bash
git add MainProject/OPF.ams
git commit -m "chore: AIMMS reformat on open (no semantic change)"
```

If there is no diff, go straight to step 5. See section 2 for why this matters.

### Step 5 — Make your change, in small commits

```bash
git add <files>
git commit -m "<type>: <what changed and why>"
```

Commit early and often. Small commits are reviewable and recoverable; one 800-line
commit after two weeks is neither. Prefixes: `feat:`, `fix:`, `docs:`, `chore:`,
`refactor:`, `exp:`.

### Step 6 — Rebase onto `main` every day

```bash
git fetch origin
git rebase origin/main
```

**This is the habit that keeps this repository workable.** It converts one
catastrophic merge into a series of small, comprehensible ones. If a conflict appears
in `OPF.ams`, resolve it immediately, while you still remember the context — and if
it looks ambiguous, message the other person rather than guessing at their intent.

### Step 7 — Check what you are about to publish

```bash
git status --short
git diff --cached --stat
```

Confirm that only the files you meant to change are there, and that nothing from
section 3 slipped in.

### Step 8 — Push and open a pull request

```bash
git push -u origin feature/<short-description>
```

Then open the PR on GitHub, fill in the description (section 4), and **tell the other
person it is waiting** — a PR nobody has been told about is a branch that goes stale.

### Step 9 — Review, merge, and get back in sync

The other person reviews and merges. Once merged, **everyone returns to `main`
immediately**:

```bash
git checkout main
git pull origin main
git branch -d feature/<short-description>
```

Do not start the next piece of work from the old branch. Go back to step 1.

---

## 2. Dividing the work

The model is organised into these sections (see `MainProject/OPF.ams`):

`Configuration` · `InputData` · `NetworkModel` · `BatteryModel` ·
`SelfConsumptionOPF` · `FOR_Computation` · `NetworkReduction` ·
`RollingHorizonFOR` · `Validation` · `ResultsOutput`

**Divide work by section, not by file.** Two people in different sections of the same
file still conflict textually, but the conflicts are localised and resolvable. Two
people in the same section at the same time is the case to avoid entirely — and the
only thing that prevents it is step 1.

Keep branches short-lived. Target: merged within a week. If a piece of work cannot be
finished in a week, split it into stages that can each be merged independently.

### Why the AIMMS reformat gets its own commit

When you open `OPF.aimms` and save, AIMMS may reorder declarations, renumber, or
rewrite formatting across the whole file. If that noise lands in the same commit as
your actual edit, the reviewer cannot see what you changed — the diff is hundreds of
lines of churn with three meaningful ones buried inside. Isolating it in its own
commit keeps the next diff readable.

---

## 3. What must never be committed

The `.gitignore` already covers these, but be aware of *why*:

| Never commit | Reason |
|---|---|
| `Database.mdb`, `Database.dsn`, `OpData.xls` | Input data — too large; shared over cloud storage |
| `FOR_rolling*.csv` | Regenerated on every run |
| `*.aimmslockfile`, `backup/`, `log/`, `PROTemp/` | AIMMS runtime artifacts |
| `gurobi.lic` or any license file | **Contains credentials** |

Machine-specific files that should not be imposed on the other person belong in
`.git/info/exclude`, which is local and never committed — not in `.gitignore`, which
is shared.

---

## 4. Pull requests

**Everything goes through a PR. No direct pushes to `main`, by either of us.**

A good PR description for this project answers:

1. **What changed** — which sections and procedures.
2. **Why** — the modelling or numerical motivation.
3. **How it was validated** — which procedure was run, and what the numbers were.
   Compare against the reference values in `results/` where applicable.
4. **Does it change results?** If yes, say by how much and why that is expected.
5. **Does it need new input data?** If yes, say where that data lives and what it is.

Keep PRs focused. One idea per PR. A PR touching four unrelated sections cannot be
reviewed properly.

**Review before merge**, always — even for small changes. In a monolithic model file,
a second pair of eyes catches the accidental edit that a diff makes easy to miss.

---

## 5. Reproducibility: results must be traceable to code

Any result that could end up in the thesis or a paper must be traceable to the exact
code and input data that produced it. When reporting a run, record:

- the **commit hash** (`git rev-parse --short HEAD`)
- whether the tree was **clean** (`git status --porcelain` empty)
- which **input data case** was loaded
- which **procedure** was run and with which key parameters

Never report a number produced from a dirty working tree. Commit first, then run.

---

## 6. Input data and study cases

Input data is not in Git (see section 3). It is versioned as **study cases** — each
case is a self-contained set of `Database.mdb` + `Database.dsn` + `OpData.xls`
representing one modelling scenario.

Current cases:

| Case | Contents |
|---|---|
| `v1_baseline` | Original network and prosumer data — the reference for all validation |
| `v2_agregadores` | Multi-aggregator DER indexing (currently an exact copy of `v1_baseline`; placeholder for the aggregator work) |

Rules:

- **`v1_baseline` is frozen.** It is the reference against which every result in
  `results/` was produced. Never edit it in place.
- **A new modelling scenario means a new case folder**, not an edit to an existing one.
- Only one case is loaded into the repo root at a time.
- When a PR depends on a new case, say so in the description and make the data
  available to the other person before requesting review.

If the two of us diverge on input data, results stop being comparable — which
silently invalidates any comparison against `results/`.

---

## 7. Validation baseline

`results/TR<n>_analysis.md` holds the reference numbers for each transformer. Before
trusting a modified model, reproduce the relevant baseline and confirm the metrics
still match — or explain deliberately why they should not.

TR9 reference (from `results/TR9_analysis.md`, case `v1_baseline`):

| Metric | Value |
|---|---|
| PV generated | 2,241 kWh/day |
| Demand | 643 kWh/day |
| Exported | 1,551 kWh/day |
| Imported | 13.6 kWh/day |
| SCR | 30.8 % |
| SSR | 97.9 % |
| Solve status | 48/48 baselines, 576/576 vertices Optimal; OVviol = 0 |

Recommended validation ladder, cheapest first:

```
MainInitialization  ->  Load_data_dsn         (plumbing: ODBC -> Access)
RunReducedTest_RollingMicro                   (12 batteries — ~10 min)
RunTR9                                        (90 prosumers — ~3 h 40 min)
RunFOR_RollingPreflight, PreflightReduce = 0  (whole feeder, 3 slots — hours)
```

Every reference number above is **per transformer** (`ReduceNetwork = 1`), in the exact
formulation. A whole-feeder 48-period run has not been completed; the preflight is the rung
that covers that scale. `docs/network-scope.md` sets out what each scope and formulation
covers and what they cost.

Two things are worth recording alongside a result, so it stays self-describing: the network
scope (`ReduceNetwork` / `DetailTagCSV`) and the formulation (`FOR_PolyS` /
`FOR_LinearizeVmax`) with the observed maximum `OVviol`. The linearized configuration relaxes
the voltage cap, so it reports `OVviol > 0` by construction and its regions come out slightly
larger than the exact ones — useful for timing and smoke tests, and worth naming as such when
the numbers travel.

---

## 8. Quick reference

```bash
# 1. tell the other person what you are about to touch

# 2-3. start clean, branch
git checkout main
git pull origin main
git checkout -b feature/my-change

# 4. absorb AIMMS reformat noise first, if any
git diff --stat
git add MainProject/OPF.ams && git commit -m "chore: AIMMS reformat on open"

# 5. real work, in small commits
git add <files> && git commit -m "feat: ..."

# 6. stay current — every day
git fetch origin && git rebase origin/main

# 7. check before publishing
git status --short
git diff --cached --stat

# 8. push, open PR, and say so
git push -u origin feature/my-change

# 9. after merge, resync and delete the branch
git checkout main && git pull origin main
git branch -d feature/my-change
```
