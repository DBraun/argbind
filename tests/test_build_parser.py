"""Regression tests for build_parser edge cases that previously crashed.

Run as subprocesses so each binds into a fresh module-global parser registry.
"""

import os
import subprocess
import sys
import tempfile

PYTHON = sys.executable


def _run(tmpdir, script, args=None):
    """Write `script` to tmpdir and run it with `args`, returning the result."""
    path = os.path.join(tmpdir, "script.py")
    with open(path, "w") as f:
        f.write(script)
    return subprocess.run(
        [PYTHON, path, *(args or [])],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmpdir,
    )


def test_parameterless_function_with_scope_patterns():
    """Binding a function that takes no arguments under scope patterns must not
    crash the parser. Previously raised UnboundLocalError from a leaked loop
    variable used to build the scope-pattern help example."""
    script = """
import argbind


@argbind.bind("train", "test")
def setup():
    return 1


if __name__ == "__main__":
    argbind.parse_args()
    print("ok")
"""
    with tempfile.TemporaryDirectory() as d:
        result = _run(d, script)
    assert result.returncode == 0, result.stderr.decode("utf-8")
    assert result.stdout.decode("utf-8").strip() == "ok"


def test_documented_parameter_without_description():
    """A parameter listed in the docstring but with no description text must not
    crash help generation. Previously fed None into textwrap.fill, raising
    AttributeError: 'NoneType' object has no attribute 'expandtabs'."""
    script = '''
import argbind


@argbind.bind()
def func(x: int = 1):
    """Do a thing.

    Parameters
    ----------
    x : int
    """
    print(x)


if __name__ == "__main__":
    argbind.parse_args()
'''
    with tempfile.TemporaryDirectory() as d:
        result = _run(d, script, ["-h"])
    # argparse's -h exits 0; the point is that build_parser did not crash.
    assert result.returncode == 0, result.stderr.decode("utf-8")
    assert "--func.x" in result.stdout.decode("utf-8")


def test_unusable_annotation_raises():
    """A non-callable, non-generic annotation (e.g. `x: None`) cannot be bound to
    the command line; build_parser raises a clear RuntimeError instead of
    silently producing no flag."""
    script = """
import argbind


@argbind.bind()
def f(x: None = None):
    print(x)


if __name__ == "__main__":
    argbind.parse_args()
"""
    with tempfile.TemporaryDirectory() as d:
        result = _run(d, script)
    assert result.returncode != 0
    assert "cannot bind" in result.stderr.decode("utf-8")
