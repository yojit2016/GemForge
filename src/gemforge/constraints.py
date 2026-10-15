"""Conservative satisfiability checks; an untested candidate is never a proof."""

from collections import defaultdict

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from .schemas import ConstraintAssessment, Dependency, DetectedRisk


def assess(dependencies: list[Dependency]) -> ConstraintAssessment:
    package = dependencies[0].package

    def result(status: str, explanation: str, witness: str | None = None) -> ConstraintAssessment:
        return ConstraintAssessment(
            package=package, status=status, explanation=explanation, witness=witness
        )

    if any(d.marker or d.group != "runtime" or d.url for d in dependencies):
        return result(
            "uncertain",
            "Markers, optional groups, or direct references require an explicit target environment and install selection.",
        )
    combined = SpecifierSet(",".join(d.constraint for d in dependencies if d.constraint))
    specs = list(combined)
    # Public exact pins denote all local variants too. Local-version expressions and
    # arbitrary equality are deliberately excluded from negative pin proofs.
    special = any(s.operator == "===" or "+" in s.version for s in specs)
    pins = [Version(s.version) for s in specs if s.operator == "==" and "*" not in s.version]
    if pins and not special:
        pin = pins[0]
        if combined.contains(pin, prereleases=True):
            return result(
                "compatible", "An exact version satisfies all declared constraints.", str(pin)
            )
        return result(
            "conflict",
            f"Exact pin {pin} is excluded by the combined PEP 440 constraints: {combined}.",
        )

    # Bounds are a superset of the allowed versions; disjoint bounds prove empty
    # intersection. Finite != exclusions cannot alone establish a general conflict.
    lower: tuple[Version, bool] | None = None
    upper: tuple[Version, bool] | None = None

    def bound(version: Version, inclusive: bool, is_lower: bool) -> None:
        nonlocal lower, upper
        old = lower if is_lower else upper
        stronger = old is None or (version > old[0] if is_lower else version < old[0])
        new = (version, inclusive)
        if old and version == old[0]:
            new = (version, inclusive and old[1])
            stronger = True
        if stronger:
            if is_lower:
                lower = new
            else:
                upper = new

    if not special:
        for spec in specs:
            op, raw = spec.operator, spec.version
            if op == "==" and raw.endswith(".*"):
                prefix = Version(raw[:-2])
                parts = list(prefix.release)
                parts[-1] += 1
                epoch = f"{prefix.epoch}!" if prefix.epoch else ""
                bound(Version(f"{epoch}{'.'.join(map(str, prefix.release))}.dev0"), True, True)
                bound(Version(f"{epoch}{'.'.join(map(str, parts))}.dev0"), False, False)
            elif op == "~=":
                value = Version(raw)
                parts = list(value.release[:-1])
                parts[-1] += 1
                epoch = f"{value.epoch}!" if value.epoch else ""
                bound(value, True, True)
                bound(Version(f"{epoch}{'.'.join(map(str, parts))}.dev0"), False, False)
            elif op in {">=", ">", "<=", "<"}:
                bound(Version(raw), op in {">=", "<="}, op in {">=", ">"})
        if lower and upper:
            if lower[0] > upper[0] or (lower[0] == upper[0] and not (lower[1] and upper[1])):
                return result("conflict", f"Disjoint PEP 440 version bounds: {combined}.")
            if lower[0] == upper[0] and not combined.contains(lower[0], prereleases=True):
                return result(
                    "conflict", f"The only bound intersection is explicitly excluded: {combined}."
                )

    # A witness proves metadata overlap, never the availability of a real release.
    candidates = {Version("0"), Version("1"), Version("2"), *pins}
    for spec in specs:
        try:
            value = Version(spec.version.removesuffix(".*"))
            candidates.add(value)
            epoch = f"{value.epoch}!" if value.epoch else ""
            parts = list(value.release)
            parts[-1] += 1
            candidates.add(Version(epoch + ".".join(map(str, parts))))
            candidates.add(Version(f"{epoch}{'.'.join(map(str, value.release))}.post1"))
        except InvalidVersion:
            pass
    for candidate in sorted(candidates):
        if combined.contains(candidate, prereleases=True):
            return result(
                "compatible",
                "A version satisfies the metadata intersection; published availability is not checked.",
                str(candidate),
            )
    return result(
        "uncertain",
        f"No witness or supported emptiness proof found for {combined}; no release catalog was queried.",
    )


def detect_risks(
    dependencies: list[Dependency],
) -> tuple[list[ConstraintAssessment], list[DetectedRisk]]:
    grouped: dict[str, list[Dependency]] = defaultdict(list)
    for dependency in dependencies:
        grouped[dependency.package].append(dependency)
    assessments = []
    risks = []
    for package, entries in sorted(grouped.items()):
        assessment = assess(entries)
        assessments.append(assessment)
        if assessment.status != "compatible":
            risks.append(
                DetectedRisk(
                    package=package,
                    kind="constraint_conflict"
                    if assessment.status == "conflict"
                    else "constraint_uncertainty",
                    certainty="proven" if assessment.status == "conflict" else "uncertain",
                    evidence=assessment.explanation,
                    sources=[d.source for d in entries],
                )
            )
        if any(d.url for d in entries):
            risks.append(
                DetectedRisk(
                    package=package,
                    kind="direct_reference",
                    certainty="uncertain",
                    evidence="Direct reference is recorded only; remote source and artifact metadata were not fetched.",
                    sources=[d.source for d in entries if d.url],
                )
            )
    return assessments, risks
