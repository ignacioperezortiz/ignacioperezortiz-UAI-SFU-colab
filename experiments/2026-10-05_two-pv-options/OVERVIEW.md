# What changed in the model, and what we found

**For Ignacio. From Tulio, 6 Oct 2026.**

This note explains what I changed in the model since 30 Sep, why I changed it, what the results are, and how I
plan to put it in the paper. The last section is for you: where fairness fits in.
How to run the model is in [`README.md`](README.md). All the numbers are in
[`results/RESULTS.md`](results/RESULTS.md).

## The short version

1. **Self-consumption comes first.** In the old model, a TSO request could make a house buy more energy later
   in the day. I added a rule so this never happens. The FOR keeps about 90 % of its size.
2. **The TSO always picks a point inside the FOR.** To deliver it, we do not solve a new optimisation. We mix
   the battery set-points that we already stored when we built the FOR. This always gives the exact point.
3. **The FOR is built only when the TSO asks for it.** Building it is the slow part. A FOR that nobody uses
   changes nothing, so we skip it. The model can still build it every half-hour if we want.
4. **PV surplus has three possible rules:**
   - (i) it is sent to the grid;
   - (ii) it is sent to the grid, but it can be cut when the TSO's point needs it;
   - (iii) it can only go to the grid if the TSO agrees, so most of the time it is cut at the house.
5. **The batteries help to cut less PV.**
   - Rule (ii): if the batteries charge at the PV peak instead of in the early morning, we cut **23 % less PV**
     for the same service. Using the batteries first when we deliver a point saves another **8-16 %**.
   - Rule (iii): when the batteries give energy to the TSO, the PV that would be cut refills them. We save
     **0.84 kWh of PV for each kWh given**.
   - Charging at the PV peak is bad for rule (iii), so in the paper we use it only with rule (ii).
6. **Fairness is the open part, and you are the one to do it.** Section 5 explains what needs to change.

## 1. The idea behind it

Self-consumption is the first priority. The TSO can only use the battery flexibility that is left over.
The FOR must make sure of this.

- **How we check it in every test:** no house may buy more energy from the grid later than in its normal plan
  (P1). Selling more is not a problem.
- **The FOR is one of the main contributions of the paper.** The DSO shows it to the TSO, the TSO chooses a
  point inside it, and that point can always be delivered.

## 2. What I changed, and why

| # | Problem | What I changed | Switch in AIMMS |
|---|---|---|---|
| 1 | In the old model, one TSO request could make houses buy much more later: up to 81.9 kWh in total on TR9, 3.4 kWh for one house. The cause: P1 gave no weight to the service half-hour (`w2(PeriodMaxP) = 0`), so it left free discharge there. | P1 now treats that half-hour like the others. When the FOR is built, no house may buy more than its P1 plan in any later half-hour. | `SCFirst = 1`, `SCNoImportFuture` with `SCAlpha = 0` |
| 2 | A TSO asking every half-hour could add up the small 1 W tolerance of that rule many times: one house bought 110 Wh more. | The same rule, with a much smaller tolerance (0.01 W). Worst house afterwards: 1.3 Wh. | `SCTight = 1` |
| 3 | When the TSO asked for a fixed number of kW, the FOR was not really used. | The TSO picks a point inside the FOR. The battery set-points are a weighted mix of the stored solutions. If the mix asks one battery to charge and discharge at the same time, it only does the difference. | `SRQ_Mode = 2` (the `FRQ_*` code) |
| 4 | Building the FOR every half-hour is slow, and most FORs are never used. | Build it only for the half-hours with a request. The results do not change. | `FRQ_SweepAll = 0` |
| 5 | PV could not be cut. | Rule (ii): in the service half-hour, each house can cut its PV surplus (PV minus its own demand), never the PV it uses itself. | `PVC_On = 1`, `PVC_Mode = 1` |
| 6 | With a "no export" rule, a lot of PV is lost every day. | Rule (iii): P1 cuts the surplus instead of exporting it. In the FOR, PV does not change; only the batteries do. PV that would be cut later refills the batteries. | `ZX_On = 1` |
| 7 | P1 fills the batteries in the morning, so at midday they are full. If the TSO then asks for less export, we must cut PV. | A second, small P1 problem: the house buys the same, the battery cycles the same and has the same energy at sunset and at the end of the window, but the charging moves to the PV peak. | `SRQ_Coord = 1` |
| 8 | When we mix stored solutions, we also mix their PV cuts, even when the batteries alone could do the job. | For each FOR corner that cuts PV, we also store a "battery-only" version of it. When we deliver a point, we choose the mix with the least PV cut. This is simple arithmetic, not an optimisation. | `FRQ_BF = 1` |
| 9 | A few rare solver problems. | Small automatic retries. | always on |

Two things to keep in mind:
- **There are no binary (integer) variables.** Every problem is convex, solved with CPLEX.
- **Convex is important.** It is the reason why mixing stored solutions always gives a feasible, exact
  point. Fairness must keep it this way.

## 3. Results (TR4, one sunny day, 6 Oct)

I ran 66 days: 4 cases × 16 different TSO behaviours. Some TSO behaviours pick random points inside the FOR,
some pick points on its edge, and two are worst cases: the TSO asks for the most export, or the most
import, every half-hour.

**Checks**
- All 800 TSO requests were delivered. The real point was never more than 0.042 kW away from the chosen one.
- Outside the half-hours of the TSO requests, no house bought more than 3.8 Wh extra (compared with the same
  day without requests).
- No solver failure.

| | Rule (ii), normal charging | Rule (ii), charging at the PV peak | Rule (iii), normal charging | Rule (iii), charging at the PV peak |
|---|---|---|---|---|
| PV cut on a day without TSO requests | 0 | 0 | 802 kWh | 801 kWh |
| PV cut for each kWh of "export less" | **0.64** | **0.49** (23 % less) | — | — |
| PV saved for each kWh of "export more" | — | — | **0.84** | 0.37 |
| Same, old mix → batteries first | 0.70 → 0.64 | 0.59 → 0.49 | — | — |
| Average FOR size at the requests (kW × kvar) | 74 500 | 78 800 | 55 200 | 60 800 |

From the earlier tests:
- With the fix, a day with 16 TSO requests ends with the same purchases as a day without requests.
- 1 276 TSO points in 88 days were all delivered exactly.
- With rule (iii), PV saved ≈ 0.98 × "export more" − 0.66 × "import more".

**Prices to pay**
- Charging at the PV peak gives about 40 % more room for "export less" at midday, but about 30 % less
  "export more" in the morning.
- With rule (iii), when the TSO asks for "import more", more PV is cut (+161 kWh in the worst case), because the
  batteries fill up from the grid.

## 4. How it goes into the paper (IEEE TSG, working file `v52.tex`)

| Section | What it says | Status |
|---|---|---|
| I Framework | The method is general: the FOR on request (new box in Fig. 2) or every half-hour; the three PV rules; charging at the PV peak with rule (ii) | done |
| II P1 | Rule (iii) PV cut (eq. 9); charging at the PV peak (P1^c, eq. 10) | done |
| III P2 | The self-consumption rule (0.01 W); the PV cut in the FOR (ii) or fixed PV (iii); delivery by mixing, batteries first; **fairness (Section III-C, still empty, yours)** | next |
| IV Case study | The four cases; FOR size, PV cut, self-consumption check; time saved by building the FOR only on request | after III |

Still open (with the supervisor or with you):
- When we mix stored solutions, do we use (a) the no-request point plus two corners, or (b) only corners?
  With fairness we need (b). See below.
- The paper says P1 is solved at the house, without the network. The simulations solved P1 with the network.
  For the final runs we should switch the network off in P1.

## 5. Fairness: what needs to change

Your fairness code (FairMode 1-4) is in this model, unchanged.
- **Where it acts:** only when the FOR is built, not in P1 and not in the second P1 problem.
- **How to switch it on:** add `FairMode := 2 ;` (or 1, 3, 4) to `scenario.txt`.

The exact places in the code are in the README. What needs a decision or a change:

1. **Mix only fair solutions.**
   - The "no request" point (the P1 plan) is usually not fair. With modes 3-4 it may even be outside the fair
     FOR.
   - Today the code builds the FOR from the no-request point plus the corners, and uses that point in the mix.
   - With fairness on, the FOR and the mix should use only the corners (and their battery-only versions).
   - Your fairness rows are linear, so a mix of fair solutions is still fair. The delivery stays exact.
2. **Should cutting PV be shared fairly?** (rule ii)
   - Modes 1-2 share only battery power. The PV cut is not shared.
   - Modes 3-4 share the whole exchange of the house, so the PV cut is included.
   - We need to choose one for the paper.
3. **The battery-only versions are already fair.** They are solved on the same matrix, with your fairness
   rows on.
4. **Self-consumption rule + fairness.**
   - With the new rule, some batteries cannot give energy without making their house buy later. For
     fairness, they act like empty batteries.
   - With mode 1, one such battery can stop the whole fleet (your 35.8 % finding).
   - It is worth one test of mode 1 vs mode 2.
5. **A first test I suggest:** rule (ii) with both charging types, FairMode 0 vs 2, on the day without
   requests, the edge pattern and 6 random patterns (about 4 hours on 3 licences).
   - Compare: FOR size, PV cut, self-consumption, and that delivered points stay exact.
