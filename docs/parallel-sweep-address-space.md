# Why the parallel sweep stalls: address-space fragmentation

**2026-08-28.** A whole-feeder production run at `RollAsyncK = 3` stopped producing
vertices in period 16. Instrumented capture identifies the mechanism, and it is neither
a deadlock nor a memory shortage: **the process address space fragments in proportion to
the number of `GMP::Instance::Copy` / `GMP::Instance::Delete` cycles performed, and every
allocation-heavy operation slows down as it does.**

This supersedes two open items: the "unexplained" period 6-8 slowdown of
`docs/parallel-sweep-memory.md` §5, and the unexplained stalls of
`docs/whole-feeder-production.md` §3. Both are the same effect at different severities.

---

## 1. The run

`RunFullFeeder_ProductionK3` on `main` @ 42fb9d7 — whole feeder, m=0, committed baseline
solved network-free (`BaseNoNetGMP = 1`), sweep parallel at K=3 × 5 threads, strict
formulation. Launched 2026-08-27 23:43:40 headless, on the machine of
`docs/parallel-sweep-memory.md` (Core Ultra 9 185H, 63.45 GB RAM, commit limit 182.55 GB).

It is the first 48-period whole-feeder attempt under the linearization-derivative fix
(PR #21), so its own vertices are not comparable with the 2026-08-17 reference.

**What it produced before stalling: 15 complete periods, 180/180 `Optimal`, zero rescues,
`OVviol` 1.8668e-10 and `UVviol` 0 in every vertex** — plus 6 directions of period 16.
The memory model of `parallel-sweep-memory.md` §4 held exactly: commit peaked at
160.9 GB against the 163 GB predicted, with no drift between periods.

## 2. The stall

Last vertex written 16:48 (period 16, direction 6 of 12 — the end of the second batch of
three). At 18:03 the monitor fired at its 75-minute threshold and captured stacks
non-invasively with `cdb -pv`.

| observation | value |
|---|---|
| threads at 100 % | **1** of 70 |
| that thread | index 0, the AIMMS procedure thread (`AimmsProcedureRunW` at the base of the stack) |
| its accumulated user time | 5 h 46 min of the run's 18.5 h |
| private bytes | **31.00 GB, identical to the centibyte across 12 consecutive one-minute samples** |
| working set | 27.06 GB |
| RAM free | 26.9 GB |
| solver sessions in flight | **none** — a batch in flight shows ~148 GB of private bytes |

31 GB is the shared instance with the previous batch's copies already deleted. The code
is therefore between the collection of batch 2 and the launch of batch 3, i.e. in
`GMP::Instance::Delete` of the last slot or `GMP::Instance::Copy` of the next
(`OPF.ams` ~3000-3110).

### It is not stuck — it is slow

`hang-debug/README.md` states the decisive test: if the spinning thread's stack changes
between samples it is slowness; if it is identical it is a stuck loop. Two samples,
16 minutes apart:

```
18:03  ntdll!NtReleaseMutant+0x14                          <- releasing a mutex
       KERNELBASE!ReleaseMutex+0xd
       libaimms3!...+0x561f6d

18:19  win32u!NtUserMsgWaitForMultipleObjectsEx+0x14
       libaimms3!...+0x561f8b                              <- +0x1e, and one frame deeper
```

The deep recursion below is the same in both; the top frames and the depth move. **The
operation is progressing.** It had been progressing for 95 minutes on a call whose
measured median is 3 s (`parallel-sweep-memory.md` §2).

Note also that the top frame is a mutex *release*, not an acquire. Nothing is waiting on
a lock; one thread is doing serialized work.

## 3. The mechanism: 7.5x more address-space regions

`!address -summary`, against the capture taken on 2026-08-25 during a period-1 probe of
the same configuration family:

| | 2026-08-25, period 1 | 2026-08-28, period 16 |
|---|---:|---:|
| Heap regions | 27 750 | **139 823** |
| `<unknown>` regions | 14 175 | **174 633** |
| MEM_PRIVATE regions | 41 982 | **314 519** |
| committed | 10.98 GB | 31.50 GB |

Region **count** grows 7.5x while committed memory grows 2.9x. The same memory is carved
into an order of magnitude more pieces. Within the 2026-08-25 capture's own five samples,
taken over three and a half minutes, the counts rise monotonically — 27 750 → 28 160 heap,
41 982 → 42 839 private. It grows continuously with work done, and nothing gives it back.

Heap and virtual-memory bookkeeping is serialized under a process-wide lock. As the region
count explodes, every allocation and every free costs more, on one thread, with the other
69 idle. That is the profile observed.

### Why the copies are the driver, not the solves

Per period the async path performs **12 `GMP::Instance::Copy` + 12 `GMP::Instance::Delete`**
of a 6 214 854-row / 6 095 686-column / 24 289 627-nonzero instance. The sequential path
performs **zero**: it reuses `RollGMP`, rewrites two objective coefficients, and calls
`GMP::Instance::Solve` (`OPF.ams` ~3113-3130).

Both paths perform the same 12 barrier solves per period. The sequential path completed
48 whole-feeder periods on 2026-08-17. Therefore the solves are not what accumulates —
the copy/delete cycles are.

### It predicts the two earlier stalls

| run | copy/delete churn per period | stalled at |
|---|---|---:|
| 2026-08-22, K=2 × 12 | 12 copies + 12 deletes + **6 extra full barrier factorisations** (one silent rescue per batch, `parallel-sweep-memory.md` §3) | period 7 |
| 2026-08-28, K=3 × 5 | 12 copies + 12 deletes, zero rescues | period 16 |

Roughly half the churn per period, roughly twice the lifetime. Not proof, but the ratio
falls out of the model rather than being fitted to it.

It also explains why **six instrumented runs on 2026-08-25/26 never stalled**: none went
past period 13. The K=3 evidence run was stopped at 13 periods to free the machine — one
period short of where this run first slowed sharply, three short of the stall.

### And it explains the slowdown that was left open

`parallel-sweep-memory.md` §5 records a cycle time rising from ~64 to ~85 min between
periods 6 and 8 and calls the cause unestablished, having ruled out memory accumulation,
CPU throttling and intrinsic period difficulty. This run reproduced the same climb —

| periods | cycle |
|---|---:|
| 1-4 | 58.2-58.5 min |
| 5 | 60.2 min |
| 6-13 | 64.2-67.2 min |
| 14 | 78.2 min |
| 15 | 87.3 min |

— and then stalled. It is one curve, not a slowdown plus an unrelated hang: the same
degradation, sampled before and after it crosses into the unusable.

The earlier investigation ruled out *memory accumulation* by watching committed bytes,
which are flat. Fragmentation is invisible in that measurement, and that is exactly why it
survived three investigations.

---

## 4. Fixes that keep the parallel sweep

The sweep's parallelism is not the problem. The problem is that the current code obtains
its K independent objectives by **building and destroying K instances per batch**. Every
option below keeps K directions solving concurrently.

### A. Reuse the K copies across the batches of a period — IMPLEMENTED, validated

Create the K copies once per period, before the batch loop. For each batch, write that
direction's two coefficients into copy *k* with `GMP::Coefficient::Set`, create a session,
`AsynchronousExecute`. Delete the K copies when the period's sweep ends.

- **Churn per period: 12 + 12 → K + K.** At K=3 that is a 4x reduction, extrapolating from
  16 periods of life to roughly 64 — enough for a 48-period run.
- **Results cannot move.** Each direction still solves the identical matrix carrying its
  own two objective coefficients. The only change is which physical copy carries which
  direction, and the copies are identical by construction. This is precisely what the
  sequential path already does to `RollGMP`, twelve times per period.
- **Sessions stay per-direction.** `CreateSolverSession` measures 0 s in the trace, so
  there is nothing to win by reusing them and one less state question to answer.
**Implemented as `RollAsyncReuse`** (`Default: 1`), with `RollSlotOf(ia)` naming which
physical copy carries direction `ia`. `RollAsyncReuse = 0` reproduces the previous code
line for line, so the old behaviour stays reachable and the A/B is exact.

**Validated at TR3**, `RunTR3_ReuseA` (0) against `RunTR3_ReuseB` (1), both at K=3 × 4 so a
period is four batches over a pool of three copies:

| | arm A, old | arm B, reuse |
|---|---|---|
| status | 576/576 `Optimal` | 576/576 `Optimal` |
| **max abs dproj** | — | **0.000e+00** |
| P,Q slide | — | **0.00 kW** |
| soc CSV | — | **identical byte for byte** |
| fair CSV | — | **identical byte for byte** |
| wall clock | 19.5 min | 19.1 min |

The one risk — a reused copy retaining a basis and picking a different argmax on a flat
face — did not materialise: there is not even a P,Q slide, which is the symptom that would
have shown first. Copy/delete calls over the 48 periods fell from 576 to 144.

### B. Chunk the run across fresh processes — IMPLEMENTED, validated

Add `RollStartPeriod` and seed the committed state from the previous chunk's
`FOR_rolling_soc_*.csv`, then run 48 periods as, say, four chunks of twelve, each in its
own `AimmsCmd` process. **A fresh process starts with a virgin address space, so
fragmentation resets to zero at every chunk boundary** — whatever else turns out to
fragment, and at whatever K fits memory.

- Nothing inside a period changes, so results are untouched by construction.
- It also removes "there is no resume", which has now cost two runs: the 2026-08-13 run
  died to a Windows Update reboot at 3/48 periods, and this one at 15/48.
**The chained state is exactly `BattSOCstart(bat)`** — read at the top of a period
(`OPF.ams` ~2777) and advanced at the bottom (~3378). Everything else is restored by
`Load_data_reset`, including the linearization point. So the checkpoint is one vector.

**Implemented as** `RollStartPeriod` (first period this process solves), `RollCkptTag` (so
the chunks of one campaign share a checkpoint while each writes its CSVs under its own
`RollFileSuffix`), and a checkpoint rewritten after every period holding the SOC together
with the period it is good for. A mismatch against `RollStartPeriod` halts rather than
chaining the wrong SOC. `scripts/concat_FOR_chunks.py` stitches the chunks and refuses a
gap or an overlap, so a chunk that stopped early cannot become a complete-looking CSV.

**A trap worth recording: the `WRITE` statement rounds.** It emitted the SOC as `0.140` —
three decimals, the identifier's display precision. The rolling horizon chains that SOC, so
a rounded restart perturbs every period after it. Measured: the chunked run still passed
(max abs dproj 1.0e-06 against a 2e-06 tolerance) but only just, and three decimals is
0.001 of battery capacity. The checkpoint is therefore written with an explicit `put` block
at 17 decimals, in the same AIMMS data syntax, which round-trips a double exactly.

**Validated at TR3**: `RunTR3_Chunk1` (periods 1-24) and `RunTR3_Chunk2` (25-48) in two
separate processes, stitched, against `RunTR3_ReuseB` — the same 48 periods in one process.

| | result |
|---|---|
| status | 576/576 `Optimal` |
| **max abs dproj** | **0.000e+00** |
| P,Q slide | 0.00 kW |
| vertex CSV | identical in **every column except `time`**, which is wall-clock solver time |
| soc, fair CSVs | **identical byte for byte** |

`RunFullFeeder_K3_C1` … `C4` apply the same to the whole feeder, twelve periods each.

A and B are complementary: A raises the ceiling, B makes the ceiling irrelevant. Together,
a whole-feeder period costs 3+3 copy/delete calls instead of 12+12, and no process lives
longer than twelve periods — against the sixteen that the 2026-08-28 run survived at 12+12.

### C. Hoist the copies out of the period loop — speculative

If the K copies could be *refreshed* per period instead of recreated, churn would fall to
K copies for the entire run. This requires re-setting every coefficient that changes
between periods — the load/PV linearization coefficients and the committed-state bounds —
which is a large surface and where correctness risk actually lives. Worth scoping against
the AIMMS matrix-manipulation API before anyone commits to it; not worth attempting before
A and B are in.

### D. Segment heap for `AimmsCmd.exe` — a free experiment, not a fix

Windows can opt an executable into the segment heap through the image-file-execution
registry key, which changes how the allocator handles exactly this kind of churn. It is a
per-image, reversible switch: set it, run three or four periods, and compare the region
count growth against this document's numbers. It may do nothing — AIMMS may not use the
Windows heap for these allocations, and 174 633 of the regions are `<unknown>` rather than
`Heap`, which points at direct `VirtualAlloc`. But it costs minutes to test against a
multi-day problem. It is a machine-level change and needs the machine owner's agreement.

### E. The instance-size lever — already on the record

`parallel-sweep-memory.md` §7 notes that 6.21 M rows comes from building the full 48-slot
horizon in every period, while the sweep only asks for the region of slot 2. A shorter
horizon would shrink the copies by the same order of magnitude and none of this would
bind. It is a modelling question for Luis and Tulio, not a tooling change.

### What will not work

- **Lowering K.** Fewer concurrent sessions, same twelve copies per period. K=2 × 12 died
  *sooner*, because its silent rescue added a full barrier factorisation per batch.
- **`RollAsyncHoist`** (in the diagnostic build, `hang-debug/patch/instrument.py` step 7).
  It reorders the launch so no copy overlaps an active solve, addressing the superseded
  "copy during a solve" hypothesis. It does not change how many copies are made.
- **A solve time limit.** It would convert a silent stall into a failed run. Useful for
  alarming, not for finishing.

## 5. Two things worth fixing regardless

- **Record that a rescue happened.** Already open in both existing documents. It is now
  also a churn measurement: the rescue is what made K=2 fragment twice as fast, and it is
  invisible in the CSVs.
- **Alarm on a stall, and make the threshold survive the diagnosis.** The 75-minute
  monitor did its job here. Note that its stack capture holds the target frozen for
  ~16 minutes per sample on a process this size, so a five-sample capture starves exactly
  the measurement one wants next; two samples answer the moving-versus-stuck question.

## 6. Reproducing the measurement

```powershell
# while a whole-feeder run is in a period's sweep
hang-debug\tools\capture-stacks.ps1 -ProcessId <pid> -OutDir <dir> -Repeat 2 -GapSeconds 900
```

Then compare, between the two samples:

- the stack of the thread named first by `!runaway` — moving means slow, identical means stuck;
- the `RgnCount` column of `!address -summary` for `Heap`, `<unknown>` and `MEM_PRIVATE`.

Region count, not committed bytes, is the quantity that tracks this failure.
