"""Static import and simple module-level alias references, without imports."""

import ast
from pathlib import Path

from .files import read_text
from .schemas import Dependency, SourceLocation, UsageLocation


def map_usages(
    root: Path,
    files: list[Path],
    dependencies: list[Dependency],
    limitations: list[str],
    import_map: dict[str, str] | None = None,
) -> list[UsageLocation]:
    packages = {d.package for d in dependencies}
    mapping = {package.replace("-", "_"): (package, "name_heuristic") for package in packages}
    for module, package in (import_map or {}).items():
        if package not in packages:
            raise ValueError(f"Import mapping {module} targets undeclared dependency {package}")
        if not module.isidentifier():
            raise ValueError(f"Import map keys must be top-level module identifiers: {module}")
        mapping[module] = (package, "explicit")
    limitations.append(
        "Import-to-distribution matching uses normalized-name heuristics unless explicitly mapped; "
        "mismatched names (e.g. python-dateutil/dateutil) need --import-map. "
        "Dynamic imports, star imports, relative imports, alias reassignment, conditional bindings, "
        "local module shadowing and nested-scope references are not resolved. "
        "Imports are syntax evidence, not executed usage."
    )
    usages = []
    for path in files:
        if path.suffix != ".py":
            continue
        source = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(read_text(path), filename=source)
        except (SyntaxError, ValueError, UnicodeError, OSError, RecursionError) as error:
            limitations.append(f"{source}: AST analysis skipped: {error}")
            continue
        aliases: dict[tuple[ast.AST, str], tuple[str, str, str, str]] = {}
        # Record every absolute import, including those inside functions.
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [
                    (item.name, item.name, item.asname or item.name.split(".")[0])
                    for item in node.names
                ]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported = [
                    (node.module, f"{node.module}.{item.name}", item.asname or item.name)
                    for item in node.names
                    if item.name != "*"
                ]
                if any(item.name == "*" for item in node.names):
                    limitations.append(
                        f"{source}:{node.lineno}: star import cannot be mapped to references"
                    )
            else:
                continue
            for module, symbol, alias in imported:
                target = mapping.get(module.split(".")[0])
                if target is None:
                    continue
                package, method = target
                usages.append(
                    UsageLocation(
                        package=package,
                        module=module,
                        symbol=symbol,
                        alias=alias,
                        kind="import",
                        mapping=method,
                        source=SourceLocation(file=source, line=node.lineno),
                    )
                )
                if node in tree.body:
                    bound_symbol = (
                        symbol
                        if not isinstance(node, ast.Import)
                        or any(item.asname == alias for item in node.names)
                        else alias
                    )
                    aliases[(node, alias)] = (package, module, bound_symbol, method)
        # Avoid claims about lexical scope: only straight-line module statements
        # following their imports are resolved. Any rebinding invalidates the alias.
        active: dict[str, tuple[str, str, str, str]] = {}
        for statement in tree.body:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                if any(item.name == "*" for item in statement.names):
                    # Unknown exports can overwrite any earlier module binding.
                    active.clear()
                    continue
                for item in statement.names:
                    alias = item.asname or (
                        item.name.split(".")[0] if isinstance(statement, ast.Import) else item.name
                    )
                    active.pop(alias, None)
                    if (statement, alias) in aliases:
                        active[alias] = aliases[(statement, alias)]
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                active.pop(statement.name, None)
                # Defaults/decorators/bases run in the enclosing namespace, unlike
                # a function body. A walrus there can invalidate an outer alias.
                expressions = list(statement.decorator_list)
                if isinstance(statement, ast.ClassDef):
                    expressions.extend(statement.bases)
                    expressions.extend(item.value for item in statement.keywords)
                else:
                    expressions.extend(statement.args.defaults)
                    expressions.extend(item for item in statement.args.kw_defaults if item)
                    expressions.extend(
                        arg.annotation
                        for arg in ast.walk(statement.args)
                        if isinstance(arg, ast.arg) and arg.annotation
                    )
                    if statement.returns:
                        expressions.append(statement.returns)
                for expression in expressions:
                    for node in ast.walk(expression):
                        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                            active.pop(node.id, None)
                # Local stores belong to another namespace; explicit global
                # mutations are conservatively treated as unresolved instead.
                for node in ast.walk(statement):
                    if isinstance(node, ast.Global):
                        for name in node.names:
                            active.pop(name, None)
                continue
            for node in ast.walk(statement):
                if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                    active.pop(node.id, None)
            if isinstance(
                statement,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.Try,
                    ast.TryStar,
                    ast.With,
                    ast.AsyncWith,
                    ast.Match,
                ),
            ):
                # Conditional bindings or imports can change the module namespace.
                active.clear()
                continue
            parents = {
                child: node for node in ast.walk(statement) for child in ast.iter_child_nodes(node)
            }
            for node in ast.walk(statement):
                if (
                    not isinstance(node, ast.Name)
                    or not isinstance(node.ctx, ast.Load)
                    or node.id not in active
                ):
                    continue
                # Lambdas/comprehensions have their own binding and evaluation rules.
                parent = parents.get(node)
                ancestors = []
                while parent:
                    ancestors.append(parent)
                    parent = parents.get(parent)
                if any(
                    isinstance(
                        p, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
                    )
                    for p in ancestors
                ):
                    continue
                package, module, symbol, method = active[node.id]
                current = node
                while (
                    isinstance(parents.get(current), ast.Attribute)
                    and parents[current].value is current
                ):
                    current = parents[current]
                    symbol += "." + current.attr
                usages.append(
                    UsageLocation(
                        package=package,
                        module=module,
                        symbol=symbol,
                        alias=node.id,
                        kind="reference",
                        mapping=method,
                        source=SourceLocation(file=source, line=node.lineno),
                    )
                )
    return sorted(
        usages, key=lambda u: (u.source.file, u.source.line or 0, u.package, u.kind, u.symbol)
    )
