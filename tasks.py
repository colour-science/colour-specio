"""Invoke tasks for code quality and formatting."""

from invoke.context import Context  # noqa: TC002
from invoke.tasks import task


@task
def lint(ctx: Context, fix: bool = False, target: str = ".") -> None:
    """Run ruff linting with optional auto-fix.

    Parameters
    ----------
    ctx : Context
        Invoke context object
    fix : bool, optional
        Whether to auto-fix issues, by default False
    target : str, optional
        Directory or file glob to target, by default "."
    """
    cmd = f"ruff check {target}"
    if fix:
        cmd += " --fix"
    ctx.run(cmd)


@task
def format(ctx: Context, check: bool = False, target: str = ".") -> None:
    """Run ruff formatting with optional check-only mode.

    Parameters
    ----------
    ctx : Context
        Invoke context object
    check : bool, optional
        Whether to check formatting without applying changes, by default False
    target : str, optional
        Directory or file glob to target, by default "."
    """
    cmd = f"ruff format {target}"
    if check:
        cmd += " --check"
    ctx.run(cmd)


@task
def typecheck(ctx: Context, target: str = "") -> None:
    """Run pyright type checking.

    Parameters
    ----------
    ctx : Context
        Invoke context object
    target : str, optional
        Directory or file glob to target, by default "" (whole project)
    """
    cmd = "pyright"
    if target:
        cmd += f" {target}"
    ctx.run(cmd)


@task
def spellcheck(ctx: Context, target: str = "") -> None:
    """Run spell checking using cspell.

    Checks for spelling errors in Python and documentation files.
    Provides helpful installation and configuration guidance if needed.

    Parameters
    ----------
    ctx : Context
        Invoke context object
    target : str, optional
        Directory or file glob to target, by default "" (uses default patterns)
    """
    import shutil

    print("📝 Running spell check...")

    # Check if npx is available
    if not shutil.which("npx"):
        print("❌ npx not found!")
        print("📦 Please install Node.js to get npx:")
        print("   • macOS: brew install node")
        print("   • Other: https://nodejs.org/")
        return

    # Determine what to check
    if target:
        cspell_pattern = f'"{target}"'
    else:
        cspell_pattern = (
            '"specio/**/*" "tests/**/*" "examples/**/*" "scripts/**/*" "*.md"'
        )

    # Try to run cspell, handle if not installed
    try:
        result = ctx.run(
            f"npx cspell {cspell_pattern} --no-progress",
            warn=True,
        )

        if result and result.ok:
            print("✅ No spelling errors found!")
        else:
            print("⚠️  Spelling errors detected!")
            print("🔧 To fix these issues:")
            print("   1. Correct any genuine spelling mistakes")
            print("   2. Add legitimate technical terms to cspell.json")
            print("   3. Technical terms should go in the 'words' array")
            print("📖 Edit cspell.json to add new technical vocabulary")

    except Exception as e:
        if "command not found" in str(e).lower() or "not found" in str(e).lower():
            print("📦 cspell not found. For faster execution, install globally:")
            print("   npm install -g cspell")
            print("🔄 Trying to install and run cspell temporarily...")
            try:
                ctx.run(
                    f"npx cspell {cspell_pattern} --no-progress",
                    warn=True,
                )
            except Exception:
                print(
                    "❌ Failed to run cspell. Please check your Node.js installation."
                )
        else:
            print(f"❌ Error running cspell: {e}")


@task
def check(ctx: Context) -> None:
    """Run all code quality checks (lint, format check, typecheck, spellcheck).

    Parameters
    ----------
    ctx : Context
        Invoke context object
    """
    print("🔍 Running linting...")
    lint(ctx, fix=False)

    print("📐 Checking formatting...")
    format(ctx, check=True)

    print("🔬 Type checking...")
    typecheck(ctx)

    print("📖 Spell checking...")
    spellcheck(ctx)

    print("✅ All checks completed!")


@task
def check_fix(ctx: Context) -> None:
    """Auto-fix linting issues and format code.

    Parameters
    ----------
    ctx : Context
        Invoke context object
    """
    print("🔧 Fixing linting issues...")
    lint(ctx, fix=True)

    print("📝 Formatting code...")
    format(ctx, check=False)

    print("✅ All fixes applied!")


@task
def ai_quality(ctx: Context, target: str = ".") -> None:
    """Run comprehensive quality checks for AI agents.

    AI Agents should use this task for quality checking.
    After running this task, AI agents will need to refresh
    their context as these commands can change files safely.

    Parameters
    ----------
    ctx : Context
        Invoke context object
    target : str, optional
        Directory or file glob to target, by default "."
    """
    print("📝 Formatting code...")
    format(ctx, check=False, target=target)

    print("🔧 Fixing linting issues...")
    lint(ctx, fix=True, target=target)

    print("🔬 Type checking...")
    typecheck(ctx, target=target if target != "." else "")

    print("📖 Spell checking...")
    spellcheck(ctx, target=target)


@task
def clean(ctx: Context) -> None:
    """Clean up build artifacts and cache files.

    Parameters
    ----------
    ctx : Context
        Invoke context object
    """
    ctx.run("find . -type d -name '__pycache__' -exec rm -rf {} +", warn=True)
    ctx.run("find . -type f -name '*.pyc' -delete", warn=True)
    ctx.run("rm -rf .pytest_cache", warn=True)
    ctx.run("rm -rf .ruff_cache", warn=True)
    print("🧹 Cleaned up cache files!")


@task
def build_proto(ctx: Context) -> None:
    """Build Protocol Buffer files from .proto definitions.

    Generates *_pb2.py and *_pb2.pyi files in specio/serialization/protobuf/
    Requires protoc v27.0+

    Parameters
    ----------
    ctx : Context
        Invoke context object
    """
    import glob

    print("🔨 Building Protocol Buffer files...")

    # Find all .proto files in the specio directory
    proto_files = glob.glob("specio/**/*.proto", recursive=True)

    if not proto_files:
        print("❌ No .proto files found in specio/ directory")
        return

    print(f"📋 Found {len(proto_files)} .proto file(s): {', '.join(proto_files)}")

    # Build the protoc command with explicit file paths
    proto_files_str = " ".join(proto_files)
    ctx.run(f"protoc --python_out=. --pyi_out=. {proto_files_str}")
    print("✅ Protocol Buffer files built successfully!")


@task
def test(ctx: Context) -> None:
    """Run tests.

    Parameters
    ----------
    ctx : Context
        Invoke context object
    """
    ctx.run("pytest")
