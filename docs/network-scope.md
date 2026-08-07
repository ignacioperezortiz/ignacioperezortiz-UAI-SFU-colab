# Network scope and formulation — what each run configuration covers

The model runs at two network scopes and in two formulations. Both are supported and both are
useful; this note records what each one is, what it costs, and which one produced the results in
`results/`.

---

## 1. Two scopes

| | `ReduceNetwork` | `DetailTagCSV` | Entry points |
|---|---|---|---|
| **Per transformer** | 1 | e.g. `"TR9"` | `RunTR1`…`RunTR9` → `RunTrafoFOR(tag)` |
| **Whole feeder** | 0 | `""` | `RunFOR_RollingPreflight` (with `PreflightReduce = 0`) |

`ApplyNetworkReduction` keeps one transformer in full detail and lumps the others as passive MV
load at their own buses. The reduction is documented in the procedure's own comment: the aggregated
transformers' impedance and losses are not modelled, and **their batteries are dropped**. A
reduced-network region is therefore the flexibility of one transformer's fleet against a shared
passive background, measured at the feeder PCC — `results/TR9_FOR_rolling.md` §1 works through that
distinction and reconciles the two numbers.

`RunFOR_Rolling` is the shared engine and **does not set the scope itself**: it uses whatever
`ReduceNetwork` holds. `RunTrafoFOR` sets it to 1, and `RunTR1`…`RunTR9` reach it through that;
a fresh session starts at 0. Setting it explicitly in a new wrapper keeps the run
self-describing.

Regions from several transformers are combined afterwards in post-processing with
`scripts/combine_FOR_pertrafo.py`, which subtracts the shared all-idle background. That background
(`FOR_rolling_baseline.csv`, from `RunFOR_Rolling_Baseline`) is produced **on the same reduced
network as the sweeps**, which is what keeps the Minkowski anchor consistent.

## 2. Two formulations

| | `FOR_PolyS` | `FOR_LinearizeVmax` | Inverter capability | Voltage cap |
|---|---|---|---|---|
| **Exact** | 0 | 0 | quadratic S-circle | quadratic |
| **Linearized** | 1 | 1 | 16-gon | tangent plane |

The exact form is what `RunFOR_Rolling` uses, and each `results/TR*_analysis.md` states it on its
line 3. It is a convex QCP under CPLEX barrier.

The linearized form is a **relaxation**: the tangent plane admits points the exact cap rejects, so
its vertices can report `VmaxTrue` above the 1.10 p.u. limit with `OVviol > 0`, and the region comes
out slightly larger. The repository has characterised this per transformer for some time — see the
"Exact vs linearized" notes in `results/TR1_analysis.md` and `results/TR9_analysis.md`, where the
exact region sits inside the linearized one. Measured on one whole-feeder slot, the same comparison
gives:

| Angle | `proj` exact | `proj` linearized | Difference |
|---|---|---|---|
| 0° | 1.311626 | 1.323508 | +0.9 % |
| 30° | 2.246051 | 2.276939 | +1.4 % |
| 60° | 3.257992 | 3.292617 | +1.1 % |

with `VmaxTrue` at most 1.10000 and `OVviol` at numerical zero in the exact run, against 1.10556 and
5.6e-03 in the linearized one. *(Three of twelve directions; the linearized sweep of that slot was
stopped early.)*

`RunFOR_RollingPreflight` defaults to the linearized form because its purpose is a solver smoke test
and a timing measurement at scale. `PreflightExact = 1` switches it to the exact form when the
vertices themselves are of interest.

`OVviol` is written to every CSV, which makes a relaxed run recognisable: `OVviol > 0` only happens
under the linearized cap. The converse does not hold — a linearized run whose vertices land inside
the true cap reports `OVviol` at numerical zero too, so the configuration is worth recording
alongside the file rather than inferred from it.

It is also worth noting that the preflight differs from production in more than the formulation: it
sweeps three representative slots with no SOC carried between them, runs `RollCyclicSOC = 1`, and
pins `FairMode = 0`. It is a scale and timing instrument, not a short production run.

## 3. What each combination costs

Whole feeder, with the GMP flags of `docs/rolling-for-performance.md` §6. Solver time is per
vertex and measured; generation is **per period** — once per period is the point of those flags —
and the exact figure is derived by difference rather than timed directly:

| Formulation | Solver (per vertex, measured) | Generation (per period) |
|---|---|---|
| Linearized | ~236 s | ~665 s |
| Exact | ~287 s | ~1,005 s (derived) |

Per vertex that is **+22 %** on the solver; once the generation is counted, the exact form costs
about **+43 %** per period. A fraction, not a multiple. Its matrix is 7,534,679 rows × 6,095,687
columns with 26,929,278 nonzeros, and the generated instance is 904.91 Mb; the generator's working
memory is much larger and is released per period.

Projected over a 48-period day on the whole feeder, with one generation per period:

| Formulation | Per period | Simulated day |
|---|---|---|
| Linearized | ~3,700 s | ~2.1 days |
| Exact | ~5,300 s | ~2.9 days |

*Projections, not measurements: they extrapolate from three slots and assume a baseline solve cost
derived by difference.* For the measured per-vertex figures see `docs/rolling-for-performance.md`
§7.3.

The reduced network is far cheaper: the production TR9 case is **3 h 40 min** for a 48-period day
without the GMP flags, and the three-criterion chain (`FairMode` 0/1/2) runs in **9 h 37 min** with
them — see `docs/rolling-for-performance.md` §7.1.

## 4. Where the published results come from

Every file in `results/` was produced **per transformer, in the exact formulation**: `RunFOR_Rolling`
sets `FOR_PolyS := 0` and `FOR_LinearizeVmax := 0` in its own body, and each `results/TR*_analysis.md`
states the configuration on line 3. The linearized procedures (`RunFOR_TR9_Linearized`,
`RunFOR_4Vertices`, `RunCompareWithPaperT25`, the `Diagnose*` family) write to their own files, which
are comparison and diagnostic artefacts.

A 48-period run on the whole feeder has not been completed yet. The whole-feeder figures quoted here
and in `docs/rolling-for-performance.md` §7.3 come from the 3-slot preflight, which is what that
procedure exists for.

## 5. Choosing

- **Per transformer, exact** — the production path, and the one every published result uses.
- **Whole feeder, linearized preflight** — sizing a run, checking the solver holds at scale, timing.
- **Whole feeder, exact** (`PreflightExact = 1`) — pricing the reportable formulation at full scale.
- **Coupling between transformers** — `RunCoupledFOR` sweeps a set of tags together, which measures
  the gap the per-transformer decomposition leaves.

On what to record alongside a run, see `CONTRIBUTING.md` §7.

One practical note for long runs: `RunFOR_Rolling` writes its CSVs with a single `putclose` at the
end, so an interrupted run leaves them empty. The preflight closes its CSV after every vertex
(`PreflightFlushCSV`); carrying that over to `RunFOR_Rolling` is worthwhile before committing to a
whole-feeder day.
