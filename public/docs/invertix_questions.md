# Questions for Invertix

A working list of questions to ask the Invertix team before and during the hackathon. Purpose: remove ambiguity, align the build with what they actually evaluate, and create natural openings to explain the plan. Each block has primary questions, the reason behind them, and follow-ups to use depending on the answer. Do not read these as a script; pick the three or four that matter most for the conversation you are in.

---

## 1. Scope and evaluation

**Q1. Should the system optimize for a specific persona, such as a hyperscaler planning a 200 MW AI campus, or stay general across enterprise, colocation, and edge use cases?**
Why: the persona changes everything. Hyperscalers care about power and carbon, colocation cares about connectivity and tenants, edge cares about latency. A focused persona produces a sharper product.
Follow-up: "I am planning to focus on large AI training campuses, where power has overtaken latency as the binding constraint. Does that match the problem you care about, or do you want inference workloads covered too?"

**Q2. How will the submission be judged: working depth of the engine, quality of the reasoning and explanations, or polish of the demo? Roughly how do you weigh those?**
Why: with limited hours, this decides whether the last six hours go into evaluation numbers or frontend polish.
Follow-up: "My plan front-loads a quantitative engine, an optimization model with a cost vs carbon Pareto frontier, and puts an agent on top for reasoning. Is that the right balance, or do you place more value on the interaction layer?"

**Q3. Is a Europe-only scope acceptable, given that PyPSA-Eur and the hourly Ember price data are European, as long as the architecture is demonstrably region-portable?**
Why: confirms the biggest scoping decision early and shows you read the data landscape.
Follow-up: "If global coverage matters, I would keep the European engine and add a coarser global layer from Ember's yearly data and AlphaEarth. Would that be seen as a strength or as scope creep?"

## 2. Problem fidelity

**Q4. How deep should the congestion modeling go? Open data has no interconnection queue or hosting capacity information, so my plan uses line loadings and nodal price spreads from a PyPSA-Eur optimal power flow as a proxy. Is a well-labeled proxy acceptable, or do you have access to better grid data you can share?**
Why: this is the weakest data axis of the four, and asking shows you know it. If they have proprietary data or a preferred source, that is a gift.
Follow-up: "If a proxy is fine, I will publish exactly how it is constructed and where it diverges from real queue times. Is there a specific congestion failure mode you have seen that I should make sure the proxy captures?"

**Q5. For the supply mix planning, should the model treat PPAs as fixed-strike financial contracts on a reference profile, or do you want physical co-location and grid connection sharing modeled?**
Why: signals you understand PPA structures, and the answer changes the LP formulation meaningfully.
Follow-up: "My default is fixed-strike pay-as-produced PPAs plus on-site assets behind the meter. If you want hourly-matched 24/7 CFE procurement modeled instead, I can make the carbon constraint hourly rather than annual."

**Q6. How much do non-power factors weigh in your view of siting: permitting timelines, land prices, water rights, local politics? They are out of open-data reach, so I plan to name them as explicit limitations rather than fake them. Is that the right call?**
Why: invites them to confirm the boundary of the problem, and pre-positions your limitations slide as a deliberate choice.

## 3. Technical expectations

**Q7. Is pre-event work on data pipelines allowed, and where is the line? I want to pre-solve a clustered PyPSA-Eur power flow and pre-export AlphaEarth embeddings so hackathon hours go into modeling and product, not downloads.**
Why: protects you from a rules violation and openly explains your de-risking strategy, which itself is a signal.

**Q8. Do you have a preference between a transparent scoring model with user-controlled weights and a learned ML ranking, or do you want to see both and how they disagree?**
Why: my plan combines both (weighted score plus a LightGBM model trained on existing data center locations with AlphaEarth embeddings as features). Their answer tells you which to put in front.
Follow-up: "The learned model encodes fiber-era siting logic, the score encodes power-era logic. Showing where they disagree is, I think, the most interesting output. Would judges find that compelling or confusing?"

**Q9. For the conversational layer, do you expect free-form reasoning, or strict grounding where every number must trace to a tool output? I plan strict grounding with a post-generation check.**
Why: shows you treat hallucination as an engineering problem. If they say free-form is fine, you still keep grounding, but you know not to spend extra hours on it.

**Q10. Any constraints on the stack, model providers, or compute? And will there be API credits, GPUs, or rate-limit considerations I should plan around?**
Why: purely practical, avoids a dead demo from an exhausted API key.

## 4. Evaluation and success criteria

**Q11. What would a winning answer to "recommend a location for 200 MW" actually contain for you: a ranked list, a full trade-off narrative, a sensitivity analysis, all three?**
Why: lets them describe the rubric in their own words. Whatever verbs they use, mirror them in the demo script.

**Q12. Is there a ground truth or reference case you will test against, for example a known good site or a published siting decision?**
Why: if yes, you can validate against it beforehand. If no, your face-validity evaluation (does the system reproduce Nordics vs FLAP-D behavior under different weights) becomes the standard, and you can say so.

**Q13. How do you want uncertainty handled: single point estimates with documented assumptions, or ranges and scenarios?**
Why: energy people distrust point estimates. If they care about scenarios, the price backtest across two historical years and a weight sensitivity analysis move up the priority list.

## 5. Invertix context (also useful for the interview itself)

**Q14. Is this challenge connected to a product direction at Invertix, and if so, who would the real user be: a developer, an investor, a utility, or an energy buyer inside a tech company?**
Why: the most important question on the list. The real user changes the framing of every screen, and asking it shows product thinking, not just engineering.

**Q15. What does the team consider the hardest unsolved part of this problem, the part where existing tools fail?**
Why: their answer is the gap your roadmap slide should point at. It also tells you what to emphasize when they probe your design.

**Q16. After the hackathon, is the expectation a working repo, a presentation, a deployed demo, or all three? And how long is the presentation slot?**
Why: logistics that decide your final-hours allocation. A five minute slot and a fifteen minute slot are different products.

---

## How to use this list

Lead with Q1, Q2, and Q14. They establish persona, rubric, and real user, which together determine eighty percent of your build decisions. Use Q4 and Q5 when speaking with anyone technical, because they demonstrate domain depth before you have shown a single line of code. Hold Q15 for a senior person; the answer is the seed of your roadmap slide and your strongest interview follow-up. Whatever they answer, close the loop: restate your plan in one sentence adjusted to their answer, and ask "does that match what you would want to see?" That turns a questionnaire into a design review, which is the real purpose.
