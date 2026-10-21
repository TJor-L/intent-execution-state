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

## 2026-10-19: machine-learning methods-only reassessment

The user clarified that a methods paper is required, and that new tasks/models may use
the same original data. Applied analysis-definition sensitivity is therefore not the
main project. F001 and the unknown new-format direction remain inactive. This is a
research proposal, not an implemented method, frozen clinical protocol or publication claim.

### Data opportunity and limits

The approved operational handoff in docs/21 records direct order–administration linkage
and common repeated administrations. The old MVP excludes repeated administrations;
its later eligible cohort is further limited to reviewed one-time, non-PRN orders.
The retained histories cap the number of events and W001/R001 used small engineered
count/timing representations. Their negative findings do not evaluate learning from
full linked recurrent trajectories. Conversely, the presence of multiple linked rows
does not establish complete observed courses, reliable scheduled-dose times, usable
medication identities, or clinical reasons for non-administration.

A new extraction from the same original sources is conceptually different from collecting
new data. It still needs its own recurrent-event/coverage design and explicit access bounds;
it cannot be implemented by merely disabling repeat rejection. Do not require new labels,
new sources or unexplained physiology. Stop a candidate if essential existing evidence is
missing; the user has said that nobody can supply new semantic explanations. Within-patient
relative time and reviewed availability remain mandatory; no cross-patient calendar model.

### Closest work checked

Targeted primary-source searches covered EHR self-supervision, order/administration pairing,
recurrent event prediction, neural point processes, object-centric predictive monitoring,
and EHR history/token compression. Most readings below are abstracts; the object-centric
graph paper's formalization, preprocessing and model sections were also read. This is not
an exhaustive novelty review, and failure to find an exact medication pairing paper does
not establish novelty. Preprints are identified as such.

| Primary source | Existing contribution and consequence for this project |
| --- | --- |
| [MOTOR, ICLR 2024](https://arxiv.org/abs/2301.03150) | Self-supervised time-to-event representation learning already exists. A new survival pretraining loss must have a substantive distinction. |
| [Know-Evolve, ICML 2017](https://proceedings.mlr.press/v70/trivedi17a.html) | Temporal relational reasoning with event intensities is established. A graph plus a point process is not a sufficient novelty claim. |
| [Predictive Process Monitoring Using Object-centric Graph Embeddings, 2025 preprint](https://arxiv.org/html/2507.15411v1) | Uses object-centric directly-follows graph embeddings with an LSTM for next activity/time. Preserving relations and predicting an object's next event are already studied. |
| [A Framework for Object-Centric Predictive Monitoring of Collaborative Processes, August 2026 preprint](https://arxiv.org/abs/2608.27671) | Explicit object relations, task reformulation and graph/sequence/tabular comparisons are established research directions. A clinical relabeling alone does not add a method. |
| [Probabilistic Forecasting of Business Process Executions with Neural Temporal Point Processes, September 2026 preprint](https://arxiv.org/abs/2609.21382) | Studies probabilistic next-event/time forecasts and tied timestamps. A Transformer likelihood model or a tie-handling rule alone is insufficient. Clock coincidence in A001 is not evidence of ties between distinct events. |
| [Tokenization Tradeoffs in Structured EHR Foundation Models, March 2026 preprint](https://arxiv.org/abs/2603.15644) | Studies event/time/workflow encodings, local code–attribute binding and compute efficiency. Generic event grouping or fewer tokens is not a new contribution. |

### Ranked method candidates

1. **Relation-preserving recurrent-event learning (priority for local assessment).**
   Learn from interleaved patient events while retaining the history of each linked order.
   An initial task would forecast subsequent qualifying administrations for orders already
   known at a cutoff, including repeated events and an explicit unobserved tail. It must
   not use future order arrivals, terminal records or identities as input. One possible
   method focus is learned allocation of a fixed history/memory budget between shared
   patient context and individual order histories, optimized for future distribution
   preservation. Order IDs define local relations only; predictions must transform
   consistently when those IDs are renamed. Shared/local state, permutation equivariance
   and censoring likelihoods are requirements and known ingredients, not claimed inventions.
   A useful contribution would need a distinct allocation/learning algorithm plus a
   defensible accuracy–cost or generalization result beyond existing relational models.
2. **One-to-many self-supervision with incomplete observation (backup).**
   Use verified links as supervision: an order may have several positive administrations,
   while an unfinished observation window supplies unknowns, not negative pairs. The
   research question is whether a new learning objective handles that structure better
   than ordinary multi-positive contrastive or time-to-event pretraining. Exact code/time
   matching shortcuts and weak semantic diversity could make this uninformative. A
   CLIP-style loss with medical labels is not enough, and cross-patient pairs are not
   automatically known semantic negatives.
3. **History compression preserving relational information (backup).**
   Study which event relations to retain under a fixed compute budget, with future-event
   distribution distortion as the target. This may become the method focus within
   candidate 1 rather than a separate paper. It requires comparison with retrieval,
   recent-K, per-order summaries and strong recurrent/graph memories, not just a short
   vanilla Transformer. Already truncated artifacts cannot establish full-history loss.

### Evidence needed before another UCSF experiment

- Specify one contribution and its nearest algorithmic comparator. If the proposal
  reduces to an existing method with order IDs renamed, reject it before a clinical run.
- First build a generated local benchmark with independent variation in interleaving,
  recurrence, memory budget and observation truncation. Include a null setting where
  links carry no additional information. A simulator designed to favor the proposed
  architecture does not establish a method advantage or clinical relevance.
- Compare methods given the same observable links, times and attributes. Include simple
  per-order recurrence baselines and strong sequence/relational models; measure memory,
  runtime and prediction loss at matched budgets. An advantage over a baseline denied
  the link information is not sufficient. No identifier memorization or future-edge leak.
- Define the observable target, terminal-event handling and observation/censoring assumptions
  before writing the recurrent extractor. No-event before coverage ends is not permanent
  non-execution. A censoring term alone does not identify outcomes under arbitrary dependent
  observation. Do not treat tied events as an arbitrary chronological sequence.
- Establish whether a bounded coherent selection can return complete qualifying histories
  for a new task. Reuse original training patients for development; do not silently assign
  patients already used in E003 validation to an independent new confirmation set. No old
  held-out data open during this assessment. Freeze a new evaluation design before results.
- A transferable ML claim would benefit from public nonclinical event benchmarks as well
  as the UCSF application, without collecting new UCSF data. The official
  [OCEL log catalog](https://www.ocel-standard.org/event-logs/) separates real and simulated
  logs. No dataset has been selected/downloaded; licenses, target compatibility and true
  relational information must be checked. Synthetic logs are not external real validation.

Current decision: assess candidate 1 locally, with 2/3 as alternatives; do not launch
three clinical searches. No substantive new algorithm or positive result has yet been
established. No new server job, extraction, GPU run or held-out evaluation is scheduled.

### M001 implementation follow-through

The user authorized starting the local prototype. `make memory-demo` now implements a
generated-only, censoring-aware allocation diagnostic; its exact design is in docs/11.
It uses a standard ridge utility learner and discrete budget solver, with a small NumPy
MLP decoder. This is a mechanism baseline, not a claimed new ML algorithm. Complete
synthetic outcomes are evaluation-only. A direct-descriptor predictor checks whether
the selector's supposedly auxiliary information already solves the prediction problem.

Additional nearest neighbors checked on 2026-10-19:

- [Temporal Graph Networks, 2020](https://arxiv.org/abs/2006.10637) (abstract): combines
  node memory with graph operators on timed interactions. Per-order state or a memory
  update module by itself is not a substantive distinction.
- [SALoM, NeurIPS 2025](https://papers.neurips.cc/paper_files/paper/2025/file/20f94998511f25bb6378cae0e098bc46-Paper-Conference.pdf)
  (abstract/introduction): long/short temporal memory with structural information and
  information-bottleneck fusion. Do not position generic long/short memory balancing
  or structural fusion as an unoccupied method contribution.

Neither is implemented as a comparator yet; the local small MLP controls must not be
called state-of-the-art baselines. The present implementation limits decoder event
context, while its full-prefix scan and descriptors remain additional costs. A true
streaming-memory claim would require a different implementation and resource comparison.

### Autonomous continuation: joint recurrent paths under incomplete observation

The user requested continuous autonomous research after M001 failed to establish a
useful main method. M001 remains a closed prototype, not a reason to stop the research
or to ask the user to choose another architecture. The current local question is whether
joint future paths provide an estimable target beyond marginal next-event forecasts,
and which learning algorithms could exploit it without interpreting unobserved events
as negatives. This is a new research question, not a rescue of W001/R001 or a clinical claim.

Additional primary-source review on 2026-10-19:

| Source and reading depth | Consequence |
| --- | --- |
| [Borrowing From the Future, 2025](https://arxiv.org/abs/2508.11210) (abstract) | Contrastive transfer from later to earlier clinical windows already exists. Future-teacher supervision alone is not a contribution. |
| [ConSurv, NeurIPS 2024](https://openreview.net/pdf?id=UVjuYBSbCN) (indexed method/algorithm excerpts) | Survival-outcome-aware pair weighting already handles some ambiguous contrastive pairs. Simply ignoring censored negatives is insufficient novelty. |
| [Conformal Prediction with Partially Labeled Data, 2023](https://proceedings.mlr.press/v204/javanmardi23a.html) (abstract) and [Predictive Inference with Weak Supervision, JMLR 2024](https://www.jmlr.org/papers/volume25/23-0253/23-0253.pdf) (abstract) | Set-valued labels and weak-label coverage are established. True-label coverage and intersection/weak coverage must not be conflated. |
| [Proper Scoring Rules for Right-Censored Survival Data, June 2026 preprint](https://arxiv.org/html/2606.06393v1) (sections 1–4) | Applies scores after the observation map, including joint censored engression. Scoring projected predictions or adding a censored energy loss is already a close comparator, not our invention. Conditional independent censoring and identifiable support matter. |
| [Add and Thin, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/file/b1d9c7e7bd265d81aae8d74a7a6bd7f1-Paper-Conference.pdf) (abstract and forward-process section) | Whole-event-sequence generative diffusion already exists. A diffusion decoder alone cannot establish novelty. |
| [Ambient Diffusion, NeurIPS 2023](https://openreview.net/pdf?id=wBJBLy9kBY) (abstract and indexed objective/theorem excerpts) and [Consistent Diffusion Meets Tweedie, 2024](https://arxiv.org/abs/2404.10177) (abstract) | Learning clean distributions from corrupted samples is established and has explicit identifiability/consistency conditions. Prefix truncation cannot be treated as ordinary random masking without checking those conditions. |
| [Correcting for Nonresponse in Latent Class Analysis, 1996](https://pubmed.ncbi.nlm.nih.gov/26750707/) (abstract) | Missing-data latent-class EM is longstanding. The small product-mixture implementation below is a reference, not a new algorithm. |

Current distinction to investigate: scalable **joint path learning for a varying roster
of anonymous linked entities under shared prefix observation**, with repeated events,
absorbing termination and explicit limits on what the observable law identifies.
Neither joint prediction nor censoring-aware scoring alone is a novelty claim. A possible
algorithmic contribution would have to improve over observed-data likelihood, latent-class
models and observation-channel generative scores, at matched information and cost. An
ambient/denoising route remains planned, not implemented or selected as a paper method.

J001 is now a finite-state reference laboratory to falsify proposals before large-model
work: every path is enumerable, so hidden dependence, observation-equivalent alternatives
and exact population loss are checkable. The supplied estimators are all established
methods. Its purpose is to separate a useful learning problem from a renamed baseline.
No clinical claim follows from designed synthetic dependence, and an unidentified tail
cannot be recovered without further assumptions merely by using a more expressive model.

The next local research work is to derive and test a distinct estimator/objective against
these references, including misspecified dependence and dependent observation stress cases.
Those stress cases and any new algorithm are still planned. No UCSF task is scheduled.

### J002: observation-depth interaction shrinkage and its close precedents

The next local implementation tests a candidate adaptation rather than assuming that
generic shrinkage is novel. [Autin, Le Pennec and Tribouley (2010)](https://www.sciencedirect.com/science/article/pii/S0047259X09001316)
already study adaptive wavelet thresholding of copula densities (abstract read).
[Ghanbari et al. (2019)](https://link.springer.com/article/10.1186/s13660-019-2140-5)
study wavelet copula estimation under right censoring (abstract, setup and coefficient
construction read); [Ghanbari and Shirazi (online 2022)](https://www.tandfonline.com/doi/abs/10.1080/03610926.2022.2113798)
study adaptive bivariate censored-density estimation with copula information (abstract).
Therefore neither censored wavelet estimation nor shrinkage toward independence is new.
The local finite path estimator is not a reproduction of those continuous bivariate
estimators and does not inherit their asymptotic guarantees.

The candidate distinction is the **nested observation structure of repeated/terminal
paths**: an interaction between two weighted prefix contrasts becomes observable only
at the later of their reveal depths. With a common independent stopping window, its
information at the independent reference is proportional to `P(C >= max(d1, d2))`,
not the product of the two observation probabilities. Different blocks therefore have
different usable sample sizes. J002 constructs the path basis explicitly, estimates
centered interaction moments from the appropriate observed subjects, shrinks by reveal
depth, then contracts toward independence just enough to restore positive probabilities.
Entity-path marginals are preserved. This is a concrete candidate mechanism; the basis,
moment shrinkage and positivity contraction are known ingredients, and a distinct
publishable contribution remains unestablished.

Strong local comparisons include ordinary global-block shrinkage and cross-validated
Dirichlet-tree smoothing with a global independent/joint blend. Context-tree weighting
also predates this work; [Vellambi and Hutter's convergence analysis](https://www.hutter1.net/publ/convbinctwx)
illustrates Bayesian mixtures over dependency structures (abstract/introduction read).
The implemented Dirichlet-tree comparator is not a reproduction of CTW. Fixed-marginal
copula smoothing is likewise established: [Kauermann, Schellhase and Ruppert (2013)](https://onlinelibrary.wiley.com/doi/abs/10.1111/sjos.12018)
use penalized spline coefficients with linear marginal constraints (abstract read).

Predictable stopping based on already observed joint history is distinguished from
stopping that depends on unseen future outcomes. The former can still be ignorable for
a correctly specified joint sequential likelihood, but generally biases the proposed
unweighted complete-prefix moment estimator. The latter can invalidate both ordinary
prefix likelihood scoring and the moment approach. Neither stress is treated as solved
by a censoring term. J002 includes both, plus dependence mechanisms outside the simple
two-class product generator, before considering clinical use.

### J003: convex likelihood is a mechanism test, not a generic novelty claim

J002's fixed full experiment lost to the stronger tree/blend reference in 142/150 cases.
J003 therefore removes its locked pilot marginals and global positivity contraction by
optimizing the full probability law. This response is a specified successor experiment,
not a retroactive change to J002. The independent-window reveal calculation still motivates
its grouped penalty; whether that grouping helps beyond ordinary regularization is tested
by global-group, tree/blend and latent-class comparisons on equal total sample budgets.

Additional primary-source checks on 2026-10-19:

- [Nardi and Rinaldo, Bernoulli 2012](https://arxiv.org/abs/0709.3526)
  (abstract): convex group-lasso likelihood for multinomial hierarchical log-linear
  interactions and its asymptotic properties already exist. Our probability-coordinate
  smooth penalty is not that estimator and inherits none of its selection guarantees;
  grouping interaction terms or using a convex objective is not a novelty claim.
- [Qu and Yin, 2012](https://www.sciencedirect.com/science/article/abs/pii/S0167947311002830)
  (publisher abstract): penalized likelihood copula density estimation with linear
  marginal constraints is established. Generic probability smoothing with constraints
  cannot be positioned as a new method.
- [Machado, van den Hout and Marra, 2021](https://discovery.ucl.ac.uk/id/eprint/10107405/1/Submitted_to_CSDA_July2020.pdf)
  (abstract and publisher introduction): penalized multistate likelihood with spline
  hazards and automatic smoothing already handles interval-censored transitions. J003's
  finite recurrent/terminal path distribution is a different setup, but regularizing
  censored state-transition likelihood is not itself new.

The concrete open question remains whether the shared-prefix observation geometry can
guide interaction complexity in a useful and scalable way. The current 225-state solver
is a falsifiable numerical laboratory, not a novel neural architecture, scalable learner,
or publishable contribution. A small optimization gap certifies a fixed convex objective;
it does not certify generalization, identification or calibration.

The subsequent exact information audit is also grounded in established missing-data
theory. [Farewell, Daniel and Seaman, Biometrika 2022 (online 2021)](https://academic.oup.com/biomet/article/109/1/227/6128501)
(summary, introduction and monotone-data setup read) characterize observed information
using stopping-time/set sigma algebras and describe likelihood factorization under MAR.
We do not claim the stopping-time formulation, conditional score projection or the
standard nuisance-information Schur complement as inventions. The local contribution
at this stage is a checked finite diagnostic showing which simpler penalty assumptions
fail in our generated recurrent-path setup. A known simulator-kernel CAR check cannot
be turned into an observational test of an unknown clinical mechanism.

### Variable-roster continuation: nearest overlap and a testable interaction layer

Primary-source review on 2026-10-19 rules out treating generic latent dynamics,
exchangeability or simultaneous-event modeling as inventions:

- [Chang, Boyd and Smyth, AISTATS 2024](https://proceedings.mlr.press/v238/chang24a.html)
  (abstract, dynamic Bernoulli/DPP construction and scaling discussion): set-valued
  continuous-time events and history-conditioned joint queries already exist. Their
  dynamic DPP comparison makes computational cost of richer set dependence explicit.
  Our discrete recurrence/terminal laboratory is not a reproduction of this model.
- [Wu et al., Markov-Modulated Hawkes Processes](https://arxiv.org/abs/1903.03223)
  (abstract): combining persistent latent states with event excitation is established.
  A hidden-state plus short-memory module alone is insufficient novelty.
- [Yang and Zha, AAAI 2024](https://ojs.aaai.org/index.php/AAAI/article/view/29570)
  (abstract): time-varying latent graphs for neural point processes already exist.
- [Sinelnikov et al., 2024](https://arxiv.org/abs/2402.05758)
  (abstract): joint latent modeling of high-dimensional events and structured missingness
  is established; an unknown observation mechanism cannot be declared solved by adding
  a latent variable.
- [Luedtke, Bartelt and Stuckenschmidt, IJCAI 2022](https://www.ijcai.org/proceedings/2022/674)
  (abstract): exchangeability-aware sum-product networks already use repeated parts for
  tractable inference. Neither exchangeable parameter sharing nor tractable marginalization
  alone identifies a new method.
- [Tarlow et al., UAI 2012](https://proceedings.mlr.press/r10/tarlow12a.html)
  (abstract and introductory construction): exact inference and sampling for cardinality
  potentials are established, with faster convolution algorithms than the initial quadratic
  dynamic program planned here. Do not claim our basic recurrence as novel or fastest.
- [Hughes, R Journal 2014](https://journal.r-project.org/articles/RJ-2014-026/)
  (centered-autologistic model section): centering association terms to separate first-
  order regression effects follows earlier Caragea/Kaiser work. Centered pair interactions
  are not a new architecture.

The concrete candidate to test is a **conditional interaction layer over a varying risk
set**, using a bounded cardinality feature with its constant and single-entity projections
removed under a fitted independent reference. At independence, its score is orthogonal
to every marginal Bernoulli score. Because the feature is a function of the event count
plus entity-specific linear offsets, exact normalization and sampling remain tractable.
This combines known cardinality inference and functional projection; useful performance,
roster-size stability and a distinct contribution remain open, not presumed from a search.
The immediate implementation is a computational/statistical mechanism test, not yet a
long-path learner, a solution to informative stopping, or a clinical adapter.

An alternative involving doubly robust censoring losses was also checked, not selected:
[Steingrimsson and Morrison, 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7334068/)
(abstract and loss description) already replace unavailable full-data risks with censoring-
unbiased deep-learning losses. Generic IPCW/augmentation would require a stronger distinct
argument and extra observation assumptions; no such loss or new clinical assumption was
introduced here.

### History-conditioned roles and changing roster size (J006 review)

[Shao et al., Conditional Sum-Product Networks, IJAR 2022](https://ml-research.github.io/papers/shao2022ijar.pdf)
(abstract, definitions, gating/structure learning and autoregressive construction read)
already condition tractable multivariate laws on input features and combine them into
sequential factorizations. J006's finite role mixture and conditional HMM are reference
implementations, not inventions of conditional dependence, gated circuits or filtering.

[Papez et al., Sum-Product-Set Networks](https://arxiv.org/html/2408.07394v1)
(abstract, introduction and set-unit definition read) extend circuits to variable-size
tree-structured objects using random finite sets. Consequently, variable cardinality,
permutation symmetry and tractable probability queries cannot by themselves support
our novelty claim. This is an overlap assessment, not a reproduction of their learner.

[Yang et al., Energy-Based Processes, ICML 2020](https://proceedings.mlr.press/v119/yang20b/yang20b.pdf)
(exchangeability/consistency setup and latent representation read) explicitly treats
marginal consistency across set sizes. Merely applying a normalized model at each roster
size is weaker than marginal consistency when entities are unobserved. Actual changes
in an interacting population need not have the same law as thinning one fixed population.

[Niepert and Domingos, Exchangeable Variable Models, ICML 2014](https://proceedings.mlr.press/v32/niepert14.html)
(abstract) establishes partially exchangeable building blocks as tractable models.
[Carlier, Friesecke and Vogler, 2021](https://arxiv.org/abs/2106.09101)
(abstract and opening representation discussion) describes finite-exchangeability laws
and correlated corrections to infinite-population representations. Finite capacity and
without-replacement dependence are not new problems. The elementary count-variance
restriction on extending negative correlation is also not a new theorem.

The current purpose is to separate three empirical/structural questions: whether
observed histories locate useful subgroups, whether a learned mapping transfers to
unseen actual roster sizes, and whether missing entities are marginalized coherently.
A favorable answer to one does not answer the others or establish a methods contribution.

### Joint local competition and latent dynamics (J007 closest references)

[Gardella, Marre and Mora, eNeuro 2016](https://arxiv.org/pdf/1606.08889)
(model definitions, polynomial normalizer, Newton inference and correlation results read)
already give tractable maximum-entropy population-coupling models, including nonlinear
individual-versus-count relationships and negative correlations. J007's signed quadratic
count emission is a restricted known family; exact normalization, derivative-based fitting
and negative dependence are not separate inventions. Its generated question is whether
local competition and persistent common-state variation are both needed in the same
recurrent conditional law, with transfer across actual roster sizes.

[Li and Oliva, Partially Observed Exchangeable Modeling, ICML 2021](https://proceedings.mlr.press/v139/li21q/li21q.pdf)
(abstract, latent construction and neural-process conditional extension read) already
models incomplete related instances jointly. Generic set imputation, latent conditioning
or arbitrary observed subsets cannot be claimed as a new task. Our precise same-history
covariance restriction concerns conditional-iid target emissions; it should not be
misrepresented as a claim that every model in this literature cannot capture any negative
association. J007 currently handles patient prefixes, not missing entity histories.

[Gourieroux and Lu, Markov Determinantal Point Process for Dynamic Random Sets](https://onlinelibrary.wiley.com/doi/10.1111/jtsa.12823)
(abstract and introduction read; first published online 2025, volume dated 2026) provides
Markov set dynamics with tractable stationary and transition laws. Temporal repulsion
is therefore established, as are the set-valued point-process baselines already listed.
We have not reproduced this estimator and cannot claim superiority to it from an HMM
comparison. A convincing new methods contribution still needs a distinction beyond
combining known count and latent-state modules.

For possible future treatment of missing recurrent entities,
[Sheldon and Dietterich, Collective Graphical Models, NeurIPS 2011](https://papers.nips.cc/paper_files/paper/2011/hash/fccb3cdc9acc14a6e70a12f74560c026-Abstract.html)
(abstract and author-paper opening construction) already uses sufficient statistics for
population inference. Its presented individual chains are iid; this is a close algorithmic
reference rather than a reproduction of the interacting finite-roster law.
[Finite state projection likelihood bounds, 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4991991/)
(likelihood-bound section) already uses retained probability mass to bound likelihoods.
[Filtered Finite State Projection](https://epubs.siam.org/doi/abs/10.1137/24M1707614)
(abstract) gives filtered truncation with computable errors. Consequently, state aggregation
or discarded-mass bounds alone would not establish novelty either. No such approximate
filter is implemented in J007, and no claim of solving unknown observation mechanisms
follows from these references.

[Prentice et al., Error-Robust Modes of the Retinal Population Code, 2016](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005148)
(model-specification and fitting sections read) combines a latent Markov chain with
state-specific Chow-Liu tree emissions, fitting both tree topology and parameters by
modified Baum-Welch. Thus combining global modes with correlated within-state outputs
is already established. J007's comparison against a product-emission HMM does not show
superiority to correlated-emission HMMs. History-based parameter sharing across different
rosters and missing recurrent histories are narrower questions, not proof of novelty.
This reference is documented but not yet reproduced.

### Missing recurrent histories and lifted filtering (J008 review)

[Niepert and Van den Broeck, Tractability through Exchangeability, AAAI 2014](https://web.cs.ucla.edu/~guyvdb/papers/NiepertAAAI14.pdf)
(abstract and introduction read) relates finite partial exchangeability to efficient
probabilistic inference, including densely coupled distributions. Thus reducing
identity configurations to sufficient counts is established beyond iid populations.

[Luedtke et al., Lifted Filtering via Exchangeable Decomposition, IJCAI 2018](https://www.ijcai.org/proceedings/2018/0703.pdf)
(abstract, multiset representation and prediction/update construction read) already
performs exact recursive filtering on exchangeable multiset states. Its formalism
supports splitting when identifying evidence breaks symmetry, and general normalized
compound-action probabilities; the illustrated action selection is independent.
J008's fixed-subset histogram filter is a restricted concrete reference calculation,
not a new lifted-filtering principle. It does not implement that paper's general
structured-species/splitting machinery or learn from partially observed histories.

The actual implementation does sum unknown future recurrence and termination histories
in a coupled finite-roster count law. Its difference from deleting a roster member is
verified, but that correctness property alone is not a method contribution. A useful
successor would need a separately assessed learning or computational contribution
against strong lifted/particle/correlated-emission references, and a defensible
observation task. No absence of a search hit is taken as evidence of novelty.

### Learning with unobserved interacting histories (J009 review)

[Brand, Coupled Hidden Markov Models for Modeling Interacting Processes, 1996](https://www.media.mit.edu/publications/coupled-hidden-markov-models-for-modeling-interacting-processes/)
(primary abstract read) already addresses coupled latent dynamics and approximate
parameter estimation via EM. Learning interacting latent histories is not a new task.
[Singh, Zhang and Chen, Learning Hidden Markov Models from Aggregate Observations](https://arxiv.org/html/2011.11236v2)
(abstract, introduction and aggregate-HMM setup read) learns individual HMM parameters
using EM and Sinkhorn belief propagation. Its aggregate observations arise from
independent individuals; its large-population relaxed count inference is distinct from
our exact small-population coupled-count posterior. That difference identifies a model
and observation distinction, not a novelty proof or an empirical superiority claim.
[Le Corff and Fort, Particle-Based Block Online EM](https://arxiv.org/abs/1111.1307)
(abstract only) establishes SMC-based EM approximation and convergence under conditions.
Replacing exact smoothing with particles alone would therefore not establish novelty.

J009 implements standard exact MAP-EM with sufficient statistics obtained by the J008
histogram smoother, and convex conditional emission M-steps. Its checks use the ordinary
Fisher identity and EM objective ascent. These are correctness properties, not new
optimization theorems. The fixed experiment compares correctly marginalized training
with component references and an explicitly naive roster-deletion control. A stronger
new-method argument still needs correlated-emission/set-process comparisons and either
a distinct modeling advantage or a substantive inference/learning contribution.

Before the next comparison, re-read the dynamic Bernoulli/DPP set-model definitions and
experimental discussion in [Chang, Boyd and Smyth, AISTATS 2024](https://proceedings.mlr.press/v238/chang24a/chang24a.pdf).
Their DPP conditions a normalized set distribution on dynamic history and permits
within-set negative dependence. The paper reports small Bernoulli-versus-DPP likelihood
differences relative to dynamic-versus-static gains, with substantial DPP scaling cost
in its studied setup. This is neither a claim that all DPPs are slow nor a result for
our roster task. Its continuous-time sequence likelihood is not directly commensurate
with J009's fixed-bin recurrence/termination likelihood. A future conditional-bin DPP
reference must use identical observed outcomes, terminal support, history information,
patient partitions and training budgets, and be labeled an adaptation rather than a
reproduction of that paper's neural point-process experiments. No DPP implementation
or comparison result had been completed at that checkpoint.

### Closest-family containment (J010)

[Sharghi et al., Improved Sequential Determinantal Point Processes for Supervised
Video Summarization, ECCV 2018](https://arxiv.org/pdf/1807.10957)
(Section 4 definitions, normalization, sampling and sequential extension read)
defines cardinality-weighted GDPPs: P(S) proportional to pi[|S|] det(L_S). Their
normalizer uses elementary symmetric polynomials of the kernel eigenvalues; the
family includes ordinary and fixed-cardinality DPPs. In our derivation, setting
L_ii=exp(b[h_i]) and log pi[k]=theta*(k-K/2)^2/max(K,1) reproduces J009's unsigned
count emission exactly. This also gives identical recurrent and missing-history
likelihoods when the other transition factors agree. J010 verifies that identity
and a non-diagonal history-shared probability reference, without fitting it.
The paper's sequential video task is not a reproduction of our observation task,
but the containment rules out a new count-emission-family claim. This conclusion
is limited to unsigned J009; it does not identify every signed J007 event law with
an ordinary event-cardinality GDPP.

[Mariet and Sra, Fixed-point Algorithms for Learning Determinantal Point Processes,
ICML 2015](https://proceedings.mlr.press/v37/mariet15.pdf) (abstract/introduction read)
already treats nonconvex DPP parameter learning; adding a generic optimizer does
not supply novelty. No full GDPP learner or empirical superiority over one is claimed.

For J011, the [lifted filtering paper](https://www.ijcai.org/proceedings/2018/0703.pdf)
remains a close reference for exact recursive inference with count/multiset states.
The proposed terminal-thinning and grouped polynomial contractions exploit the
specific count potential and two-bit shift structure. Their implementation and
operation-count reduction are research questions, not a claim that lifting,
binomial transforms or variable elimination are new. Unknown initial populations,
reappearing entities and informative observation remain outside the current task.

The J011 source check also re-read the compound-action definition and prediction
construction in Lüdtke et al.: the general framework permits arbitrary normalized
compound-action laws, while its illustrated probabilities arise from independent
individual choices. Its prediction enumerates applicable compound actions and sums
their masses. J011 factors that sum for a much narrower fixed-history count law;
it is not evidence that the general framework cannot express coupled events.
[Tarlow et al., Fast Exact Inference for Recursive Cardinality Models, UAI 2012](https://proceedings.mlr.press/r10/tarlow12a.html)
(primary abstract and existing earlier model review) remains prior for efficient
cardinality marginalization via auxiliary-variable belief propagation. The current
runtime comparison is against J008's sparse enumeration only. Neither LiMa nor
Tarlow's implementation has been benchmarked here, and generic convolution/lifting
speedups cannot be claimed as new.

### Differentiating the factored filter (J012)

[Eisner, Inside-Outside and Forward-Backward Algorithms Are Just Backprop, 2016](https://aclanthology.org/W16-5901/)
(primary abstract read) explains how differentiating evidence computations yields
posterior expectations and gradients. J012 follows that established principle for
the specialized J011 contraction. Its research purpose is to retain the computational
benefit during smoothing and learning; adding an adjoint or verifying Fisher's identity
does not itself establish novelty. The emitted derivatives concern the same fixed
known-roster model, not an identified clinical missingness mechanism.

### Conditioned sequential Monte Carlo reference (J013)

[Doucet and Johansen, A Tutorial on Particle Filtering and Smoothing](https://www.stats.ox.ac.uk/~doucet/doucet_johansen_tutorialPF2011.pdf)
(introduction and generic SMC/proposal discussion consulted) supplies the standard
importance/resampling framework. J013 conditions the hidden recurrence proposal on
the current observed recurrence pattern, with exact cardinality-polynomial sampling;
shared latent-state and hidden-terminal proposals still use their prior laws. This
is a problem-specific reference implementation of known particle methods, not an
optimal proposal, an implementation of every SMC refinement, or a novel sampler.
