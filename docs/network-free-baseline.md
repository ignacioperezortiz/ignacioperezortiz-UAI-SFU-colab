# The committed baseline must keep the network on the whole feeder

**2026-08-30.** `BaseNoNetGMP = 1` solves the committed self-consumption baseline with the
`NetworkModel` rows deactivated. It saves about 9.6 h over a 48-period whole-feeder run and
was adopted as the default. **It is not safe.** At the midday PV peak it makes the direction
sweep infeasible in every direction, and the failure is silent in the sense that nothing
warns you: the baseline itself reports `Optimal`.

**The rule from here on: any whole-feeder run keeps the network in the committed baseline
(`BaseNoNetGMP = 0`).** The saving is not worth a region that cannot be computed.

---

## 1. What happened

`RunFullFeeder_K3_P20`, whole feeder, m=0, `BaseNoNetGMP = 1`, resumed from a checkpoint at
period 20:

| period | sweep |
|---:|---|
| 20 | 12/12 `Optimal` |
| 21 | 12/12 `Optimal` |
| **22** | **11 `Infeasible` + 1 `IntermediateNonOptimal`** |

The 2026-08-17 sequential reference — same case, same feeder, `BaseNoNetGMP = 0` — has
**576/576 `Optimal`, including period 22**.

## 2. The A/B

`RunFullFeeder_K3_P20_NetBase`: periods 20-23 from the same period-20 checkpoint, identical
in every assignment except `BaseNoNetGMP = 0`.

| | `BaseNoNetGMP = 1` | `BaseNoNetGMP = 0` |
|---|---|---|
| period 20 | 12/12 `Optimal` | 12/12 `Optimal` |
| period 21 | 12/12 `Optimal` | 12/12 `Optimal` |
| **period 22** | **0/12** | **12/12 `Optimal`** |
| solve time, period 22 | 1028-1966 s | 573-718 s |

One parameter, and the difference between a period that has no region and a period that
solves cleanly and twice as fast — proving infeasibility is the expensive part.

## 3. Why

The baseline commits the slot-1 dispatch that the sweep then holds fixed. Solved without the
`NetworkModel` rows, that dispatch is optimal for a feeder with no voltage limits and no
current equations, so **nothing stops it from committing a point the network cannot
support**. The sweep pins slot 1 to that dispatch *and* enforces the network. When the
committed point is outside what the network admits, no direction has a feasible point, and
all twelve fail together — which is the signature actually observed.

The baseline keeps reporting `Optimal`, because within its own relaxed problem it is.

### Why it took so long to surface

`BaseNoNetGMP` was validated in two places, and neither could have caught this:

- **TR3**, one reduced transformer, where the network is barely binding. The committed
  dispatch came out identical column by column, which is exactly what you would expect when
  the constraint being removed is slack.
- **Six whole-feeder periods on 2026-08-22**, 72/72 `Optimal` — **all six were night
  periods**. No PV, voltages far from the cap, network slack again.

The run that finally exercised the middle of the day is the one that failed.

### The run said so before it broke

The network was visibly tightening for hours beforehand, in columns the CSV already carries:

| period | directions at `VmaxTrue` = 1.10000 | max `OVviol` |
|---:|---:|---|
| 13 | 5 of 12 | 1.8668e-10 |
| 16 | 7 of 12 | 1.8668e-10 |
| 17 | 7 of 12 | 1.0467e-08 |
| 18 | 7 of 12 | 2.9867e-08 |

`OVviol` had sat at exactly 1.8668e-10 for sixteen periods and then moved. The FOR area was
collapsing over the same span — 37.3 at period 13 down to 15.0 at period 19. Both are the
network taking over as the binding constraint, which is precisely when a baseline that
ignores it stops being equivalent.

**Worth adopting as a check:** on a whole-feeder run, watch the count of directions pinned at
`VmaxTrue` = `MaxV`. Once it passes roughly half, a network-free baseline is no longer
answering the same question.

## 4. What this costs, and why pay it

`BaseNoNetGMP` cut the period boundary from 36 min to 24 min, about 9.6 h over 48 periods on
the reference machine. Giving it back is a real cost.

It is still the right trade. The saving buys nothing if the midday periods — the ones the
study is about, where PV is largest and the flexibility region is most interesting — come out
empty. And it is partly recovered anyway: the infeasible solves at period 22 cost 1028-1966 s
each against 573-718 s for the feasible ones, so a bad period is roughly twice the wall clock
of a good one *and* produces nothing.

## 5. What changes

- `RunFullFeeder_Production` and `RunFullFeeder_ProductionK3` now pin `BaseNoNetGMP = 0`.
- `RunFullFeeder_NB_P24` … `RunFullFeeder_NB_P48` are the four-period chunk runners for the
  whole feeder with the network baseline, chained through `FOR_rolling_ckpt_fullk3nb.dat`.
- `RunFullFeeder_K3_C1..C4` and `RunFullFeeder_K3_P20..P48` are **superseded**. They carry
  `BaseNoNetGMP = 1` and are kept only because they are what produced the finding.
- `docs/whole-feeder-production.md` §2 presented `BaseNoNetGMP` as the working default. That
  section is now qualified by this one.

## 6. Still open

- **Periods 1-19 of the 2026-08-30 run were produced with `BaseNoNetGMP = 1`.** Night and
  early morning, where the evidence says the network is slack — the six-period A/B of
  2026-08-22 covers part of that span and found no difference. Cheap to confirm: re-run a
  couple of those periods with `BaseNoNetGMP = 0` from the checkpoint and compare on `proj`.
  Until that is done, treat the first nineteen periods as provisional.
- **Does `BaseNoNetwork = 1` have the same defect?** It reaches a network-free baseline by the
  other generation path and was Prof. Luis's original request, implemented and validated by
  Tulio at TR4. Nothing here tests it at whole-feeder scale, but the argument in section 3 is
  about *what the baseline is allowed to commit*, not about how the rows are removed, so it
  should be assumed to share the defect until shown otherwise.
- **The 9.6 h is still worth having** if the baseline can be made network-aware more cheaply
  than the full 36-minute boundary — for instance keeping only the voltage limits. Not
  attempted.
