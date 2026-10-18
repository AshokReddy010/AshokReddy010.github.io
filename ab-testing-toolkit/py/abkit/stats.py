"""Analysis: compare control and treatment on a rate or a mean."""
import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy.stats import norm, t as student_t


@dataclass
class TestResult:
    metric: str
    method: str
    n_control: int
    n_treatment: int
    control: float
    treatment: float
    abs_diff: float
    ci_low: float
    ci_high: float
    rel_lift: float
    rel_ci_low: float
    rel_ci_high: float
    p_value: float
    alpha: float

    @property
    def significant(self):
        return self.p_value < self.alpha

    def to_dict(self):
        return asdict(self) | {"significant": self.significant}


def _relative_ci(mean_c, mean_t, var_mean_c, var_mean_t, crit):
    """Confidence interval for the relative lift, using the delta method."""
    if mean_c == 0:
        return float("nan"), float("nan"), float("nan")
    lift = mean_t / mean_c - 1
    se = math.sqrt(var_mean_t / mean_c**2 + mean_t**2 * var_mean_c / mean_c**4)
    return lift, lift - crit * se, lift + crit * se


def proportion_test(x_control, n_control, x_treatment, n_treatment, alpha=0.05, metric="conversion"):
    """Two-sided z-test for the difference between two conversion rates."""
    if min(n_control, n_treatment) <= 0:
        raise ValueError("both groups need at least one user")
    p_c = x_control / n_control
    p_t = x_treatment / n_treatment
    diff = p_t - p_c
    pooled = (x_control + x_treatment) / (n_control + n_treatment)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n_control + 1 / n_treatment))
    z = diff / se_pooled if se_pooled > 0 else 0.0
    p_value = 2 * (1 - norm.cdf(abs(z)))
    var_c = p_c * (1 - p_c) / n_control
    var_t = p_t * (1 - p_t) / n_treatment
    crit = norm.ppf(1 - alpha / 2)
    se = math.sqrt(var_c + var_t)
    lift, lift_low, lift_high = _relative_ci(p_c, p_t, var_c, var_t, crit)
    return TestResult(
        metric, "two-proportion z-test", int(n_control), int(n_treatment), p_c, p_t, diff,
        diff - crit * se, diff + crit * se, lift, lift_low, lift_high, float(p_value), alpha,
    )


def mean_test(control, treatment, alpha=0.05, metric="mean"):
    """Welch's t-test for the difference between two means (unequal variances)."""
    c = np.asarray(control, dtype=float)
    t = np.asarray(treatment, dtype=float)
    if len(c) < 2 or len(t) < 2:
        raise ValueError("both groups need at least two users")
    var_c = c.var(ddof=1) / len(c)
    var_t = t.var(ddof=1) / len(t)
    diff = t.mean() - c.mean()
    se = math.sqrt(var_c + var_t)
    dof = (var_c + var_t) ** 2 / (var_c**2 / (len(c) - 1) + var_t**2 / (len(t) - 1))
    stat = diff / se if se > 0 else 0.0
    p_value = 2 * student_t.sf(abs(stat), dof)
    crit = student_t.ppf(1 - alpha / 2, dof)
    lift, lift_low, lift_high = _relative_ci(c.mean(), t.mean(), var_c, var_t, crit)
    return TestResult(
        metric, "Welch t-test", len(c), len(t), float(c.mean()), float(t.mean()), float(diff),
        float(diff - crit * se), float(diff + crit * se), lift, lift_low, lift_high, float(p_value), alpha,
    )


def bootstrap_mean_diff(control, treatment, n_boot=2000, alpha=0.05, seed=0):
    """Percentile bootstrap interval for the difference in means.

    Makes no assumption about the shape of the data, so it is a useful second
    opinion on skewed metrics such as revenue per user.
    """
    rng = np.random.default_rng(seed)
    c = np.asarray(control, dtype=float)
    t = np.asarray(treatment, dtype=float)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = rng.choice(t, len(t)).mean() - rng.choice(c, len(c)).mean()
    low, high = np.quantile(diffs, [alpha / 2, 1 - alpha / 2])
    return float(t.mean() - c.mean()), float(low), float(high)
