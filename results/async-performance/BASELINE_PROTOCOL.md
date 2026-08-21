# Controlled-baseline campaign — protocol

**Goal.** Re-run all nine transformers so their wall clocks are comparable **to each
other**. The August 17–18 campaign was not: it ran across a batch, across days, and
across whatever else the machine was doing. A measured **1.48×** of it turned out to
be session state rather than the model.

One rule carries the whole thing:

> **One transformer per fresh AIMMS session.** Open AIMMS, run one `RunTRn_Base`,
> close AIMMS without saving. Repeat.

Closing between runs is not housekeeping. It is what makes the base the same.

---

## 1. Prepare the machine (once)

**Reboot.** The box has been up 20 days. A reboot clears heap fragmentation, the
page file, and the stale `aimms.exe` that has been idle since Aug 13 — that stale
process would also confuse the run logger, which treats "an AIMMS process exists"
as "a run is in progress".

**After the reboot, close everything you do not need.** Measured today, with no
AIMMS running, ~13.6 GB of the 31.7 GB was already committed. The reclaimable part:

| | held |
|---|---:|
| Edge + WebView2 (28 processes) | ~2.0 GB |
| Notion (6 processes) | ~1.4 GB |
| Teams | ~0.2 GB |
| postgres (25 processes) | ~0.2 GB |

That is ~3.8 GB. It matters more than it looks: the large transformers are
**memory-bandwidth bound**, which is exactly why 6 concurrent solves lost to 4 on
TR6. Leave Notion and the browsers closed for the whole campaign.

Leave alone: `SentinelAgent`, `MsMpEng`, `CcmExec`, the Dell agents. They are
managed, and consistency matters more than squeezing them out — they are part of
the base as long as they are the same for every run.

**Already correct, no action needed** (verified today):

- power plan **High performance**, processor min and max both **100%** — no downclocking
- sleep and hibernate **disabled** on AC
- 24 physical cores, 32 logical, 31.7 GB

## 2. Start the logger (once)

```
powershell -ExecutionPolicy Bypass -File scripts\watch_runs.ps1
```

Start it after the reboot, before the first run, and leave it running for the whole
campaign. Ctrl+C when finished. It writes to `results/async-performance/baseline/`:

| file | what |
|---|---|
| `env_header.txt` | machine state at campaign start — the base itself |
| `env_log.csv` | one sample per 30 s: AIMMS RSS, free RAM, commit, CPU% |
| `env_events.txt` | AIMMS open/close, with each session's wall clock |

It touches nothing in the model. Its job is to make a disturbed run **identifiable**
rather than a mystery later.

## 3. Run, one at a time

For each transformer: **open AIMMS → run one procedure → close without saving.**

| order | procedure | batteries | split | estimate |
|---|---|---:|---|---:|
| 1 | `RunTR4_Base` | 46 | 6×4 | ~19 min |
| 2 | `RunTR3_Base` | 49 | 6×4 | ~20 min |
| 3 | `RunTR1_Base` | 77 | 6×4 | ~25 min |
| 4 | `RunTR9_Base` | 90 | 6×4 | ~75 min |
| 5 | `RunTR2_Base` | 95 | 6×4 | ~57 min |
| 6 | `RunTR8_Base` | 124 | 4×6 | ~3.1 h |
| 7 | `RunTR5_Base` | 214 | 4×6 | ~3.0 h |
| 8 | `RunTR7_Base` | 259 | 4×6 | ~4.9 h |
| 9 | `RunTR6_Base` | 262 | 4×6 | ~4.4 h |

Smallest first, on purpose: the first four finish in about 2.5 h and prove the
protocol before the long ones commit a night. **Total ~18.6 h.**

Estimates are projections from the August numbers, not measurements. Ranking them by
size is the point — if the measured order does not track battery count, something in
the base moved.

Each run writes `FOR_rolling_TRn_base.csv` plus its `_soc_` and `_fair_` files.
Nothing from the earlier passes (`_gmp`, `_async`, `_asyncB`) is touched.

## 4. Rules that keep the base the same

- **Do not use the machine during a run.** Not for browsing, not for Notion, not
  for opening the result CSVs. Reading a CSV mid-run is cheap; loading a browser is
  not.
- **Do not run two transformers in one session.** That reintroduces the exact
  confounder this campaign exists to remove.
- **Close AIMMS without saving, every time.** AIMMS rewrites all of `OPF.ams` on
  save and would overwrite the `_Base` procedures with its in-memory copy.
- If you must interrupt, note which transformer, and re-run that one from a fresh
  session. Do not patch a partial result — `RunFOR_Rolling` writes its CSVs with a
  single `putclose` at the end, so an interrupted run leaves them empty anyway.

## 5. Afterwards

For each transformer, wall clock comes from the CSV timestamps (`CreationTime` →
`LastWriteTime`) and is cross-checked against `env_events.txt`. Then:

```
py -3 scripts/compare_FOR_runs.py FOR_rolling_TRn_gmp.csv FOR_rolling_TRn_base.csv --tol 5e-5
```

`5e-5` rather than `5e-6` because the async drift grows with instance size — see
§5 of `README.md`. The checks that must hold regardless: **576/576 Optimal**, and
the `_soc_` file **bit-identical** to the sequential twin.

---

## 6. Outcome — campaign complete, 2026-08-20

All nine ran under this protocol on 19–20 August. **35.72 h → 19.62 h, 1.82×.**
Full results in `README.md` §3 and `timings.csv`; per-run timings in
`baseline/base_timings.csv`; the environment log in `baseline/`.

The protocol did its job twice over:

- **It caught a crash.** TR3's first attempt died at period 17 (AIMMS fault, dump in
  `log/ErrorReports/`). The resource log placed the crash at 11:22:44 and showed the
  infeasibility messages arriving seven minutes *later* — symptom, not cause. It also
  ruled out memory: 21.3 GB free at the worst point. The rerun completed cleanly, so
  the fault was transient.
- **It caught a bad measurement of mine.** After that rerun the CSV appeared to show
  54.3 min, because AIMMS overwrites the file in place and `CreationTime` still pointed
  at the crashed run. The real figure, from the CPU trace, was 20.1 min.

> **Timing rule that came out of this:** `CreationTime` → `LastWriteTime` is valid only
> for a file created fresh. For any rerun to an existing filename, take the wall clock
> from `env_events.txt` and the CPU trace. Session wall ≈ run + ~3 min of AIMMS load
> and shutdown.

One protocol slip worth noting: AIMMS was several times left open and idle for hours
after a run finished (once for eight). Harmless here, since the next run began with a
fresh session either way — but it is what the "close without saving" step exists to
prevent.
