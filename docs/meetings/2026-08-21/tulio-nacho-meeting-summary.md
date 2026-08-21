# Meeting Summary — Tulio Coura & Ignacio Pérez Ortiz

**Date:** 21 August 2026  
**Duration:** 33 min 40 s  
**Purpose:** Review the computational results and next validation steps, and clarify how the paper should be positioned against the closest literature.

## 1. Implementation and validation

- **Weekend benchmark:** Ignacio will run the updated full-feeder case using the latest parallelization and constraint changes. Current reference times are about **27 h for matrix generation** and **3.4 days for the previous long run**.
- **Critical validation comparison:** Tulio will compare the **full-feeder FOR** with **transformer-by-transformer FORs**. A large difference would indicate that medium-voltage coupling or constraints are being missed; a small difference could support transformer-level parallel computation followed by aggregation.
- **Modeling result:** The fully linearized Taylor-expansion test produced **voltage violations**. The quadratic formulation therefore remains the stronger reference when network-feasibility accuracy is important.
- **Runtime expectation:** Most obvious software improvements have already been applied (matrix generation, parallelization, warm-start changes and constraint removal). Further software-only gains may be modest, while better hardware can still reduce runtime.

> **Validation principle:** Any speedup is valuable only if it does not materially reduce the quality or feasibility of the resulting FOR.

## 2. Paper positioning and literature strategy

- **Closest paper discussed:** Savvopoulos, Hatziargyriou and Laaksonen (2024), *A Holistic Approach to the Efficient Estimation of Operational Flexibility From Distributed Resources*, IEEE Open Access Journal of Power and Energy, Vol. 11, DOI: 10.1109/OAJPE.2024.3429390.
- **Important overlap:** That work already combines **time-dependent P–Q flexibility at the TSO–DSO interface**, **BESS inter-temporal constraints**, **scenario-based renewable uncertainty**, and a **local BESS schedule aimed at self-consumption**. This makes it an important reference for positioning the present work.
- **Implication for novelty:** The contribution cannot rely only on having a multi-period/time-coupled FOR or a self-consumption baseline. The strongest candidate discussed is the **disaggregation of system-level flexibility into implementable actions for multiple aggregators and prosumers, with fairness explicitly considered**.
- **Literature-review structure:** Organize the review by technical blocks — **FOR**, **multi-aggregator/disaggregation**, **fairness**, **DOE/operating envelopes**, and **rolling/receding horizon** — and end each block with the limitation that the proposed method addresses.
- **Current writing status:** The three introduction versions and the associated papers are still being organized. They are **not ready to send yet**; Tulio will share them with Ignacio once the package is clear and coherent, without committing to completion on 21 August.

> **Main paper message:** Position the paper around what it adds beyond existing flexibility frameworks, with each claimed contribution tied directly to a documented literature gap.

## 3. Open research question: rolling horizon, uncertainty and DOE

- **Rolling-horizon rationale:** The current structure resembles MPC, but the present simulation uses perfect future information. The reason for repeatedly solving the problem therefore needs a clearer justification before MPC/receding horizon is claimed as a methodological contribution.
- **DOE rationale:** If prosumers have already optimized self-consumption, the paper should explain what additional operational freedom a DOE represents and why it is needed.
- **Exploratory two-stage idea:** During a service request, the system coordinates a target point inside the FOR and disaggregates it among aggregators/prosumers; outside service periods, prosumers retain local flexibility and may react to prices, markets or uncertainty.

> **Status:** The two-stage/DOE concept remains exploratory. It should be investigated further before being presented as part of the final formulation.

## 4. Agreed actions

| Owner | Action | When |
|---|---|---|
| Tulio | Open the pull request with the latest parallelization/constraint changes and share the linearization test. | 21 Aug |
| Ignacio | Run the updated full-feeder simulation and record runtime/progress. | Weekend |
| Tulio | Compare transformer-by-transformer FORs with the full-feeder FOR. | Next step |
| Tulio | Organize the three introduction versions together with the supporting papers; send the package to Ignacio when it is clear and ready. | In progress |
| Tulio | Prepare/refine the one-page gap and contribution note for Prof. Luis after the literature package is sufficiently organized. | No fixed date |
| Ignacio | Review Savvopoulos et al. (2024) and prioritize references for FOR, DOE, fairness and multi-aggregator positioning. | Next week |
| Joint | Revisit disaggregation, fairness, DOE and the rolling-horizon rationale; separate core contributions from future work. | Next meeting |
| Joint | Arrange a concise project discussion with Mariana using the current model/results as the basis. | Upcoming |

## 5. Questions to resolve next

1. **Novelty:** What is the precise technical gap after the closest FOR, time-dependent flexibility, fairness and multi-aggregator papers are considered?
2. **Computation:** How much runtime can be saved without losing network-feasibility accuracy?
3. **Rolling horizon:** Does the formulation need explicit forecast updates or uncertainty to justify the MPC/receding-horizon framing?
4. **DOE:** What operational role should local prosumer flexibility have after self-consumption has already been optimized?
5. **Real time:** What definition of “real time” is appropriate for the intended application?

**Next priority:** Complete the computational benchmark while organizing the literature and introduction carefully. Finalize the contribution statement only after the closest-paper comparison and feedback from Prof. Luis.
