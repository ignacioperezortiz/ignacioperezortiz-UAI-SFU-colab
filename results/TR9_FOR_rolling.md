# TR9 rolling FOR — reading the workbook

Companion note for **`TR9_FOR_rolling.xlsx`**.

The workbook holds one flexibility operating region (FOR) per half-hour at the TR9
grid connection point (PCC). This note explains what is in it, and — the part that
matters for the next step — which of the two regions to use when we allocate
flexibility between prosumers and when we dispatch it.

---

## 1. What was computed

Each half-hour of the day is a rolling step. For each step the optimizer takes the
next half-hour as the service slot and pushes the PCC operating point as far as it
will go in 12 compass directions: 0°, 30°, … 330°. Each push is one optimization
solve. Joining the 12 resulting vertices gives the boundary of the region.

48 steps × 12 directions = **576 solves, all optimal**.

| Tab | What is in it |
|---|---|
| `1_Summary` | Purpose, sign convention, column glossary, and the recipe for rebuilding one FOR by hand |
| `2_Sample_00h00` | Worked example, period 1 = 00:00. Numbers typed in, so they can be overwritten to test a what-if |
| `3_Sample_12h00` | Worked example, period 25 = 12:00 |
| `4_All_periods` | Master data: all 576 boundary points, plus the baseline and the deviation of each |
| `P02_00h30` … `P48_23h30` | One tab per rolling step, each with both charts. These read from `4_All_periods` |

**Sign convention.** `P > 0` is import from the grid, `P < 0` is export. `Q > 0` means
the inverters absorb reactive power, `Q < 0` means they inject it. Units are MW and
MVAr, per-unit on a 1 MVA base.

---

## 2. The three objects on every tab

**The baseline `B`.** The PCC point with every battery switched off. It is roughly
load − PV, and it also carries the network losses the PV is covering. This is the
part nobody controls in the service slot: the PV output and the load are what they
are. In the workbook it is the peach cell at the top of each tab.

**The absolute FOR.** The 12 vertices as they come out of the solver, plotted as
`P` against `Q`. This is where the region sits in real power terms.

**The deviation FOR.** The same region with the origin moved to the baseline:

```
ΔP = P − B_P        ΔQ = Q − B_Q
```

Same shape, same size, different reference point. `ΔP > 0` means the battery absorbs
more than it would have (charge / import). `ΔP < 0` means it injects more
(discharge / export).

That is the whole difference. **The absolute FOR says where the feeder is. The
deviation FOR says what the batteries can do about it.**

---

## 3. Why the deviation FOR is the one for fairness and dispatch

This is the point of the note. Four reasons.

**The absolute region is dominated by something nobody controls.** At 12:00 the
baseline is −2.2582 MW — a deep export, because PV at TR9 is about 3.5× the local
demand. The region around it is 0.2866 MW wide in P. The *position* of the region is
PV and load. The *size* is the battery. Roughly eight parts position to one part
battery, at that hour. If we allocate on the absolute point, we allocate on the position.

**A flexibility service is a change, not a level.** When a DSO or TSO asks for
something, the request is "200 kW more export for the next half-hour". That request
is a ΔP. It is measured from what would have happened anyway. The absolute value at
the PCC is not the service; it is the outcome of the service plus the baseline.

**Fairness needs a comparable quantity.** Two prosumers with the same battery and
different PV arrays have different absolute FORs and comparable deviation FORs.
Paying on the absolute point pays for owning a large array and a small load. That is
a position, not a contribution. The deviation is what each participant actually
brings.

**The baseline is not a service in the first place.** The PV commitment is already
serving local load, the neighbours' load, and the losses, and the prosumer is not
paid for it. Charging or crediting on the absolute point counts that twice.

> **Use ΔP and ΔQ for anything that allocates, prices, or dispatches.**

---

## 4. Do not throw the absolute FOR away

The network limits bind on absolute quantities. Voltage does not care about
deviations — it responds to the actual injection at the actual hour. **254 of the 576
vertices sit on the 1.10 pu over-voltage limit.** That limit is what shapes the region
in most hours.

So the two views split:

- **feasibility and network checks → absolute FOR**
- **allocation, pricing, and dispatch requests → deviation FOR**

Both are in the workbook, on the same tab, side by side, for this reason.

---

## 5. One caveat about the reference point

The deviation here is measured from the **batteries-off** baseline, not from the
committed self-consumption schedule.

That is a deliberate choice, and it has a consequence: part of ΔP is what the battery
was going to do anyway under its own self-consumption plan. If what we want is
"flexibility on top of the committed plan", the reference has to be the committed
dispatch instead, and the numbers will be smaller.

Neither reference is wrong. They answer different questions. The rule is to **state
which reference a number came from** whenever we quote one. Every ΔP in this workbook
is measured from batteries-off.

---

## 6. Reading one period tab

Each period tab has the 12 vertices, then a small interpretation block that computes
itself:

| Row | Meaning |
|---|---|
| `P width (MW)` | How wide the region is in active power |
| `import-reach (charge)` | `max(0, max ΔP)` — how much more the battery can absorb |
| `export-reach (dischg)` | `max(0, −min ΔP)` — how much more it can inject |
| `verdict` | Whether the region straddles zero, or is one-sided |
| `what stops it` | The voltage at the blocked vertex, when the region is one-sided |

A region that straddles zero can go either way. A one-sided region can only go one
way — and `what stops it` reports the true network voltage at the vertex that is
blocked, so we can see whether the over-voltage limit is active there.

**On `what stops it`:** an active limit at the blocked vertex is evidence, not proof.
Confirming *which* constraint sets the boundary needs the shadow price of that
constraint, and the workbook does not carry duals. When the voltage at the blocked
vertex is clear of the cap, the deduction is safe the other way: the limit is not
voltage, so the battery bounds it.

---

## 7. What the day looks like

| | Periods | When |
|---|---|---|
| Two-sided (can charge or discharge) | 36 | most of the day |
| One-sided, export only | 7 | 08:00–10:30 and 12:00 |
| One-sided, charge only | 5 | 15:30–17:00 and 19:00 |

In **all 12** one-sided periods the blocked direction sits at the 1.10 pu ceiling.

Four periods, to show the range:

| Period | Baseline `B_P` (MW) | import-reach (MW) | export-reach (MW) | Reading |
|---|---|---|---|---|
| 1 = 00:00 | +0.5454 | 0.2296 | 0.2903 | night import, both directions open |
| 13 = 06:00 | −0.6465 | 0.0764 | 0.4518 | PV ramping, export-heavy |
| 25 = 12:00 | −2.2582 | 0.0000 | 0.2874 | solar peak, cannot absorb more |
| 33 = 16:00 | −1.2201 | 0.3954 | 0.0000 | must charge; export blocked at 1.10 pu |

Period 33 is worth a look. The region can absorb up to 0.3954 MW, and it cannot
inject at all. The 180° vertex sits at Vmax = 1.10000 pu. The feeder is at its
voltage ceiling, so more injection is not available at that hour whatever the battery
state is.

Across the day, import-reach peaks at 0.4906 MW and export-reach at 0.4790 MW.
Baselines run from −2.3117 MW (period 26, deepest export) to +1.2369 MW (period 43).

---

## 8. Data, precision, and checks

Boundary points come from the rolling FOR solves exported as `FOR_rolling_TR9.csv`;
baselines from `FOR_rolling_baseline.csv`. Both are regenerated per run and are not
tracked in Git (see `CONTRIBUTING.md` §3).

`P`, `Q`, `proj` and the baselines are stored rounded to 4 decimals, `VmaxTrue` to 5.
The `proj check` column recomputes `P·cos(angle) + Q·sin(angle)` from those rounded
values, so it agrees with the solver's own `proj` to about 1e-4 rather than exactly.

The workbook was checked cell by cell against the two exports before this PR:

- all 576 rows match the solver export on period, angle, `P`, `Q`, `proj`, status and `VmaxTrue`
- all 48 baselines match the baseline export
- every period tab links to the correct 12-row block of `4_All_periods`
- all 576 `proj` values reproduce from `P`, `Q` and the angle
- all 588 computed ΔP / ΔQ match the master sheet
- solve quality: 576 optimal, true voltages within 1.10000 / 0.94454 pu, no limit violations

---

## 9. Open question for discussion

Section 5 is the one to settle before we build the allocation on top of this.

If the fairness mechanism should reward flexibility **beyond the self-consumption
commitment**, the reference point has to move from batteries-off to the committed
dispatch, and every ΔP in this workbook shifts. That is a re-export, not a
recalculation of the FOR itself — the region does not change shape, only its origin.

Worth agreeing on the reference before either of us builds anything that depends on it.
