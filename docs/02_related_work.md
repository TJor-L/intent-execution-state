# Related work and novelty audit

Initial primary-source reading list, checked 2026-10-14. This is not an exhaustive
novelty review. No claim of being the first intent/execution model is established.

| Area | Source | Relation and comparison to develop |
| --- | --- | --- |
| Longitudinal EHR representation / Transformers | Li et al., [BEHRT: Transformer for Electronic Health Records](https://www.nature.com/articles/s41598-020-62922-y), Scientific Reports 10, 7155 (2020) | Architecture background; motivates a strong type-aware sequence comparator. Different clinical task, not a direct matched experiment. |
| EHR foundation models / survival pretraining | Steinberg et al., [MOTOR: A Time-To-Event Foundation Model For Structured Medical Records](https://arxiv.org/abs/2301.03150); [ICLR 2024 paper](https://openreview.net/pdf?id=NialiwI2V6) | Close methodological neighbor: TTE representation learning. Distinguish order-conditioned execution from generic multi-task survival. |
| Competing risks | Lee, Zame, Yoon, van der Schaar, [DeepHit](https://ojs.aaai.org/index.php/AAAI/article/view/11842), AAAI (2018) | Direct survival-method comparator candidate. Learns event-time distributions with competing outcomes; does not by itself establish the proposed intention/execution contribution. |
| Temporal events / neural point processes | Mei and Eisner, [The Neural Hawkes Process](https://proceedings.neurips.cc/paper_files/paper/2017/hash/6463c88460bd63bbe256e495c63aa40b-Abstract.html), NeurIPS (2017) | Marked-event baseline family; history-conditioned intensities are background, not a new contribution here. |
| Medication representation and external data | [MIMIC-IV v3.1 data documentation](https://physionet.org/content/mimiciv/3.1/) | Documents orders, prescriptions and eMAR as distinct sources. Dataset reference, not a modeling baseline; access requirements apply. |

The initial architecture reading above is historical; the workflow/evaluation update below
now guides R001. This remains a targeted search, not a systematic review. Record search terms,
inclusion criteria, actual medication setting, links, input cutoffs, target labels,
censoring treatment, and the closest prior contribution in a comparison table.
Do not treat “uses a different event name” as a research gap. A substantive overlap
with a prior method is a redesign trigger, even if it appears after Phase 0.

## 2026-10-19: fixed-data evaluation pivot and nearest neighbors

Search scope: primary papers/publisher abstracts on EHR healthcare-process information,
competing-risk probability evaluation, Brier scoring with covariate-dependent censoring,
partial identification of model comparisons, and likelihood survival trees. Search phrases
included “EHR healthcare process timing predictive”, “competing risks proper scoring
Brier”, “survival model comparison partial identification”, and “survival tree likelihood”.
Included work addressing the target, censoring assumptions, or reference model family;
excluded secondary tutorials as methodological evidence. This is not an exhaustive search
or an established novelty claim. Abstract-only reading is explicitly identified below.

| Primary source | What is already established | R001 distinction and limit |
| --- | --- | --- |
| Agniel et al., [BMJ 2018](https://www.bmj.com/content/361/bmj.k1479) | Healthcare-process features, including ordering and timing, can contain predictive information. | Finding workflow information useful is not itself a contribution. R001 asks about selection objectives for first execution within a fixed retained history. |
| Alberge et al., [Survival Models: Proper Scoring Rule and Stochastic Optimization with Competing Risks, AISTATS 2025](https://proceedings.mlr.press/v258/alberge25a.html) | Proper censoring-adjusted scoring and gradient-boosted competing-risk models, with broad empirical comparisons. | We do not propose a new scoring rule or claim stronger performance. Our shallow tree is a simple independent reference, not SurvivalBoost or a state-of-the-art benchmark. |
| Kvamme and Borgan, [JMLR 2023](https://www.jmlr.org/papers/v24/19-1030.html) | Marginal censoring weights can be problematic when covariates predict censoring; proposes an administrative-censoring alternative. | We do not assume the additional censoring information needed by that alternative. Finite observed-sample completion bounds answer a narrower question and may remain wide. |
| Jonkers et al., [Proper Scoring Rules for Right-Censored Survival Data, preprint v2, September 2026](https://arxiv.org/abs/2606.06393v2) | Maps forecasts through censoring; proper scoring under conditional independent censoring; examines forecast-dependent plug-in ranking problems. | Objective mismatch and censoring-sensitive rankings are already studied. R001 compares two selection policies empirically; it does not show that likelihood or correctly specified IPCW scoring is improper. |
| Choi, Kim and Kim, [Sharp Partial Identification for Survival Model Comparison Without Target Outcomes, preprint, October 2026](https://arxiv.org/abs/2610.09658) (abstract read) | Direct paired Brier contrasts preserve a shared unknown outcome law under a target-shift sensitivity model, with uncertainty analysis. | Close neighbor. R001 completes censored labels within one observed sample across several horizons; it does not provide transport identification or their inferential guarantee. Shared-completion bounds are not claimed as new theory. |
| LeBlanc and Crowley, [Survival Trees by Goodness of Split, 1993](https://www.tandfonline.com/doi/abs/10.1080/01621459.1993.10476296) (abstract read) | Likelihood-based survival partitioning is longstanding. | Our explicit depth-two, smoothed piecewise competing-risk tree is a small reference implementation, not an exact replication or new tree algorithm. |

Decision: stop positioning this as a new architecture or discovery that metrics can
rank models differently. The possible contribution is a reproducible, task-specific
empirical assessment: whether a fixed selection objective changes patient-held-out
choices and execution-probability errors, and when censoring leaves the difference
unresolved. Existing W001/W002 findings motivated R001, so this is exploratory development.
A single bounded institutional cohort and simple candidate bank limit generalization.
Clinical magnitude and a useful transferable lesson remain unestablished; even a clean
R001 run may support only a technical report or a negative evaluation study.
