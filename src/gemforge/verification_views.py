"""Typed views of stored observations; never rerun or revise a verification verdict."""

import json

from .schemas import ExitCapsule, ProbeComparison, ProbeObservation, VerificationView


def verification_view(capsule: ExitCapsule) -> VerificationView:
    verification = capsule.verification
    limitations = []

    def observations(side):
        if side is None:
            return {}
        # Old capsules already hold actual probe JSON on sanitized stdout. Decode
        # only matching observed outcomes; incomplete details stay explicitly absent.
        details = {}
        commands = [c for c in side.commands if c.check == "probes"]
        if len(commands) == 1 and len(commands[0].stdout) <= 100_000:
            try:
                rows = json.loads(commands[0].stdout)
                for row in rows:
                    value = ProbeObservation.model_validate(row)
                    if value.name in details or side.probe_outcomes.get(value.name) != value.status:
                        raise ValueError("Ambiguous probe details")
                    details[value.name] = value
                if set(details) != set(side.probe_outcomes):
                    raise ValueError("Incomplete probe details")
            except (ValueError, TypeError):
                details = {}
        if side.probe_outcomes and not details:
            limitations.append(
                f"{side.label}: detailed probe values are unavailable or inconsistent; statuses alone are retained."
            )
        return {
            name: details.get(name, ProbeObservation(name=name, status=status))
            for name, status in side.probe_outcomes.items()
        }

    before, after = observations(verification.baseline), observations(verification.candidate)
    specifications = {p.name: p for p in verification.probes}
    comparisons = {
        c.check.removeprefix("probe:"): c
        for c in verification.comparisons
        if c.check.startswith("probe:")
    }
    probes = [
        ProbeComparison(
            name=name,
            specification=specifications.get(name),
            baseline=before.get(name),
            candidate=after.get(name),
            comparison=comparisons.get(name),
        )
        for name in sorted(set(before) | set(after) | set(specifications))
    ]
    return VerificationView(
        verification=verification.model_copy(deep=True), probes=probes, limitations=limitations
    )
