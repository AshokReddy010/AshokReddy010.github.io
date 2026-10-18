"""Turn raw experiment data into a decision and a written readout."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .checks import srm_check
from .corrections import holm
from .cuped import cuped_adjust
from .power import mde_proportions
from .stats import bootstrap_mean_diff, mean_test, proportion_test


@dataclass
class Readout:
    name: str
    decision: str
    reason: str
    srm: object
    primary: object
    secondary: list = field(default_factory=list)
    guardrails: list = field(default_factory=list)
    cuped: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def _split(df, group_col, control, treatment):
    return df[df[group_col] == control], df[df[group_col] == treatment]


def analyse_experiment(
    df,
    name="Experiment",
    group_col="group",
    control="control",
    treatment="treatment",
    primary="converted",
    revenue="revenue",
    pre_revenue="pre_revenue",
    guardrail="refunded",
    expected_control_share=0.5,
    alpha=0.05,
):
    """Run the full analysis on one row per user and return a Readout.

    Decision rules, in order:
      1. Sample ratio mismatch fails  -> do not trust the result
      2. A guardrail is significantly worse -> do not ship
      3. Primary metric interval is entirely above zero -> ship
      4. Primary metric interval is entirely below zero -> do not ship
      5. Otherwise -> inconclusive
    """
    c, t = _split(df, group_col, control, treatment)
    srm = srm_check(len(c), len(t), expected_control_share)

    primary_result = proportion_test(
        int(c[primary].sum()), len(c), int(t[primary].sum()), len(t), alpha, metric="Conversion rate"
    )

    secondary, cuped_info, notes = [], {}, []
    if revenue in df:
        raw = mean_test(c[revenue], t[revenue], alpha, metric="Revenue per user")
        secondary.append(raw)
        _, boot_low, boot_high = bootstrap_mean_diff(c[revenue], t[revenue], n_boot=1000, alpha=alpha, seed=7)
        notes.append(
            f"Bootstrap check on revenue per user: interval {boot_low:+.3f} to {boot_high:+.3f}, "
            f"against {raw.ci_low:+.3f} to {raw.ci_high:+.3f} from the t-test."
        )
        if pre_revenue in df:
            adjusted, reduction = cuped_adjust(df[revenue].to_numpy(), df[pre_revenue].to_numpy())
            is_c = (df[group_col] == control).to_numpy()
            is_t = (df[group_col] == treatment).to_numpy()
            adj = mean_test(adjusted[is_c], adjusted[is_t], alpha, metric="Revenue per user (CUPED)")
            secondary.append(adj)
            cuped_info = {
                "variance_reduction": reduction,
                "ci_width_raw": raw.ci_high - raw.ci_low,
                "ci_width_cuped": adj.ci_high - adj.ci_low,
            }

    guardrails = []
    if guardrail in df:
        guardrails.append(
            proportion_test(
                int(c[guardrail].sum()), len(c), int(t[guardrail].sum()), len(t), alpha, metric="Refund rate"
            )
        )

    # Every metric other than the primary one is corrected together, so adding
    # metrics does not add false wins. The CUPED row repeats a metric, so it is left out.
    extra = [r for r in secondary if "CUPED" not in r.metric] + guardrails
    if len(extra) > 1:
        adjusted_p = holm([r.p_value for r in extra])
        notes.append(
            "Holm-adjusted p-values for the non-primary metrics: "
            + ", ".join(f"{r.metric.lower()} {p:.4f}" for r, p in zip(extra, adjusted_p))
            + "."
        )

    guardrail_harm = [g for g in guardrails if g.significant and g.abs_diff > 0]
    if not srm.passed:
        decision = "Do not trust"
        reason = (
            f"Sample ratio mismatch: expected {expected_control_share:.0%} of users in control, "
            f"observed {srm.observed_control_share:.2%} (p = {srm.p_value:.2g}). "
            "Find the assignment or logging fault before reading any metric."
        )
    elif guardrail_harm:
        g = guardrail_harm[0]
        decision = "Do not ship"
        reason = f"Guardrail {g.metric.lower()} got significantly worse ({g.abs_diff:+.2%} points, p = {g.p_value:.3g})."
    elif primary_result.ci_low > 0:
        decision = "Ship"
        reason = (
            f"Conversion rose by {primary_result.abs_diff:+.2%} points "
            f"(95% interval {primary_result.ci_low:+.2%} to {primary_result.ci_high:+.2%}), with no guardrail harmed."
        )
    elif primary_result.ci_high < 0:
        decision = "Do not ship"
        reason = f"Conversion fell by {primary_result.abs_diff:+.2%} points and the interval is entirely below zero."
    else:
        detectable = mde_proportions(primary_result.control, min(len(c), len(t)), alpha)
        decision = "Inconclusive"
        reason = (
            f"The interval for conversion ({primary_result.ci_low:+.2%} to {primary_result.ci_high:+.2%}) includes zero. "
            f"A test of this size can reliably detect a lift of about {detectable:.2%} points or more."
        )

    return Readout(name, decision, reason, srm, primary_result, secondary, guardrails, cuped_info, notes)


def _row(result, as_rate):
    fmt = (lambda v: f"{v:.2%}") if as_rate else (lambda v: f"{v:.3f}")
    diff = (lambda v: f"{v:+.2%} pts") if as_rate else (lambda v: f"{v:+.3f}")
    return {
        "Metric": result.metric,
        "Control": fmt(result.control),
        "Treatment": fmt(result.treatment),
        "Difference": diff(result.abs_diff),
        "95% interval": f"{diff(result.ci_low)} to {diff(result.ci_high)}",
        "Relative lift": f"{result.rel_lift:+.1%}",
        "p-value": f"{result.p_value:.4f}",
    }


def render_readout(readout):
    """Format a Readout as markdown."""
    rows = [_row(readout.primary, True)]
    rows += [_row(r, False) for r in readout.secondary]
    rows += [_row(g, True) for g in readout.guardrails]
    table = pd.DataFrame(rows).to_markdown(index=False)
    srm = readout.srm
    lines = [
        f"# {readout.name}",
        "",
        f"**Decision: {readout.decision}.** {readout.reason}",
        "",
        "## Health check",
        "",
        f"- Users: {srm.n_control:,} control, {srm.n_treatment:,} treatment",
        f"- Sample ratio mismatch: {'passed' if srm.passed else 'FAILED'} (p = {srm.p_value:.3g}, threshold {srm.threshold})",
        "",
        "## Results",
        "",
        table,
        "",
    ]
    if readout.cuped:
        c = readout.cuped
        lines += [
            "## Variance reduction",
            "",
            f"- CUPED with pre-experiment revenue removed {c['variance_reduction']:.1%} of the variance in revenue per user.",
            f"- Interval width went from {c['ci_width_raw']:.3f} to {c['ci_width_cuped']:.3f} "
            f"({1 - c['ci_width_cuped'] / c['ci_width_raw']:.1%} narrower).",
            "",
        ]
    if readout.notes:
        lines += ["## Notes", ""] + [f"- {n}" for n in readout.notes] + [""]
    return "\n".join(lines)
