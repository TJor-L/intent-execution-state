# Methodology

Let $H_t$ contain only events with occurrence and information availability no later
than $t$. A shared encoder produces $h_t=f_\theta(H_t)$. The candidate factors are
$P(O_{future}\mid H_t)$, $P(A_{future}\mid H_t,O_{available})$, and
$P(Y_{future}\mid H_t,A_{executed,available})$. Future treatments must not be supplied
as known features for a prediction made at the order index.

For first-event execution define causes administration, cancellation/discontinuation,
and another verified terminal outcome. Administrative observation end is censoring,
not a fourth event. For cause $k$, intensity $\lambda_k(u\mid h_t,O)$ yields
$S(u)=\exp[-\int_0^u\sum_k\lambda_k(v)dv]$ and
$F_k(u)=\int_0^u S(v)\lambda_k(v)dv$.

The implemented baseline uses piecewise constant, population-level intensities.
It estimates each bin/cause rate from event counts and person-time with a weak Gamma
prior. The planned structured model conditions those rates on history and available
order attributes. Test this change against equally informed independent heads.

The first-event formulation does not represent recurring doses or continuous infusions.
It assumes observation/censoring is conditionally noninformative for the likelihood
target; discharge and workflow may violate this. Revisit the risk set and censoring
model after inspecting source semantics. These are predictive conditionals, not
identified interventional distributions.
