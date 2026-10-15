import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from gemforge.ai import GemmaConfig
from gemforge.api import app as api
from gemforge.cli import app
from gemforge.engine import scan_repository
from gemforge.exporters import capsule_markdown, write_capsule
from gemforge.schemas import ExitCapsule


def write(root: Path, name: str, text: str) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_duplicate_sources_conflict_and_aliases(tmp_path):
    write(
        tmp_path,
        "requirements.txt",
        "# dependencies\nPydantic==1.10.13\nrequests>=2\nrequests>=2\n",
    )
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\ndependencies = [\n "pydantic>=2",\n "requests<3",\n]\n',
    )
    write(
        tmp_path,
        "main.py",
        "import requests as r\nfrom pydantic import BaseModel as BM\nr.get('https://example.test')\nBM()\n",
    )
    capsule = scan_repository(tmp_path)
    assert len(capsule.dependencies) == 5
    assert len([d for d in capsule.dependencies if d.package == "requests"]) == 3
    assert capsule.dependencies[0].source.file in {"pyproject.toml", "requirements.txt"}
    assert [(risk.package, risk.certainty) for risk in capsule.risks] == [("pydantic", "proven")]
    assert capsule.recommendations[0].package == "pydantic"
    assert capsule.recommendations[0].status == "not_requested"
    assert capsule.verification.status == "not_run"
    refs = {u.symbol for u in capsule.usages if u.kind == "reference"}
    assert refs == {"requests.get", "pydantic.BaseModel"}
    assert next(d for d in capsule.dependencies if d.raw == "pydantic>=2").source.line == 3


@pytest.mark.parametrize(
    ("first", "second", "status"),
    [
        ("==1.0", "==1.0.0", "compatible"),
        ("==1.0", "!=1.0", "conflict"),
        (">=2", "<2", "conflict"),
        (">2", "<=2", "conflict"),
        (">=1,<=1", "!=1", "conflict"),
        ("~=1.4.5", ">=1.5", "conflict"),
        ("~=1.4", ">=1.5", "compatible"),
        ("==1.2.*", ">=1.3", "conflict"),
        ("==1.2.*", "==1.2.9", "compatible"),
        ("==1.2", "==1.2+local", "compatible"),
        ("==1.2+local", "!=1.2+local", "uncertain"),
        ("==1!1.0", "<1!1.0", "conflict"),
        ("==1!1.*", ">=1!2", "conflict"),
        ("==2.0rc1", ">=2.0rc1,<3", "compatible"),
        ("==1.0.post1", ">1.0", "conflict"),
        ("==1.0rc1", "<1.0", "conflict"),
        ("==1.0", "~=1.0", "compatible"),
        (">=1", "<2,!=1", "compatible"),
        ("===banana", "", "uncertain"),
        ("", "", "compatible"),
    ],
)
def test_pep440(tmp_path, first, second, status):
    write(tmp_path, "requirements.txt", f"widget{first}\n")
    write(tmp_path, "pyproject.toml", f'[project]\ndependencies = ["widget{second}"]\n')
    capsule = scan_repository(tmp_path)
    assert capsule.constraints[0].status == status
    if capsule.constraints[0].witness:
        from packaging.specifiers import SpecifierSet

        assert SpecifierSet(",".join(filter(None, [first, second]))).contains(
            capsule.constraints[0].witness,
            prereleases=True,
        )


def test_markers_extras_groups_and_urls_are_not_false_proofs(tmp_path):
    write(
        tmp_path,
        "requirements.txt",
        'demo[http]==1; python_version < "3.12"\nremote @ https://example.test/archive.zip\n',
    )
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\ndependencies = ["demo>=2"]\n[project.optional-dependencies]\ntest = ["demo==3"]\n[dependency-groups]\ndev = [{include-group="test"}, "helper>=1"]\n',
    )
    capsule = scan_repository(tmp_path)
    assert all(r.certainty == "uncertain" for r in capsule.risks)
    assert next(d for d in capsule.dependencies if d.extras).extras == ["http"]
    assert any("unsupported dependency entry" in item for item in capsule.limitations)
    assert {r.package for r in capsule.recommendations} == {r.package for r in capsule.risks}


def test_requirements_lines_continuation_invalid_and_unsupported(tmp_path):
    write(
        tmp_path,
        "requirements.txt",
        "# comment\nFoo_Bar>=1,\\\n <2 # note\n-r other.txt\nnot a requirement!\n",
    )
    capsule = scan_repository(tmp_path)
    assert len(capsule.dependencies) == 1
    assert capsule.dependencies[0].package == "foo-bar"
    assert capsule.dependencies[0].source.line == 2
    assert any("pip option" in item for item in capsule.limitations)
    assert any("invalid requirement" in item for item in capsule.limitations)


def test_dynamic_metadata_and_ambiguous_lines(tmp_path):
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\ndynamic=["version"]\ndependencies=["x>=1", "x>=1"]\n',
    )
    capsule = scan_repository(tmp_path)
    assert any("dynamic" in item for item in capsule.limitations)
    assert len(capsule.dependencies) == 2


def test_no_target_execution_and_broken_files_are_reported(tmp_path):
    write(tmp_path, "requirements.txt", "requests\n")
    write(tmp_path, "evil.py", "raise RuntimeError('must not execute')\n")
    write(tmp_path, "broken.py", "def ???\n")
    write(tmp_path, "nested/pyproject.toml", "[project\n")
    write(tmp_path, ".venv/requirements.txt", "ignored==1\n")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    capsule = scan_repository(tmp_path)
    assert len(capsule.dependencies) == 1
    assert any("AST analysis skipped" in item for item in capsule.limitations)
    assert any("manifest could not" in item for item in capsule.limitations)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_imports_rebinding_and_explicit_mapping(tmp_path):
    write(tmp_path, "requirements.txt", "requests\npython-dateutil\n")
    write(
        tmp_path,
        "main.py",
        "import requests as r\nr.get('x')\nimport dateutil.parser as dp\ndp.parse('x')\nr = object()\nr.get('y')\ndef f():\n import requests as q\n q.get('z')\n",
    )
    capsule = scan_repository(tmp_path, {"dateutil": "python-dateutil"})
    refs = [u for u in capsule.usages if u.kind == "reference"]
    assert [u.symbol for u in refs] == ["requests.get", "dateutil.parser.parse"]
    assert refs[1].mapping == "explicit"
    assert any(u.alias == "q" and u.kind == "import" for u in capsule.usages)


def test_repeated_alias_imports_keep_correct_order(tmp_path):
    write(tmp_path, "requirements.txt", "requests\nhttpx\n")
    write(
        tmp_path,
        "main.py",
        "import requests as client\nclient.get('a')\nimport httpx as client\nclient.get('b')\n",
    )
    refs = [u.symbol for u in scan_repository(tmp_path).usages if u.kind == "reference"]
    assert refs == ["requests.get", "httpx.get"]


def test_relative_and_star_imports_not_fabricated(tmp_path):
    write(tmp_path, "requirements.txt", "requests\n")
    write(tmp_path, "main.py", "from .requests import get\nfrom requests import *\nget('x')\n")
    capsule = scan_repository(tmp_path)
    assert capsule.usages == []
    assert any("star import" in item for item in capsule.limitations)


def test_capsule_export_roundtrip_no_overwrite(tmp_path):
    capsule = scan_repository(tmp_path)
    target = tmp_path / "capsule.json"
    write_capsule(capsule, target)
    assert ExitCapsule.model_validate_json(target.read_text()).verification.status == "not_run"
    with pytest.raises(FileExistsError):
        write_capsule(capsule, target)
    assert "No risks detected" in capsule_markdown(capsule)


def test_cli_json_and_export_preflight(tmp_path):
    write(tmp_path, "requirements.txt", "demo==1\n")
    result = CliRunner().invoke(app, ["scan", str(tmp_path), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["dependencies"][0]["package"] == "demo"
    assert "GemForge dependency facts" in result.stderr
    target = tmp_path / "keep.md"
    target.write_text("keep")
    new = tmp_path / "new.json"
    result = CliRunner().invoke(
        app, ["scan", str(tmp_path), "--output", str(new), "--markdown", str(target)]
    )
    assert result.exit_code == 2
    assert target.read_text() == "keep"
    assert not new.exists()
    assert CliRunner().invoke(app, ["scan", str(tmp_path), "--import-map", "broken"]).exit_code == 2


def test_api_scan_and_invalid_path(tmp_path):
    client = TestClient(api)
    assert client.get("/health").json()["phase"] == "3"
    response = client.post("/scan", json={"path": str(tmp_path)})
    assert response.status_code == 200
    assert response.json()["verification"]["status"] == "not_run"
    assert client.post("/scan", json={"path": str(tmp_path / "missing")}).status_code == 400
    assert client.post("/scan", json={"path": str(tmp_path), "execute": True}).status_code == 422


def test_gemma_config_requires_explicit_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMFORGE_MODEL", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMFORGE_MODEL_ID", raising=False)
    with pytest.raises(ValueError, match="Set GEMINI_API_KEY"):
        GemmaConfig.from_environment(env_file=Path(".dist/nonexistent-env-file"))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-only")
    monkeypatch.setenv("GEMFORGE_MODEL_ID", "gemini-proprietary")
    with pytest.raises(ValueError, match="Gemma"):
        GemmaConfig.from_environment()
    monkeypatch.setenv("GEMFORGE_MODEL_ID", "gemma-4-explicit-test-id")
    config = GemmaConfig.from_environment()
    assert "test-key-only" not in repr(config)
    # This tests configuration only, not model availability or a real API call.


def test_invalid_mapping(tmp_path):
    with pytest.raises(ValueError, match="undeclared"):
        scan_repository(tmp_path, {"x": "absent"})


def test_oversized_files_reported(tmp_path):
    write(tmp_path, "requirements.txt", "x" * 2_000_001)
    capsule = scan_repository(tmp_path)
    assert not capsule.dependencies
    assert any("exceeds" in item for item in capsule.limitations)


def test_ignored_target_is_separate_but_explicitly_scannable(tmp_path):
    write(tmp_path, "requirements.txt", "shared==1\n")
    write(tmp_path, ".git/history-marker", "development history")
    target = tmp_path / ".dist" / "target"
    write(target, "requirements.txt", "shared==2\n")
    write(target, ".git/history-marker", "target history")
    write(target, "main.py", "raise RuntimeError('target must never execute')\n")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    development_scan = scan_repository(tmp_path)
    target_scan = scan_repository(target)
    assert [d.constraint for d in development_scan.dependencies] == ["==1"]
    assert [d.constraint for d in target_scan.dependencies] == ["==2"]
    assert development_scan.risks == target_scan.risks == []
    assert development_scan.verification.status == target_scan.verification.status == "not_run"
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_star_import_invalidates_unknown_aliases(tmp_path):
    write(tmp_path, "requirements.txt", "requests\n")
    write(
        tmp_path,
        "main.py",
        "import requests as r\nr.get('before')\nfrom unknown import *\n"
        "r.get('uncertain')\nimport requests as r\nr.get('after')\n",
    )
    refs = [u for u in scan_repository(tmp_path).usages if u.kind == "reference"]
    assert [u.source.line for u in refs] == [2, 6]


def test_function_local_rebinding_does_not_erase_module_alias(tmp_path):
    write(tmp_path, "requirements.txt", "requests\n")
    write(
        tmp_path, "main.py", "import requests as r\ndef local():\n r = object()\nr.get('outside')\n"
    )
    refs = [u.symbol for u in scan_repository(tmp_path).usages if u.kind == "reference"]
    assert refs == ["requests.get"]


def test_same_line_imports_keep_distinct_alias_bindings(tmp_path):
    write(tmp_path, "requirements.txt", "requests\nhttpx\n")
    write(
        tmp_path,
        "main.py",
        "import requests as c; c.get('a'); import httpx as c; c.get('b')\n",
    )
    refs = [u.symbol for u in scan_repository(tmp_path).usages if u.kind == "reference"]
    assert sorted(refs) == ["httpx.get", "requests.get"]


def test_definition_default_can_rebind_module_alias(tmp_path):
    write(tmp_path, "requirements.txt", "requests\n")
    write(
        tmp_path,
        "main.py",
        "import requests as r\ndef local(value=(r := object())):\n pass\nr.get('uncertain')\n",
    )
    assert not [u for u in scan_repository(tmp_path).usages if u.kind == "reference"]
