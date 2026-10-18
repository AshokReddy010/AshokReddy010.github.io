"""Simulations that check the toolkit behaves as statistics says it should."""
import numpy as np
from scipy.stats import norm


def _z_p_values(x_c, x_t, n):
    p_c, p_t = x_c / n, x_t / n
    pooled = (x_c + x_t) / (2 * n)
    se = np.sqrt(pooled * (1 - pooled) * 2 / n)
    z = np.divide(p_t - p_c, se, out=np.zeros_like(se, dtype=float), where=se > 0)
    return 2 * (1 - norm.cdf(np.abs(z)))


def rejection_rate(p_control, p_treatment, n_per_group, n_sims=20000, alpha=0.05, seed=0):
    """Share of simulated experiments that come out significant.

    With equal rates this is the false positive rate; with different rates it is power.
    """
    rng = np.random.default_rng(seed)
    x_c = rng.binomial(n_per_group, p_control, n_sims)
    x_t = rng.binomial(n_per_group, p_treatment, n_sims)
    return float((_z_p_values(x_c, x_t, n_per_group) < alpha).mean())


def interval_coverage(p_control, p_treatment, n_per_group, n_sims=20000, alpha=0.05, seed=0):
    """Share of simulated confidence intervals that contain the true difference."""
    rng = np.random.default_rng(seed)
    p_c = rng.binomial(n_per_group, p_control, n_sims) / n_per_group
    p_t = rng.binomial(n_per_group, p_treatment, n_sims) / n_per_group
    se = np.sqrt(p_c * (1 - p_c) / n_per_group + p_t * (1 - p_t) / n_per_group)
    crit = norm.ppf(1 - alpha / 2)
    diff, truth = p_t - p_c, p_treatment - p_control
    return float(((diff - crit * se <= truth) & (truth <= diff + crit * se)).mean())


def peeking_false_positive_rate(rate, n_per_group, looks, n_sims=20000, alpha=0.05, seed=0, corrected=False):
    """False positive rate when the test is checked `looks` times and stopped at the first win.

    Both groups share the same true rate, so every "win" is a false one.
    corrected=True tests each look at alpha / looks (Bonferroni across looks).
    """
    rng = np.random.default_rng(seed)
    step = n_per_group // looks
    x_c = np.zeros(n_sims)
    x_t = np.zeros(n_sims)
    stopped = np.zeros(n_sims, dtype=bool)
    threshold = alpha / looks if corrected else alpha
    for look in range(1, looks + 1):
        x_c += rng.binomial(step, rate, n_sims)
        x_t += rng.binomial(step, rate, n_sims)
        stopped |= _z_p_values(x_c, x_t, step * look) < threshold
    return float(stopped.mean())
