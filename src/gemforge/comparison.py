"""Compare only observed paired checks; never convert missing execution to success."""

from .schemas import CheckComparison, EnvironmentResult, VerificationStatus


def compare_environments(
    baseline: EnvironmentResult, candidate: EnvironmentResult
) -> VerificationStatus:
    comparisons = []

    def compare(name: str, before: str | None, after: str | None):
        if before == after == "passed":
            status = "passed_both"
        elif before == "passed" and after in {"failed", "error"}:
            status = "regression"
        elif before in {"failed", "error"} and after == "passed":
            status = "repaired"
        elif before in {"failed", "error"} and after in {"failed", "error"}:
            status = "baseline_failure"
        elif before == after == "not_run":
            status = "not_run"
        else:
            status = "not_comparable"
        comparisons.append(
            CheckComparison(
                check=name,
                status=status,
                explanation=f"Baseline={before or 'missing'}; candidate={after or 'missing'}.",
            )
        )

    original = {r.check: r for r in baseline.commands}
    proposed = {r.check: r for r in candidate.commands}
    for check in sorted(set(original) | set(proposed)):
        compare(
            check,
            original[check].status if check in original else None,
            proposed[check].status if check in proposed else None,
        )
    for key in sorted(set(baseline.test_outcomes) | set(candidate.test_outcomes)):
        compare("test:" + key, baseline.test_outcomes.get(key), candidate.test_outcomes.get(key))
    for key in sorted(set(baseline.probe_outcomes) | set(candidate.probe_outcomes)):
        compare("probe:" + key, baseline.probe_outcomes.get(key), candidate.probe_outcomes.get(key))
    verdict, status, reason = (
        "inconclusive",
        "inconclusive",
        "Selected checks were incomplete or retained baseline failures.",
    )
    runtime_regressions = [
        c
        for c in comparisons
        if c.status == "regression" and c.check not in {"venv", "install", "packages", "python"}
    ]
    setup_failed = any(
        not any(r.check == "install" and r.status == "passed" for r in side.commands)
        or any(r.status in {"timeout", "execution_failed"} for r in side.commands)
        for side in (baseline, candidate)
    )
    if runtime_regressions:
        verdict, status, reason = (
            "regression_detected",
            "failed",
            "At least one comparable baseline-passing check failed in the candidate.",
        )
    elif setup_failed:
        verdict, status, reason = (
            "execution_failed",
            "inconclusive",
            "Installation/setup failed or a command timed out; compatibility is not established.",
        )
    elif (
        candidate.test_outcomes
        and any(v == "passed" for v in candidate.test_outcomes.values())
        and not baseline.limitations
        and not candidate.limitations
        and all(c.status in {"passed_both", "repaired"} for c in comparisons)
    ):
        verdict, status, reason = (
            "verified_for_selected_checks",
            "passed",
            "All selected comparable candidate checks passed. This is not a general safety guarantee.",
        )

    def legacy(side):
        if not side.commands:
            return "not_run"
        if any(c.status in {"timeout", "execution_failed", "not_run"} for c in side.commands):
            return "inconclusive"
        return "failed" if any(c.status == "failed" for c in side.commands) else "passed"

    return VerificationStatus(
        status=status,
        verdict=verdict,
        reason=reason,
        original_status=legacy(baseline),
        candidate_status=legacy(candidate),
        baseline=baseline,
        candidate=candidate,
        comparisons=comparisons,
        evidence=[f"{c.check}: {c.status}" for c in comparisons],
    )
