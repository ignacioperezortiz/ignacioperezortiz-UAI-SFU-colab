# Priority reading — Savvopoulos, Hatziargyriou & Laaksonen (2024)

**Paper:** Nikolaos Savvopoulos, Nikos Hatziargyriou, and Hannu Laaksonen, “A Holistic Approach to the Efficient Estimation of Operational Flexibility From Distributed Resources,” *IEEE Open Access Journal of Power and Energy*, vol. 11, 2024.  
**DOI:** [10.1109/OAJPE.2024.3429390](https://doi.org/10.1109/OAJPE.2024.3429390)

## Why this paper should be read carefully

This is one of the closest references identified during the 21 August meeting. In particular, it already addresses several elements that overlap with the current work:

- **time-dependent P–Q flexibility at the TSO–DSO interface**;
- **BESS inter-temporal constraints** through a multi-period optimization;
- **scenario-based renewable-generation uncertainty**;
- **network constraints** within the flexibility estimation;
- a **local BESS schedule aimed at maximizing self-consumption** before estimating flexibility;
- computational implications of including temporal constraints and scenarios.

The paper is therefore important not only as background literature but as a **reference against which the novelty of the present framework should be tested explicitly**.

## Questions to keep in mind while reading

1. What does this paper already solve that overlaps with our FOR and rolling-horizon formulation?
2. What assumptions does it make about **who controls the DERs** and how flexibility is implemented after the system-level region is computed?
3. Does it provide any explicit **disaggregation mechanism** from the TSO–DSO flexibility region to multiple aggregators or prosumers?
4. Does it address **fairness** between aggregators or between prosumers?
5. How is the BESS self-consumption schedule linked to the subsequent flexibility calculation, and how does that differ from our intended framework?
6. Which parts of our claimed contribution remain clearly distinct after this comparison?

## Connection to the current paper positioning

The meeting conclusion was that **multi-period/time-coupled FOR estimation or self-consumption alone cannot be treated as sufficient novelty**. The strongest direction to investigate is the coordinated **disaggregation of grid-feasible flexibility into implementable aggregator/prosumer actions, together with fairness**, while clearly justifying the role of the rolling horizon and DOE concepts.

See also the [21 August 2026 meeting summary](../meetings/2026-08-21/tulio-nacho-meeting-summary.md).
