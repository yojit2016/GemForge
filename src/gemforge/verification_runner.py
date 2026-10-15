"""Trusted fixed checks, copied outside the target and run by its isolated Python.

This script uses stdlib only except the explicitly installed pytest runner.
No shell commands or source text from AI are evaluated.
"""

import ast
import importlib
import inspect
import json
import sys
from pathlib import Path


def main():
    action, root_text, output_text = sys.argv[1:4]
    root, output = Path(root_text), Path(output_text)
    if action == "syntax":
        files = list(root.rglob("*.py"))
        for path in files:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path.relative_to(root)))
        print(json.dumps({"files_parsed": len(files)}))
        return 0
    if action == "pytest":
        import pytest

        sys.path.insert(0, str(root))
        tests = (
            [str(root / "tests")]
            if (root / "tests").is_dir()
            else [str(p) for p in root.rglob("test_*.py")]
        )
        if not tests:
            print("No supported pytest test files discovered")
            return 5
        return pytest.main(
            [
                "-q",
                "-p",
                "no:cacheprovider",
                "-c",
                str(output.parent / "pytest.ini"),
                "--rootdir",
                str(root),
                "--basetemp",
                str(output.parent / "test-tmp"),
                "--junitxml",
                str(output),
                *tests,
            ]
        )
    sys.path.insert(0, str(root))
    if action == "import":
        module = importlib.import_module(sys.argv[4])
        print(json.dumps({"imported": module.__name__}))
        return 0
    if action == "probes":
        results = []
        for probe in json.loads(Path(sys.argv[4]).read_text(encoding="utf-8")):
            result = {"name": probe["name"], "status": "failed"}
            try:
                module = importlib.import_module(probe["module"])
                cls = getattr(module, probe["class_name"])
                if not inspect.isclass(cls):
                    raise TypeError("Probe target must be a class")
                expected_error = probe.get("expected_exception")
                exception_class = None
                if expected_error:
                    module_name, _, name = expected_error.rpartition(".")
                    exception_class = getattr(importlib.import_module(module_name), name)
                    if not inspect.isclass(exception_class) or not issubclass(
                        exception_class, Exception
                    ):
                        raise TypeError("Expected exception must identify an Exception class")
                try:
                    instance = cls(**probe["kwargs"])
                except Exception as error:
                    result["actual_exception"] = type(error).__name__
                    if exception_class and isinstance(error, exception_class):
                        result["status"] = "passed"
                else:
                    actual = {
                        name: getattr(instance, name) for name in probe["expected_attributes"]
                    }
                    result["actual"] = actual
                    if not expected_error and actual == probe["expected_attributes"]:
                        result["status"] = "passed"
            except Exception as error:
                result["error_type"] = type(error).__name__
                result["message"] = str(error)[:1000]
            results.append(result)
        output.write_text(json.dumps(results, default=str), encoding="utf-8")
        print(json.dumps(results, default=str))
        return 0 if all(r["status"] == "passed" for r in results) else 1
    raise ValueError("Unsupported fixed check")


if __name__ == "__main__":
    raise SystemExit(main())
