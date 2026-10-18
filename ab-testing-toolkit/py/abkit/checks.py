"""Health checks to run before trusting any experiment result."""
from dataclasses import dataclass

from scipy.stats import chisquare


@dataclass
class SrmResult:
    n_control: int
    n_treatment: int
    expected_control_share: float
    observed_control_share: float
    p_value: float
    threshold: float

    @property
    def passed(self):
        return self.p_value >= self.threshold


def srm_check(n_control, n_treatment, expected_control_share=0.5, threshold=0.001):
    """Sample ratio mismatch: did users split between groups as designed?

    A tiny p-value means the split is off by more than chance allows, which
    points to a bug in assignment or logging. Results should not be trusted
    until it is explained. The strict 0.001 threshold is the usual convention,
    because this check runs on every experiment.
    """
    total = n_control + n_treatment
    if total == 0:
        raise ValueError("no users")
    expected = [total * expected_control_share, total * (1 - expected_control_share)]
    p_value = chisquare([n_control, n_treatment], f_exp=expected).pvalue
    return SrmResult(
        int(n_control), int(n_treatment), expected_control_share, n_control / total, float(p_value), threshold
    )
