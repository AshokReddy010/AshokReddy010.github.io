"""abkit: a small toolkit for planning and analysing A/B tests."""

from .checks import srm_check
from .corrections import benjamini_hochberg, bonferroni, holm
from .cuped import cuped_adjust
from .power import (
    duration_days,
    mde_proportions,
    power_proportions,
    sample_size_means,
    sample_size_proportions,
)
from .readout import analyse_experiment, render_readout
from .stats import bootstrap_mean_diff, mean_test, proportion_test

__all__ = [
    "srm_check",
    "bonferroni",
    "holm",
    "benjamini_hochberg",
    "cuped_adjust",
    "duration_days",
    "mde_proportions",
    "power_proportions",
    "sample_size_means",
    "sample_size_proportions",
    "analyse_experiment",
    "render_readout",
    "bootstrap_mean_diff",
    "mean_test",
    "proportion_test",
]
