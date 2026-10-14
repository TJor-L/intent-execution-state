# Training objectives

For duration $d_i$ and cause $c_i\in\{0,1,2,3\}$, zero denotes right censoring.
The observed-data negative log likelihood is

$$\ell_i=\sum_b E_{ib}\sum_k\lambda_{bk}
-\mathbb{1}[c_i>0]\log\lambda_{b(d_i),c_i},$$

where $E_{ib}=\max(0,\min(d_i-t_b,t_{b+1}-t_b))$. Intervals are $(t_b,t_{b+1}]$;
an event exactly at a right edge belongs to that interval. Censoring inside a bin
contributes its fractional exposure, not a complete-bin survival term.

The baseline posterior mean rate is $(N_{bk}+0.5)/(\sum_i E_{ib}+1\text{ hour})$.
This is an explicitly smoothed estimator, not the unsmoothed MLE. All estimates use
training patients only. Held-out loss excludes the prior. Continuous-time density
likelihood can be negative and depends on the chosen time unit (hours).

For a later neural implementation enforce positive rates (e.g. softplus), then reuse
the same exposure logic with autograd. Optional state regression needs a defined
measurement target, observation mask and timing mechanism; weights between execution,
intention and state objectives must be tuned using validation data only. No joint
loss or causal treatment objective is implemented in Phase 0.
