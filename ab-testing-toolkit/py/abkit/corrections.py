"""Corrections for testing several metrics or variants at once."""
import numpy as np


def bonferroni(p_values):
    """Multiply each p-value by the number of tests. Simple and conservative."""
    p = np.asarray(p_values, dtype=float)
    return np.minimum(p * len(p), 1.0)


def holm(p_values):
    """Holm's step-down method. Controls the same error as Bonferroni with more power."""
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adjusted = np.empty(m)
    running_max = 0.0
    for rank, idx in enumerate(order):
        running_max = max(running_max, (m - rank) * p[idx])
        adjusted[idx] = min(running_max, 1.0)
    return adjusted


def benjamini_hochberg(p_values):
    """Benjamini-Hochberg. Controls the false discovery rate; suits exploratory metrics."""
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)[::-1]
    m = len(p)
    adjusted = np.empty(m)
    running_min = 1.0
    for i, idx in enumerate(order):
        rank = m - i
        running_min = min(running_min, p[idx] * m / rank)
        adjusted[idx] = running_min
    return adjusted
