"""CUPED: use pre-experiment behaviour to reduce noise in a metric."""
import numpy as np


def cuped_adjust(metric, covariate):
    """Return the CUPED-adjusted metric and the share of variance removed.

    metric: the outcome measured during the experiment, one value per user
    covariate: the same users' value from BEFORE the experiment started

    Because the covariate was fixed before assignment, removing the part of the
    metric it explains does not bias the treatment effect. It only shrinks the
    variance, which narrows the confidence interval.
    """
    y = np.asarray(metric, dtype=float)
    x = np.asarray(covariate, dtype=float)
    if y.shape != x.shape:
        raise ValueError("metric and covariate must have the same length")
    var_x = x.var(ddof=1)
    if var_x == 0:
        return y.copy(), 0.0
    theta = np.cov(x, y, ddof=1)[0, 1] / var_x
    adjusted = y - theta * (x - x.mean())
    reduction = 1 - adjusted.var(ddof=1) / y.var(ddof=1)
    return adjusted, float(reduction)
