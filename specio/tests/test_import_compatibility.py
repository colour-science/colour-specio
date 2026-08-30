"""Every module imports on the oldest Python this package supports.

Python 3.14 evaluates annotations lazily (PEP 649), so a module whose
annotations name something unavailable at definition time -- a
TYPE_CHECKING-only import, or a class referring to itself from inside its
own body -- imports there and raises NameError on 3.12 and 3.13.
`pyproject.toml` declares support for both.

A development environment on 3.14 cannot catch this by running, which is
how it got in: imports moved under TYPE_CHECKING and two self-referential
return annotations lost their quotes, and every module kept importing
locally while the package became unusable on the versions it claims. The
checks below are static, so they hold whatever interpreter runs them.
"""

from __future__ import annotations

import ast
import pathlib

import specio

PACKAGE_ROOT = pathlib.Path(specio.__file__).parent
FUTURE_IMPORT = "from __future__ import annotations"


def _python_files() -> list[pathlib.Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def _is_type_checking_test(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    return isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING"


def test_type_checking_imports_are_deferred() -> None:
    """A TYPE_CHECKING import is not bound at runtime, so annotations
    naming it need deferred evaluation."""
    offenders = []
    for path in _python_files():
        source = path.read_text()
        if FUTURE_IMPORT in source:
            continue
        tree = ast.parse(source)
        if any(
            isinstance(node, ast.If) and _is_type_checking_test(node.test)
            for node in ast.walk(tree)
        ):
            offenders.append(path.relative_to(PACKAGE_ROOT))

    assert not offenders, (
        "these modules import under TYPE_CHECKING without "
        f"`{FUTURE_IMPORT}`, so any annotation naming those imports raises "
        "NameError below Python 3.14: "
        + ", ".join(str(p) for p in offenders)
    )


def test_self_referential_annotations_are_deferred() -> None:
    """A class is not bound until its body finishes, so an annotation
    inside it naming the class needs deferring or quoting."""
    offenders = []
    for path in _python_files():
        source = path.read_text()
        if FUTURE_IMPORT in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.ClassDef):
                continue
            annotations = []
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    if child.returns is not None:
                        annotations.append(child.returns)
                    annotations.extend(
                        arg.annotation
                        for arg in [
                            *child.args.posonlyargs,
                            *child.args.args,
                            *child.args.kwonlyargs,
                        ]
                        if arg.annotation is not None
                    )
                elif isinstance(child, ast.AnnAssign) and child.annotation is not None:
                    annotations.append(child.annotation)
            for annotation in annotations:
                names = {
                    inner.id
                    for inner in ast.walk(annotation)
                    if isinstance(inner, ast.Name)
                }
                if node.name in names:
                    offenders.append(f"{path.relative_to(PACKAGE_ROOT)}:{node.name}")
                    break

    assert not offenders, (
        "these classes annotate their own name without "
        f"`{FUTURE_IMPORT}` or quotes, which raises NameError at class "
        "creation below Python 3.14: " + ", ".join(offenders)
    )
