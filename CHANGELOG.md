# Changelog
## v0.5.2
First release as an extended fork of [pseeth/argbind](https://github.com/pseeth/argbind),
published to PyPI as **`argbind-dbraun`** (`pip install argbind-dbraun`). The import name is
unchanged — still `import argbind` — so it is a drop-in replacement for existing code and
`.yml` configs.

- **Breaking:** the long-deprecated `bind_to_parser` alias (kept for `argbind<=0.1.3`) is removed;
  use `argbind.bind` instead.
- Ships a `py.typed` marker (PEP 561), so downstream type checkers pick up its annotations.
- Removed the PyTorch-based `mnist` and `bind_module` examples; `bind_module` is now covered by a
  torch-free unit test, and the test suite no longer requires `torch`.
- Internal: `load_args` / `dump_args` use `pathlib` instead of `os.path` (no behavior change).

## v0.5.1
- **`$include` is resolved relative to the including file**, not the process CWD. A config and its
  `$include` tree now load identically regardless of where they are invoked from — including from a
  read-only `site-packages` install. Includes are written relative to the file that lists them
  (e.g. a file in `conf/` uses `$include: [base.yml, mixins/x.yml]`; one in `conf/ablations/` uses
  `$include: [../base.yml]`). For backward compatibility, if the file-relative path does not exist,
  it falls back to the previous CWD-relative resolution, so configs that still write includes
  relative to the run directory keep working.

## v0.5.0
- **Modern type annotation support** (PEP 585 / PEP 604), matching what
  `pyupgrade --py310-plus` rewrites `typing` aliases into:
  - `X | None` is now unwrapped like `Optional[X]` everywhere (CLI parsing and
    YAML type casting). Previously it reached argparse as a `type=` callable and
    crashed `build_parser()` with `ValueError: ... is not callable`.
  - `list[X]` and `List[X]` are now both dispatched via `typing.get_origin`, so
    builtin generics get the same space-separated CLI parsing. Previously
    `list[X]` silently generated no CLI flag at all.
  - `dict`, `dict[K, V]`, and `Dict[K, V]` all get `key=value` CLI parsing.
    Previously only bare `typing.Dict` did; the others were silently CLI-less
    (subscripted `Dict[K, V]`) or broken (`type=dict`).
  - `tuple[X, ...]` (and `Tuple[X, ...]`) variadic tuples now parse each
    element with `X` instead of raising `IndexError` past the first element.
  - Unions of several real types that include `str` (e.g.
    `str | os.PathLike | None`) accept the raw command-line string, since a
    CLI value is already a valid `str` member. Unions without `str` generate
    no CLI flag and stay configurable via YAML, matching the old
    `Union[X, Y]` behavior, instead of crashing the parser.
- Added `tests/test_modern_annotations.py` covering all of the above plus a
  regression guard that the legacy `typing` spellings behave unchanged.

## v0.4.0
- **Major enhancement**: Boolean arguments with defaults now support flexible syntax!
  - Use flag-style: `--func.arg` sets to `True`
  - Use value-style: `--func.arg=0/1/true/false/True/False` to set to any boolean value
  - Both syntaxes work from command line and `.yml` files
  - Removes the previous limitation where booleans set to `True` in `.yml` files couldn't be overridden from command line
  - Boolean arguments **without defaults** still use flag-only syntax for backwards compatibility
- Added `Optional[bool]` type support with `str_to_bool` converter class
- Added comprehensive tests for boolean flexibility
- Updated all documentation to reflect new boolean behavior

## v0.3.3
- Allow `argbind.load_args` to take in an already open filestream.

## v0.3.2
- Better way of binding classes.
- Using `__qualname__` instead of `__name__` to identify functions more reliably.
- Classes are bound by replacing their `__init__` function with an argbound version.
- Binding `__init__` functions uses as the prefix the name of the class, rather than `__init__`.

## v0.2.0
- Fixed a bug in resolving variables in lists, introduced in v0.1.8.

## v0.1.9
- Positional arguments can now be bound with `positional=True`. ArgBind should now be able to build programs
  with identical APIs to ArgParse, with less code and added support for .yaml files!

## v0.1.8
- Environment variables can now be referenced within YAML files. All variables that are in `os.environ` are used to resolve any values that start with `$` in a YAML file.
- Variables now resolve not only for strings but also within lists of strings.

## v0.1.7
- Updated the behavior of `args.debug` to create a prettier and more readable
  output.

## v0.1.6
- Added `without_prefix` option to `bind`, which exposes the keyword arguments
  without the function name as the prefix, if `without_prefix=True`. There was
  an unused version of this in its place called `no_global` which has now been
  removed.

## v0.1.5
- Using `functools.wraps` in the `bind` decorator. This decorates the
  function without changing its name.

## v0.1.4
- `bind_to_parser` renamed to `bind`. `bind_to_parser` still exists
  to maintain backwards compatibility.

## v0.1.3
- Stable release.

## v0.1.2
- Removing unused functionality.

## v0.1.1
- Fixing some minor bugs.

## v0.1.0
- Initial release.
