"""Planning: how many users an experiment needs, and how long it will run."""
import math

from scipy.optimize import brentq
from scipy.stats import norm


def sample_size_proportions(baseline, mde, alpha=0.05, power=0.80, relative=False):
    """Users needed in EACH group to detect a change in a conversion rate.

    baseline: control conversion rate, e.g. 0.12
    mde: minimum detectable effect. Absolute points by default (0.01 = one point);
         set relative=True to give it as a share of the baseline (0.05 = 5% lift).
    """
    if not 0 < baseline < 1:
        raise ValueError("baseline must be between 0 and 1")
    p1 = baseline
    p2 = baseline * (1 + mde) if relative else baseline + mde
    if not 0 < p2 < 1 or p2 == p1:
        raise ValueError("mde gives an impossible treatment rate")
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    p_bar = (p1 + p2) / 2
    numerator = (
        z_alpha * math.sqrt(2 * p_bar * (1 - p_bar))
        + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return math.ceil(numerator / (p2 - p1) ** 2)


def sample_size_means(sd, mde, alpha=0.05, power=0.80):
    """Users needed in EACH group to detect a change of `mde` in a mean."""
    if sd <= 0 or mde == 0:
        raise ValueError("sd must be positive and mde non-zero")
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    return math.ceil(2 * (z_alpha + z_beta) ** 2 * sd**2 / mde**2)


def power_proportions(baseline, treatment, n_per_group, alpha=0.05):
    """Chance of a significant result when the true rates are baseline and treatment."""
    z_alpha = norm.ppf(1 - alpha / 2)
    p_bar = (baseline + treatment) / 2
    se_null = math.sqrt(2 * p_bar * (1 - p_bar) / n_per_group)
    se_alt = math.sqrt(
        (baseline * (1 - baseline) + treatment * (1 - treatment)) / n_per_group
    )
    diff = abs(treatment - baseline)
    return float(norm.cdf((diff - z_alpha * se_null) / se_alt))


def mde_proportions(baseline, n_per_group, alpha=0.05, power=0.80):
    """Smallest absolute lift a test of this size can reliably detect."""
    upper = 1 - baseline - 1e-9
    return float(
        brentq(
            lambda d: power_proportions(baseline, baseline + d, n_per_group, alpha) - power,
            1e-9,
            upper,
        )
    )


def duration_days(n_per_group, daily_users, groups=2, traffic_share=1.0):
    """Days needed to collect the sample, given eligible users per day."""
    if daily_users <= 0 or not 0 < traffic_share <= 1:
        raise ValueError("daily_users must be positive and traffic_share in (0, 1]")
    return math.ceil(n_per_group * groups / (daily_users * traffic_share))
