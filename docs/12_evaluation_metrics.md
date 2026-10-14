# Evaluation metrics

Implemented: per-order observed-data NLL averaged over the held-out split, with a
patient-cluster percentile bootstrap interval. The baseline exports $S(t)$ and
$F_k(t)$ at time-bin edges. For constant total rate $r_b$ over width $\Delta_b$,
$\Delta F_{bk}=S(t_b)(1-e^{-r_b\Delta_b})\lambda_{bk}/r_b$.
Tests require each CIF to be nondecreasing and $S+\sum_kF_k=1$.

Planned execution metrics: time-dependent discrimination and competing-risk calibration
at prespecified horizons, with a suitable censoring estimator fitted without test-label
leakage. Evaluate eligibility/positivity of censoring weights and provide uncertainty.
Do not score every censored case as a known “not administered by horizon.”

Planned physiology metrics: MAE $n^{-1}\sum|y-\hat y|$, RMSE
$\sqrt{n^{-1}\sum(y-\hat y)^2}$, probabilistic log scores and calibration, stratified
by prediction and observation interval. The first observed lab after treatment is
not a fixed-time target. Specify the measurement process and missingness estimand.

Label counts and population CIF are diagnostics, not proof of individual discrimination.
The current baseline is identical across patients and has no clinical predictive claim.
