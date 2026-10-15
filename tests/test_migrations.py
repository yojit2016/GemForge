import pytest

from gemforge.engine import scan_repository
from gemforge.migrations import apply_migration, prepare_migration


def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "requirements.txt").write_text("pydantic==1.10.13 # keep\nrequests==2.31.0\n")
    (root / "pyproject.toml").write_text(
        '[project]\ndependencies=["pydantic>=2", "requests==2.31.0"]\n'
    )
    return root


def test_manifest_plan_preserves_unrelated_requirements_and_comments(tmp_path):
    root = repo(tmp_path)
    before = (root / "requirements.txt").read_bytes()
    plan = prepare_migration(root, "pydantic", "pydantic>=2", scan_repository(root))
    assert (root / "requirements.txt").read_bytes() == before
    assert len(plan.edits) == 1
    assert "pydantic>=2 # keep" in plan.edits[0].after
    assert "requests==2.31.0" in plan.edits[0].after
    assert "--- a/requirements.txt" in plan.unified_diff
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "requirements.txt").write_bytes(before)
    apply_migration(copy, plan)
    assert "pydantic>=2 # keep" in (copy / "requirements.txt").read_text()
    (copy / "requirements.txt").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        apply_migration(copy, plan)


@pytest.mark.parametrize(
    "target",
    ["requests>=2", "pydantic", "pydantic @ https://host/pkg.whl", "pydantic>=2; os_name=='nt'"],
)
def test_reject_unsafe_targets(tmp_path, target):
    root = repo(tmp_path)
    with pytest.raises(ValueError):
        prepare_migration(root, "pydantic", target, scan_repository(root))


def test_requires_valid_recommendation_or_explicit_target(tmp_path):
    root = repo(tmp_path)
    with pytest.raises(ValueError, match="generated target"):
        prepare_migration(root, "pydantic", None, scan_repository(root))


def test_toml_target_edit_is_narrow_and_valid(tmp_path):
    root = repo(tmp_path)
    plan = prepare_migration(root, "pydantic", "pydantic>=2,<3", scan_repository(root))
    assert len(plan.edits) == 2
    assert all("requests==2.31.0" in e.after for e in plan.edits)


def test_edit_path_cannot_escape_copy(tmp_path):
    root = repo(tmp_path)
    plan = prepare_migration(root, "pydantic", "pydantic>=2", scan_repository(root))
    plan.edits[0].file = "../outside.txt"
    with pytest.raises(ValueError, match="Unsafe"):
        apply_migration(root, plan)
