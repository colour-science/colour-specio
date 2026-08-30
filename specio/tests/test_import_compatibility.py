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
from typing import TYPE_CHECKING

import specio

if TYPE_CHECKING:
    from collections.abc import Iterator

PACKAGE_ROOT = pathlib.Path(specio.__file__).parent
FUTURE_IMPORT = "from __future__ import annotations"
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _modules_without_future_import() -> Iterator[tuple[pathlib.Path, ast.Module]]:
    """Every module that has not deferred its annotations."""
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        source = path.read_text()
        if FUTURE_IMPORT not in source:
            yield path.relative_to(PACKAGE_ROOT), ast.parse(source)


def _is_type_checking(node: ast.AST) -> bool:
    """An `if TYPE_CHECKING:` guard, imported plainly or by module."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _annotations_of(node: ast.AST) -> Iterator[ast.expr]:
    """Every annotation written anywhere inside `node`."""
    for child in ast.walk(node):
        if isinstance(child, FUNCTION_NODES):
            if child.returns is not None:
                yield child.returns
            args = child.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                if arg.annotation is not None:
                    yield arg.annotation
        elif isinstance(child, ast.AnnAssign) and child.annotation is not None:
            yield child.annotation


def _names_in(annotation: ast.expr) -> set[str]:
    return {n.id for n in ast.walk(annotation) if isinstance(n, ast.Name)}


def _self_referential_classes(tree: ast.Module) -> Iterator[str]:
    """Classes annotating their own name, which is unbound until the
    class body finishes."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            node.name in _names_in(annotation) for annotation in _annotations_of(node)
        ):
            yield node.name


def test_type_checking_imports_are_deferred() -> None:
    """A TYPE_CHECKING import is not bound at runtime, so annotations
    naming it need deferred evaluation."""
    offenders = [
        str(path)
        for path, tree in _modules_without_future_import()
        if any(_is_type_checking(node) for node in ast.walk(tree))
    ]

    assert not offenders, (
        f"these modules import under TYPE_CHECKING without `{FUTURE_IMPORT}`, "
        "so any annotation naming those imports raises NameError below "
        "Python 3.14: " + ", ".join(offenders)
    )


def test_self_referential_annotations_are_deferred() -> None:
    """A class is not bound until its body finishes, so an annotation
    inside it naming the class needs deferring or quoting."""
    offenders = [
        f"{path}:{name}"
        for path, tree in _modules_without_future_import()
        for name in _self_referential_classes(tree)
    ]

    assert not offenders, (
        f"these classes annotate their own name without `{FUTURE_IMPORT}` "
        "or quotes, which raises NameError at class creation below "
        "Python 3.14: " + ", ".join(offenders)
    )
