# TR9 rolling FOR — reading the workbook

Companion note for **`TR9_FOR_rolling.xlsx`**.

The workbook holds one flexibility operating region (FOR) per half-hour, computed
at the feeder's point of common coupling, with **TR9's batteries as the flexible
resource**. This note explains what is in it, and — the part that matters for the
next step — which of the two regions to use when we allocate flexibility between
prosumers and when we dispatch it.

---

## 1. Where the region is measured

Worth being precise about, because the file name says TR9 and the measuring point
does not.

**The PCC is the feeder's slack / HV bus** (`docs/FOR_demo_runbook.md`). `P_PCC` and
`Q_PCC` are summed over the slack-bus phases, import-positive. So every (P, Q) in
this workbook is a **whole-feeder** quantity: all nine transformers, all 172+ loads,
every PV panel.

What makes the file "TR9" is not the measuring point but the resource:

```
PCC operating point  =  B(t)  +  (TR9's battery flexibility)
```

The eight other transformers are lumped as passive loads in this run, their batteries
idle. This matches `results/FOR_interpretation/FOR_reading.md`, which is the reference
for the convention.

A number that makes it concrete. At period 25 the baseline is −2.2582 MW. TR9's own
net load minus PV at that period is **−0.1784 MW**. The sum over all nine transformers
is **−2.2803 MW**, and the 22 kW gap to the baseline is network losses. The region
rides the whole feeder, not TR9.

---

## 2. What was computed

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

## 3. The three objects on every tab

**The baseline `B`.** The PCC point with every battery on the feeder switched off. It
is the whole feeder's passive imbalance — load minus PV across all nine transformers,
plus the network losses. Nobody controls it inside the service slot. It swings from
about +0.5 MW overnight to −2.3 MW at midday and back to +1.2 MW in the evening peak.
In the workbook it is the peach cell at the top of each tab.

**The absolute FOR.** The 12 vertices as they come out of the solver, plotted as
`P` against `Q`. This is where the feeder sits.

**The deviation FOR.** The same region with the origin moved to the baseline:

```
ΔP = P − B_P        ΔQ = Q − B_Q
```

Same shape, same size, different reference point. `ΔP > 0` means TR9's batteries
absorb more than they would have (charge / import). `ΔP < 0` means they inject more
(discharge / export).

That is the whole difference. **The absolute FOR says where the feeder is. The
deviation FOR says what TR9's batteries can do about it.**

---

## 4. Why the deviation FOR is the one for fairness and dispatch

This is the point of the note.

### The absolute region cannot tell the transformers apart

The argument in one table. Period 25, the same period, from the nine per-TR runs:

| Run | Max P reached (MW) | **P width of the region (MW)** |
|---|---|---|
| TR1 | −2.2663 | 0.1936 |
| TR3 | −2.2916 | 0.1848 |
| TR4 | −2.2927 | **0.1782** |
| TR5 | −2.1852 | **0.6559** |
| TR6 | −2.1647 | 0.3440 |
| TR7 | −2.1749 | 0.3810 |
| TR8 | −2.2372 | 0.3144 |
| TR9 | −2.2590 | 0.2866 |

Every absolute region sits between −2.16 and −2.29 MW. They lie on top of each other,
because they share the same feeder baseline. Look only at the absolute point and the
nine transformers are indistinguishable.

Their **widths** differ by a factor of 3.7 — TR5 moves the PCC by 0.656 MW, TR4 by
0.178 MW. That is the real difference in what each fleet delivers, and only the
deviation view shows it.

A fairness mechanism that reads the absolute point cannot rank contributions at all.
One that reads the deviation gets the ranking for free.

### A flexibility service is a change, not a level

When a DSO or TSO asks for something, the request is "200 kW more export for the next
half-hour". That request is a ΔP, measured from what would have happened anyway. The
absolute value at the PCC is not the service; it is the service plus a background
nobody controls.

### The baseline is not a service in the first place

The passive imbalance is already there. The PV is already serving local load, the
neighbours' load, and the losses, and nobody is paid for it. Crediting on the absolute
point counts that background as though it were a delivered service.

### The scale gap

At 12:00 the baseline is −2.2582 MW and TR9's whole region is 0.2866 MW wide — about
eight parts background to one part battery. Allocating on the absolute point means
allocating on the background.

> **Use ΔP and ΔQ for anything that allocates, prices, or dispatches.**

---

## 5. Do not throw the absolute FOR away

The network limits bind on absolute quantities. Voltage does not care about
deviations — it responds to the actual injection at the actual hour. **254 of the 576
vertices sit on the 1.10 pu over-voltage limit.** That limit is what shapes the region
in most hours.

So the two views split:

- **feasibility and network checks → absolute FOR**
- **allocation, pricing, and dispatch requests → deviation FOR**

Both are in the workbook, on the same tab, side by side, for this reason.

---

## 6. One caveat about the reference point

The deviation is measured from the **batteries-off** baseline, not from the committed
self-consumption schedule.

That is a deliberate choice, and it has a consequence: part of ΔP is what the battery
was going to do anyway under its own self-consumption plan. If what we want is
"flexibility on top of the committed plan", the reference has to be the committed
dispatch instead, and the numbers will be smaller.

Neither reference is wrong. They answer different questions. The rule is to **state
which reference a number came from** whenever we quote one. Every ΔP in this workbook
is measured from batteries-off, feeder-wide.

---

## 7. Reading one period tab

Each period tab has the 12 vertices, then a small interpretation block that computes
itself:

| Row | Meaning |
|---|---|
| `P width (MW)` | How wide the region is in active power |
| `import-reach (charge)` | `max(0, max ΔP)` — how much more TR9's batteries can absorb |
| `export-reach (dischg)` | `max(0, −min ΔP)` — how much more they can inject |
| `verdict` | Whether the region straddles zero, or is one-sided |
| `what stops it` | The voltage at the blocked vertex, when the region is one-sided |

"Straddles zero" here means the **deviation** region straddles ΔP = 0, so TR9's fleet
can go either way. It does **not** mean the feeder can reach zero exchange — at midday
the passive surplus is about 2.3 MW and one transformer's batteries move at most about
0.3 MW, so P = 0 is out of reach. See `FOR_reading.md` for where B(t) itself crosses
zero, around 04:30–05:00 and 18:00.

**On `what stops it`:** an active limit at the blocked vertex is evidence, not proof.
Confirming *which* constraint sets the boundary needs the shadow price of that
constraint, and the workbook does not carry duals. When the voltage at the blocked
vertex is clear of the cap, the deduction is safe the other way: the limit is not
voltage, so the battery bounds it.

---

## 8. What the day looks like

| | Periods | When |
|---|---|---|
| Two-sided (fleet can charge or discharge) | 36 | most of the day |
| One-sided, discharge only | 7 | 08:00–10:30 and 12:00 |
| One-sided, charge only | 5 | 15:30–17:00 and 19:00 |

In **all 12** one-sided periods the blocked direction sits at the 1.10 pu ceiling.

Four periods, to show the range. `B_P` is feeder-wide; the reaches are TR9's fleet:

| Period | Baseline `B_P` (MW) | import-reach (MW) | export-reach (MW) | Reading |
|---|---|---|---|---|
| 1 = 00:00 | +0.5454 | 0.2296 | 0.2903 | night import, both directions open |
| 13 = 06:00 | −0.6465 | 0.0764 | 0.4518 | PV ramping, export-heavy |
| 25 = 12:00 | −2.2582 | 0.0000 | 0.2874 | solar peak, fleet cannot absorb more |
| 33 = 16:00 | −1.2201 | 0.3954 | 0.0000 | must charge; export blocked at 1.10 pu |

Period 33 is worth a look. The fleet can absorb up to 0.3954 MW and cannot inject at
all. The 180° vertex sits at Vmax = 1.10000 pu. The feeder is at its voltage ceiling,
so more injection is not available at that hour whatever the battery state is.

Across the day, import-reach peaks at 0.4906 MW and export-reach at 0.4790 MW.
Baselines run from −2.3117 MW (period 26, deepest export) to +1.2369 MW (period 43).

---

## 9. Data, precision, and checks

Boundary points come from the rolling FOR solves exported as `FOR_rolling_TR9.csv`;
baselines from `FOR_rolling_baseline.csv` — one baseline series shared by all nine
per-transformer runs, which is itself a check that the measuring point is feeder-wide.
Both files are regenerated per run and are not tracked in Git (see `CONTRIBUTING.md`
section 3).

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
- the baseline reconciles with the sum of the nine transformers' load − PV to within 1%, the gap being network losses

---

## 10. Open question for discussion

Section 6 is the one to settle before we build the allocation on top of this.

If the fairness mechanism should reward flexibility **beyond the self-consumption
commitment**, the reference point has to move from batteries-off to the committed
dispatch, and every ΔP in this workbook shifts. That is a re-export, not a
recalculation of the FOR itself — the region does not change shape, only its origin.

Worth agreeing on the reference before either of us builds anything that depends on it.
