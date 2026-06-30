"""Exhaustive, torch-free tests for binding dataclasses and dataclasses.field.

These cover the field varieties argbind has to handle when a dataclass is bound:
``default_factory`` (lambda, bare ``list``, ``dict``), ``field(default=...)`` and
plain defaults, CLI overrides, type casting from YAML, scoping, save/load
round-trips, the requirement that the ``default_factory`` sentinel never leaks
into saved YAML, and the fresh-per-instantiation guarantee that
``default_factory`` provides.
"""

import os
import subprocess
import sys
import tempfile

PYTHON = sys.executable

# A dataclass exercising every field variety in one place.
SCRIPT = """
from dataclasses import dataclass, field
from typing import List

import argbind


@argbind.bind()
@dataclass
class Example:
    my_list: List[int] = field(default_factory=lambda: [1, 2, 3])
    items: list = field(default_factory=list)
    count: int = field(default=5)
    name: str = "hi"


if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        print(Example())
"""

# Instantiates the same factory-backed dataclass twice with a mutation between.
FRESH_SCRIPT = """
from dataclasses import dataclass, field

import argbind


@argbind.bind()
@dataclass
class Example:
    items: list = field(default_factory=list)


if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        a = Example()
        a.items.append("X")
        b = Example()
        print(a.items, b.items)
"""

# A scoped dataclass with a dict factory, for scoping and save/load tests.
SCOPED_SCRIPT = """
from dataclasses import dataclass, field
from typing import Dict, List

import argbind


@argbind.bind("train", "test")
@dataclass
class Cfg:
    numbers: List[int] = field(default_factory=lambda: [1, 2, 3])
    mapping: Dict[str, int] = field(default_factory=dict)
    plain: int = 5


if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args, "train"):
        print("train:", Cfg())
    with argbind.scope(args, "test"):
        print("test:", Cfg())
"""


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


def _out(result):
    """Decode stdout, normalizing line endings for cross-platform robustness."""
    assert result.returncode == 0, result.stderr.decode("utf-8")
    return result.stdout.decode("utf-8").replace("\r\n", "\n").strip()


def test_all_field_kinds_resolve_defaults():
    """A lambda factory, a bare ``list`` factory, ``field(default=...)`` and a
    plain default all resolve to their declared values."""
    with tempfile.TemporaryDirectory() as d:
        out = _out(_run(d, SCRIPT))
    assert out == "Example(my_list=[1, 2, 3], items=[], count=5, name='hi')"


def test_cli_overrides_fields():
    """A list factory, a ``field(default=...)`` and a plain field are all
    overridable from the command line."""
    with tempfile.TemporaryDirectory() as d:
        out = _out(
            _run(
                d,
                SCRIPT,
                [
                    "--Example.my_list",
                    "7 8",
                    "--Example.count",
                    "9",
                    "--Example.name",
                    "bye",
                ],
            )
        )
    assert out == "Example(my_list=[7, 8], items=[], count=9, name='bye')"


def test_default_factory_is_fresh_per_instantiation():
    """The whole point of ``default_factory``: each instance gets its own object,
    so mutating one must not affect the next. This guards the sentinel handling --
    a shared/resolved-once default would make both lists ``['X']``."""
    with tempfile.TemporaryDirectory() as d:
        out = _out(_run(d, FRESH_SCRIPT))
    assert out == "['X'] []"


def test_saved_yaml_omits_factory_sentinel():
    """``default_factory`` fields left at their default must not be written to
    YAML (the sentinel is not serializable); plain fields are written."""
    with tempfile.TemporaryDirectory() as d:
        save = os.path.join(d, "saved.yml")
        _out(_run(d, SCRIPT, ["--args.save", save]))
        with open(save) as f:
            content = f.read()
    # No sentinel leaked, in any representation.
    assert "<factory>" not in content
    assert "!!python" not in content
    assert "_HAS_DEFAULT_FACTORY" not in content
    # Factory-backed fields are omitted; plain fields are present.
    assert "my_list" not in content
    assert "items" not in content
    assert "Example.count: 5" in content
    assert "Example.name: hi" in content


def test_save_load_roundtrip_preserves_overrides_and_defaults():
    """Overrides survive a save/load cycle; untouched factory fields fall back to
    their factory defaults on load."""
    with tempfile.TemporaryDirectory() as d:
        save = os.path.join(d, "s.yml")
        _out(
            _run(
                d,
                SCOPED_SCRIPT,
                ["--Cfg.plain", "9", "--train/Cfg.numbers", "5 6", "--args.save", save],
            )
        )
        out = _out(_run(d, SCOPED_SCRIPT, ["--args.load", save]))
    assert out == (
        "train: Cfg(numbers=[5, 6], mapping={}, plain=9)\n"
        "test: Cfg(numbers=[1, 2, 3], mapping={}, plain=9)"
    )


def test_dict_factory_and_scoping():
    """A ``Dict`` factory parses ``key=value`` overrides, a scoped override applies
    only within its scope, and a top-level override applies to every scope."""
    with tempfile.TemporaryDirectory() as d:
        out = _out(
            _run(
                d,
                SCOPED_SCRIPT,
                [
                    "--train/Cfg.mapping",
                    "a=1 b=2",
                    "--test/Cfg.numbers",
                    "9 9",
                    "--Cfg.plain",
                    "42",
                ],
            )
        )
    assert out == (
        "train: Cfg(numbers=[1, 2, 3], mapping={'a': 1, 'b': 2}, plain=42)\n"
        "test: Cfg(numbers=[9, 9], mapping={}, plain=42)"
    )


def test_field_type_cast_from_yaml():
    """YAML values are cast to each field's annotated type on load (a quoted
    string to ``int``, and a YAML int to ``str``)."""
    with tempfile.TemporaryDirectory() as d:
        cfg = os.path.join(d, "cfg.yml")
        with open(cfg, "w") as f:
            f.write('Example.count: "9"\nExample.name: 123\n')
        out = _out(_run(d, SCRIPT, ["--args.load", cfg]))
    assert "count=9" in out
    assert "name='123'" in out
