"""Tests for modern type annotations on bound functions.

Covers PEP 585 builtin generics (list[int], dict[str, int], tuple[int, ...])
and PEP 604 unions (X | None). These are the forms that pyupgrade
--py310-plus rewrites typing.List/typing.Optional into, so bound signatures
in downstream code bases use them extensively.
"""

import os
import subprocess
import sys
import tempfile

import pytest

PYTHON = sys.executable

requires_pep604 = pytest.mark.skipif(
    sys.version_info < (3, 10), reason="X | Y annotations require Python 3.10"
)


def run_script(source, args, cwd):
    script_path = os.path.join(cwd, "script.py")
    with open(script_path, "w") as f:
        f.write(source)
    return subprocess.run(
        [PYTHON, script_path] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
    )


def check_cases(source, test_cases):
    with tempfile.TemporaryDirectory() as tmpdir:
        for case in test_cases:
            result = run_script(source, case["args"], tmpdir)
            # Normalize CRLF so multi-line comparisons are robust on Windows.
            output = result.stdout.decode("utf-8").replace("\r\n", "\n").strip()
            assert output == case["expected"], (
                f"Case '{case['name']}' failed:\n"
                f"  Args: {case['args']}\n"
                f"  Expected: {case['expected']}\n"
                f"  Got: {output}\n"
                f"  Stderr: {result.stderr.decode('utf-8')}"
            )


@requires_pep604
def test_pep604_optional_primitives():
    """X | None unwraps to X for argparse, same as Optional[X]."""
    source = """
import argbind

@argbind.bind()
def func(
    a: str | None = None,
    b: int | None = None,
    c: float | None = None,
):
    print(f"a={a!r},b={b!r},c={c!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {
                "name": "defaults",
                "args": [],
                "expected": "a=None,b=None,c=None",
            },
            {
                "name": "cli_overrides_are_typed",
                "args": ["--func.a=hello", "--func.b=5", "--func.c=0.5"],
                "expected": "a='hello',b=5,c=0.5",
            },
        ],
    )


@requires_pep604
def test_pep604_optional_bool():
    """bool | None keeps the flexible flag/value boolean syntax."""
    source = """
import argbind

@argbind.bind()
def func(flag: bool | None = None):
    print(f"flag={flag!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {"name": "default", "args": [], "expected": "flag=None"},
            {"name": "flag_style", "args": ["--func.flag"], "expected": "flag=True"},
            {"name": "value_true", "args": ["--func.flag=1"], "expected": "flag=True"},
            {
                "name": "value_false",
                "args": ["--func.flag=0"],
                "expected": "flag=False",
            },
        ],
    )


def test_pep585_lists():
    """list[X] gets the same space-separated CLI parsing as List[X]."""
    source = """
import argbind

@argbind.bind()
def func(
    ints: list[int] = None,
    strs: list[str] = None,
    floats: list[float] = None,
):
    print(f"ints={ints!r},strs={strs!r},floats={floats!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {
                "name": "defaults_stay_none",
                "args": [],
                "expected": "ints=None,strs=None,floats=None",
            },
            {
                "name": "cli_overrides_are_typed",
                "args": [
                    "--func.ints",
                    "1 2 3",
                    "--func.strs",
                    "a b",
                    "--func.floats",
                    "0.5 1.5",
                ],
                "expected": "ints=[1, 2, 3],strs=['a', 'b'],floats=[0.5, 1.5]",
            },
        ],
    )


def test_pep585_dicts():
    """Bare dict and dict[K, V] both get key=value CLI parsing."""
    source = """
import argbind

@argbind.bind()
def func(plain: dict = None, typed: dict[str, int] = None):
    print(f"plain={plain!r},typed={typed!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {
                "name": "defaults_stay_none",
                "args": [],
                "expected": "plain=None,typed=None",
            },
            {
                "name": "cli_overrides",
                "args": ["--func.plain", "x=5 y=a", "--func.typed", "a=1 b=2"],
                "expected": "plain={'x': 5, 'y': 'a'},typed={'a': 1, 'b': 2}",
            },
        ],
    )


def test_pep585_tuples():
    """tuple[X, Y] parses per-position; tuple[X, ...] is variable-length."""
    source = """
import argbind

@argbind.bind()
def func(
    fixed: tuple[int, float, str] = None,
    variadic: tuple[int, ...] = (1, 5, 10),
):
    print(f"fixed={fixed!r},variadic={variadic!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {
                "name": "defaults",
                "args": [],
                "expected": "fixed=None,variadic=(1, 5, 10)",
            },
            {
                "name": "cli_overrides",
                "args": ["--func.fixed", "1 2.5 abc", "--func.variadic", "2 4 8 16"],
                "expected": "fixed=(1, 2.5, 'abc'),variadic=(2, 4, 8, 16)",
            },
        ],
    )


@requires_pep604
def test_pep604_optional_containers():
    """list[X] | None and dict[K, V] | None unwrap to the container parsing."""
    source = """
import argbind

@argbind.bind()
def func(
    ints: list[int] | None = None,
    cfg: dict[str, float] | None = None,
):
    print(f"ints={ints!r},cfg={cfg!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {"name": "defaults", "args": [], "expected": "ints=None,cfg=None"},
            {
                "name": "cli_overrides",
                "args": ["--func.ints", "4 5", "--func.cfg", "lr=1e-3"],
                "expected": "ints=[4, 5],cfg={'lr': 0.001}",
            },
        ],
    )


@requires_pep604
def test_pep604_class_binding():
    """Bound classes with modern annotations in __init__ work end to end."""
    source = """
import argbind

@argbind.bind()
class Model:
    def __init__(self, tags: list[str] | None = None, dim: int | None = None):
        print(f"tags={tags!r},dim={dim!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        Model()
"""
    check_cases(
        source,
        [
            {"name": "defaults", "args": [], "expected": "tags=None,dim=None"},
            {
                "name": "cli_overrides",
                "args": ["--Model.tags", "a b c", "--Model.dim=8"],
                "expected": "tags=['a', 'b', 'c'],dim=8",
            },
        ],
    )


@requires_pep604
def test_pep604_union_with_str_member():
    """Unions containing str accept the raw command-line string.

    A CLI value is already a str, so for unions like str | os.PathLike | None
    the string passes through unchanged. This also applies to the legacy
    spelling Optional[Union[str, Path]].
    """
    source = """
import os
from pathlib import Path
from typing import Optional, Union
import argbind

@argbind.bind()
def func(
    source: str | os.PathLike | None = None,
    legacy: Optional[Union[str, Path]] = None,
):
    print(f"source={source!r},legacy={legacy!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {
                "name": "defaults",
                "args": [],
                "expected": "source=None,legacy=None",
            },
            {
                "name": "cli_strings_pass_through",
                "args": ["--func.source=/tmp/audio.wav", "--func.legacy=conf/base.yml"],
                "expected": "source='/tmp/audio.wav',legacy='conf/base.yml'",
            },
        ],
    )


@requires_pep604
def test_pep604_unsupported_union_is_yaml_only():
    """A union of several real types without str must not crash build_parser.

    Such parameters cannot be parsed from the command line (which converter
    would apply?), so no CLI flag is generated and they stay configurable
    via YAML, matching the old behavior of typing.Union[X, Y].
    """
    source = """
from pathlib import Path
import argbind

@argbind.bind()
def func(p: int | Path = 1, q: int = 1):
    print(f"p={p!r},q={q!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # The big one: parser construction must not raise.
        result = run_script(source, [], tmpdir)
        assert result.returncode == 0, result.stderr.decode("utf-8")
        assert result.stdout.decode("utf-8").strip() == "p=1,q=1"

        # No CLI flag for the union parameter, but the others are present.
        result = run_script(source, ["-h"], tmpdir)
        help_text = result.stdout.decode("utf-8")
        assert "--func.q" in help_text
        assert "--func.p" not in help_text

        # YAML can still configure it.
        yaml_path = os.path.join(tmpdir, "conf.yml")
        with open(yaml_path, "w") as f:
            f.write("func.p: 42\n")
        result = run_script(source, [f"--args.load={yaml_path}"], tmpdir)
        assert result.stdout.decode("utf-8").strip() == "p=42,q=1"


@requires_pep604
def test_pep604_yaml_type_casting():
    """YAML values are cast through X | None just like Optional[X]."""
    source = """
import argbind

@argbind.bind()
def func(b: int | None = None, c: float | None = None):
    print(f"b={b!r},c={c!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "conf.yml")
        with open(yaml_path, "w") as f:
            f.write('func.b: "42"\nfunc.c: 1e-4\n')
        result = run_script(source, [f"--args.load={yaml_path}"], tmpdir)
        output = result.stdout.decode("utf-8").strip()
        assert output == "b=42,c=0.0001", (
            f"Got: {output}\nStderr: {result.stderr.decode('utf-8')}"
        )


@requires_pep604
def test_pep604_scoped():
    """Modern annotations work with scope patterns."""
    source = """
import argbind

@argbind.bind('train', 'val')
def create_dataset(batch_size: int | None = None, sources: list[str] = None):
    print(f"batch_size={batch_size!r},sources={sources!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args, 'train'):
        create_dataset()
    with argbind.scope(args, 'val'):
        create_dataset()
"""
    check_cases(
        source,
        [
            {
                "name": "scoped_overrides",
                "args": [
                    "--train/create_dataset.batch_size=32",
                    "--val/create_dataset.batch_size=8",
                    "--create_dataset.sources",
                    "a b",
                ],
                "expected": (
                    "batch_size=32,sources=['a', 'b']\nbatch_size=8,sources=['a', 'b']"
                ),
            },
        ],
    )


def test_legacy_typing_unchanged():
    """The old typing-module spellings keep working exactly as before."""
    source = """
from typing import Dict, List, Optional, Tuple
import argbind

@argbind.bind()
def func(
    ints: List[int] = None,
    d: Dict = None,
    s: Optional[str] = None,
    t: Tuple[int, str] = None,
):
    print(f"ints={ints!r},d={d!r},s={s!r},t={t!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {
                "name": "defaults",
                "args": [],
                "expected": "ints=None,d=None,s=None,t=None",
            },
            {
                "name": "cli_overrides",
                "args": [
                    "--func.ints",
                    "1 2",
                    "--func.d",
                    "k=v",
                    "--func.s=hello",
                    "--func.t",
                    "3 x",
                ],
                "expected": "ints=[1, 2],d={'k': 'v'},s='hello',t=(3, 'x')",
            },
        ],
    )


def test_pep563_future_annotations():
    """`from __future__ import annotations` (PEP 563) stringizes annotations.

    build_parser must still derive CLI converters from them instead of crashing
    with "'bool' is not callable". This mirrors binding a class whose module uses
    future annotations (e.g. audiotree's SaliencyParams).
    """
    source = """
from __future__ import annotations
import argbind

@argbind.bind()
def func(
    enabled: bool = True,
    num_tries: int = 8,
    loudness_cutoff: float = -40.0,
    name: str = "uniform",
):
    print(
        f"enabled={enabled!r},num_tries={num_tries!r},"
        f"loudness_cutoff={loudness_cutoff!r},name={name!r}"
    )

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    check_cases(
        source,
        [
            {
                "name": "defaults",
                "args": [],
                "expected": "enabled=True,num_tries=8,loudness_cutoff=-40.0,name='uniform'",
            },
            {
                "name": "cli_overrides_are_typed",
                "args": [
                    "--func.enabled=0",
                    "--func.num_tries=3",
                    "--func.loudness_cutoff=-12.5",
                    "--func.name=bias",
                ],
                "expected": "enabled=False,num_tries=3,loudness_cutoff=-12.5,name='bias'",
            },
        ],
    )


@requires_pep604
def test_pep563_containers_and_class():
    """Under PEP 563, eval_str resolves list[X] / X | None and class __init__ hints."""
    source = """
from __future__ import annotations
import argbind

@argbind.bind()
class Model:
    def __init__(self, tags: list[str] = None, dim: int | None = None):
        print(f"tags={tags!r},dim={dim!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        Model()
"""
    check_cases(
        source,
        [
            {"name": "defaults", "args": [], "expected": "tags=None,dim=None"},
            {
                "name": "cli_overrides",
                "args": ["--Model.tags", "a b c", "--Model.dim=8"],
                "expected": "tags=['a', 'b', 'c'],dim=8",
            },
        ],
    )


def test_pep563_unresolvable_annotation_is_yaml_only():
    """A PEP 563 annotation that can't be evaluated at runtime (e.g. a
    TYPE_CHECKING-only name) must not crash build_parser: the parameter is left
    YAML-only while the resolvable ones still get CLI flags.
    """
    source = """
from __future__ import annotations
from typing import TYPE_CHECKING
import argbind

if TYPE_CHECKING:
    from pathlib import Path  # deliberately not imported at runtime

@argbind.bind()
def func(p: Path = None, q: int = 1):
    print(f"p={p!r},q={q!r}")

if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # The key guarantee: parser construction must not raise.
        result = run_script(source, [], tmpdir)
        assert result.returncode == 0, result.stderr.decode("utf-8")
        assert result.stdout.decode("utf-8").strip() == "p=None,q=1"

        # The resolvable param gets a CLI flag; the unresolvable one does not.
        result = run_script(source, ["-h"], tmpdir)
        help_text = result.stdout.decode("utf-8")
        assert "--func.q" in help_text
        assert "--func.p" not in help_text
