import argparse
import ast
import dataclasses
import inspect
import os
import sys
import textwrap
import types
import warnings
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Literal, Union, get_args, get_origin

import docstring_parser
import yaml

PARSE_FUNCS = {}
ARGS = {}
USED_ARGS = {}
PATTERN = None
DEBUG = False
HELP_WIDTH = 60


# A dataclass field with a default_factory shows this singleton as its __init__
# default; capture it via public API (rather than importing a private name) so it
# can be filtered out before serialization. See dump_args.
@dataclasses.dataclass
class _FactoryProbe:
    x: list = dataclasses.field(default_factory=list)


_DEFAULT_FACTORY_SENTINEL = (
    inspect.signature(_FactoryProbe.__init__).parameters["x"].default
)


@contextmanager
def scope(parsed_args, pattern=""):
    """
    Context manager to put parsed arguments into
    a state.
    """
    parsed_args = parsed_args.copy()
    remove_keys = []
    matched = {}

    global ARGS
    global PATTERN

    old_args = ARGS
    old_pattern = PATTERN

    for key in parsed_args:
        if "/" in key:
            if key.split("/")[0] == pattern:
                matched[key.split("/")[-1]] = parsed_args[key]
            remove_keys.append(key)

    parsed_args.update(matched)
    for key in remove_keys:
        parsed_args.pop(key)
    ARGS = parsed_args
    PATTERN = pattern
    yield

    ARGS = old_args
    PATTERN = old_pattern


def _format_func_debug(func_name, func_kwargs, scope=None):
    formatted = [f"{func_name}("]
    if scope is not None:
        formatted.append(f"  # scope = {scope}")
    for key, val in func_kwargs.items():
        formatted.append(f"  {key} : {type(val).__name__} = {val}")
    formatted.append(")")
    return "\n".join(formatted)


def bind(
    *args, without_prefix=False, positional=False, group: Union[list, str] = "default"
):
    """Binds a functions arguments so that it looks up argument
    values in a dictionary scoped by ArgBind.

    Parameters
    ----------
    args : List[str] or [fn or Object] + List[str], optional
        List of patterns to bind the function under. If the first item
        in the list is a function or Object, then the function is bound
        here (e.g. decorate is called on the first argument). Otherwise,
        it is treated is a decorator.
    without_prefix : bool, optional
        Whether or not to bind without the function name as the prefix.
        If True, the functions arguments will be available at "arg_name"
        rather than "func_name.arg_name", by default False
    positional : bool, optional
        Arguments that are not keyword arguments are not bound by default. If
        this is True, then the arguments will be bound as positional arguments
        in some order, by default False
    group : list or str, optional
        Group or list of groups to assign this function to. ``build_parser``
        and ``parse_args`` can then build a parser for only a subset of bound
        functions by group, by default "default".
    """

    if args and not isinstance(args[0], str):
        bound_fn_or_cls = args[0]
        patterns = args[1:] if len(args) > 1 else []
    else:
        bound_fn_or_cls = None
        patterns = args

    if positional and patterns:
        warnings.warn(
            f"Combining positional arguments with scoping patterns is not allowed. Removing scoping patterns {patterns}. \n"
            "See https://github.com/pseeth/argbind/tree/main/examples/hello_world#argbind-with-positional-arguments"
        )
        patterns = []

    if isinstance(group, str):
        group = [group]

    def decorator(object_or_func):
        func = object_or_func
        prefix = func.__qualname__  # get prefix before a potential monkey patch below changes it to a superclass's prefix
        is_class = inspect.isclass(func)
        if is_class:
            # If the class has no __init__ method, find the __init__ method from the closest superclass
            # that defines one. Then monkey patch that __init__ onto the class.
            if "__init__" not in func.__dict__:
                for base in func.__mro__[1:]:
                    if "__init__" in base.__dict__:
                        func.__init__ = base.__init__  # monkey patch
                        break
            func = getattr(func, "__init__")

        if "__init__" in prefix:
            prefix = prefix.split(".")[0]

        # Check if function is bound already. If it is, just re-wrap it,
        # instead of wrapping the function twice.
        if prefix in PARSE_FUNCS:
            func = PARSE_FUNCS[prefix][0]
        else:
            PARSE_FUNCS[prefix] = (func, patterns, without_prefix, positional, group)

        @wraps(func)
        def cmd_func(*args, **kwargs):
            parameters = list(inspect.signature(func).parameters.items())

            cmd_kwargs = {}
            pos_kwargs = {parameters[i][0]: arg for i, arg in enumerate(args)}

            for key, param in parameters:
                arg_val = param.default
                if arg_val is not inspect.Parameter.empty or positional:
                    arg_name = f"{prefix}.{key}" if not without_prefix else f"{key}"
                    if arg_name in ARGS and key not in kwargs:
                        val = ARGS[arg_name]
                        if key in pos_kwargs:
                            val = pos_kwargs[key]
                        # Cast value to the expected type (important for YAML-loaded values)
                        val = _cast_value(val, param.annotation)
                        cmd_kwargs[key] = val
                        use_key = arg_name
                        if PATTERN:
                            use_key = f"{PATTERN}/{use_key}"
                        USED_ARGS[use_key] = val

            kwargs.update(cmd_kwargs)
            cmd_args = []
            for i, arg in enumerate(args):
                key = parameters[i][0]
                if key not in kwargs:
                    cmd_args.append(arg)

            # Ensure dictionary order is in parameter order
            kwargs = {k: kwargs[k] for k, _ in parameters if k in kwargs}

            if "args.debug" not in ARGS:
                ARGS["args.debug"] = False
            if ARGS["args.debug"] or DEBUG:
                if PATTERN:
                    scope = PATTERN
                else:
                    scope = None
                print(_format_func_debug(prefix, kwargs, scope))
            return func(*cmd_args, **kwargs)

        if is_class:
            setattr(object_or_func, "__init__", cmd_func)
            cmd_func = object_or_func

        return cmd_func

    if bound_fn_or_cls is None:
        return decorator
    else:
        return decorator(bound_fn_or_cls)


class bind_module:
    def __init__(self, module, *scopes, filter_fn=lambda fn: True, **kwargs):
        """Binds every function/class in a specified module. The output
        class is a bound version of the original module, with the
        attributes in the same place.

        Parameters
        ----------
        module : ModuleType
            Module or object whose attributes to bind.
        scopes : List[str] or [fn or Object] + List[str], optional
            List of patterns to bind the function under.
        filter_fn : Callable, optional
            A function that takes in the function that is to be bound, and
            returns a boolean whether it should be bound.
            Defaults to always True, no matter what the function is.
        kwargs : keyword arguments, optional
            Keyword arguments to the bind function.

        """
        for fn_name in dir(module):
            fn = getattr(module, fn_name)
            if not isinstance(fn, type(sys)) and hasattr(fn, "__qualname__"):
                if filter_fn(fn):
                    bound_fn = bind(fn, *scopes, **kwargs)
                    setattr(self, fn_name, bound_fn)


def get_used_args():
    """
    Gets the args that have been used so far
    by the script (e.g. their function they target
    was actually called).
    """
    return USED_ARGS


def dump_args(args, output_path):
    """
    Dumps the provided arguments to a
    file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Drop the dataclasses default_factory sentinel; it is not serializable.
    filtered_args = {}
    for key, value in args.items():
        if value is not _DEFAULT_FACTORY_SENTINEL:
            filtered_args[key] = value

    with open(path, "w") as f:
        yaml.Dumper.ignore_aliases = lambda *args: True
        x = yaml.dump(filtered_args, Dumper=yaml.Dumper)
        prev_line = None
        output = []
        for line in x.split("\n"):
            cur_line = line.split(".")[0].strip()
            if not cur_line.startswith("-"):
                if cur_line != prev_line and prev_line:
                    line = f"\n{line}"
                prev_line = line.split(".")[0].strip()
            output.append(line)
        f.write("\n".join(output))


def load_args(input_path_or_stream):
    """
    Loads arguments from a given input path or file stream, if
    the file is already open.
    """
    if isinstance(input_path_or_stream, (str, Path)):
        path = Path(input_path_or_stream)
        # Resolve $include relative to THIS file's directory (not the process CWD), so a
        # config and its include tree load identically regardless of where it's invoked
        # from — including when installed read-only in site-packages.
        base_dir = path.resolve().parent
        with path.open("r") as f:
            data = yaml.load(f, Loader=yaml.Loader)
    else:
        base_dir = None
        data = yaml.load(input_path_or_stream, Loader=yaml.Loader)

    if "$include" in data:
        include_files = data.pop("$include")
        include_args = {}
        for include_file in include_files:
            # Prefer file-relative resolution (CWD-independent). Fall back to the legacy
            # CWD-relative path if the file-relative one doesn't exist, so configs that
            # still write includes relative to the run directory keep working.
            if base_dir is not None and not Path(include_file).is_absolute():
                file_relative = base_dir / include_file
                if file_relative.exists():
                    include_file = file_relative
            include_args.update(load_args(include_file))
        include_args.update(data)
        data = include_args

    _vars = os.environ.copy()
    if "$vars" in data:
        _vars.update(data.pop("$vars"))

    for key, val in data.items():
        # Check if string starts with $.
        if isinstance(val, str):
            if val.startswith("$"):
                lookup = val[1:]
                if lookup in _vars:
                    data[key] = _vars[lookup]

        elif isinstance(val, list):
            new_list = []
            for subval in val:
                if isinstance(subval, str) and subval.startswith("$"):
                    lookup = subval[1:]
                    if lookup in _vars:
                        new_list.append(_vars[lookup])
                    else:
                        new_list.append(subval)
                else:
                    new_list.append(subval)
            data[key] = new_list

    if "args.debug" not in data:
        data["args.debug"] = DEBUG
    return data


class str_to_list:
    def __init__(self, _type):
        self._type = _type

    def __call__(self, values):
        _values = values.split(" ")
        _values = [self._type(v) for v in _values]
        return _values


class str_to_tuple:
    def __init__(self, _type_list):
        self._type_list = _type_list

    def __call__(self, values):
        _values = values.split(" ")
        if len(self._type_list) == 2 and self._type_list[1] is Ellipsis:
            # Variable-length tuple[X, ...]: every element has the same type
            return tuple(self._type_list[0](v) for v in _values)
        _values = [self._type_list[i](v) for i, v in enumerate(_values)]
        return tuple(_values)


class str_to_dict:
    def __init__(self):
        pass

    def _guess_type(self, s):
        try:
            value = ast.literal_eval(s)
        except ValueError:
            return s
        else:
            return value

    def __call__(self, values):
        values = values.split(" ")
        _values = {}

        for elem in values:
            key, val = elem.split("=", 1)
            key = self._guess_type(key)
            val = self._guess_type(val)
            _values[key] = val

        return _values


class str_to_bool:
    def __init__(self):
        pass

    def __call__(self, value):
        """Convert string or int to bool.

        Accepts: 0, 1, 'true', 'false', 'True', 'False'
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if value.lower() in ("true", "1"):
            return True
        if value.lower() in ("false", "0"):
            return False
        raise ValueError(f"Cannot convert {value} to bool")


# PEP 604 unions (X | None) have origin types.UnionType rather than
# typing.Union on Python 3.10-3.13 (the two are unified in 3.14).
_UNION_ORIGINS = tuple({Union, getattr(types, "UnionType", Union)})


def _unwrap_optional(arg_type):
    """Unwrap Optional[X] or X | None to X, return None if not Optional.

    Args:
        arg_type: Type annotation to check

    Returns:
        The inner type if arg_type is Optional[X] / X | None, otherwise None
    """
    origin = get_origin(arg_type)
    if origin in _UNION_ORIGINS:
        args = get_args(arg_type)
        # Check if this is Optional[X] (i.e., Union[X, None])
        if len(args) == 2 and type(None) in args:
            # Return the non-None type
            return args[0] if args[1] is type(None) else args[1]
    return None


def _unwrap_literal(arg_type):
    """Unwrap Literal[v1, v2, ...] to its allowed values, return None if not Literal.

    Args:
        arg_type: Type annotation to check

    Returns:
        Tuple of allowed values if arg_type is Literal[...], otherwise None
    """
    if get_origin(arg_type) is Literal:
        return get_args(arg_type)
    return None


def _cast_value(value, target_type):
    """Cast a value to the target type if needed.

    This is used when loading values from YAML files to ensure they match
    the expected type from function signatures.

    Args:
        value: The value to cast
        target_type: The target type annotation

    Returns:
        The value cast to the target type, or the original value if already correct type
    """
    # If target_type is not specified, return as-is
    if target_type is inspect.Parameter.empty:
        return value

    # Unwrap Optional[X] to X if needed
    unwrapped = _unwrap_optional(target_type)
    if unwrapped is not None:
        target_type = unwrapped

    # Handle None values
    if value is None:
        return value

    # Handle Literal[v1, v2, ...] — cast to the type of the first allowed value
    literal_values = _unwrap_literal(target_type)
    if literal_values is not None:
        val_type = type(literal_values[0])
        try:
            value = val_type(value)
        except (ValueError, TypeError):
            pass
        if value not in literal_values:
            raise ValueError(
                f"invalid value {value!r} - must be one of {list(literal_values)}"
            )
        return value

    # Fast path: return the value as-is if it is already the right type. Skip
    # generic aliases like List[int], which are not valid second arguments to
    # isinstance() (``isinstance(target_type, type)`` is False for them).
    if isinstance(target_type, type) and isinstance(value, target_type):
        return value

    # Try to cast to the target type
    try:
        # For bool, use str_to_bool converter to handle string inputs correctly
        if target_type is bool:
            converter = str_to_bool()
            return converter(value)
        # For other basic types (int, float, str), use the type directly
        elif target_type in (int, float, str):
            return target_type(value)
        # For other types (including generics), return as-is and let Python handle it
        return value
    except (ValueError, TypeError):
        # If casting fails, return the original value
        return value


def build_parser(group: Union[list, str] = "default"):
    """Builds the argument parser from all the bound functions.

    Returns
    -------
    ArgumentParser
        Argument parser built by ArgBind.
    """
    p = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument(
        "--args.save",
        type=str,
        required=False,
        help="Path to save all arguments used to run script to.",
    )
    p.add_argument(
        "--args.load",
        type=str,
        required=False,
        help="Path to load arguments from, stored as a .yml file.",
    )
    p.add_argument(
        "--args.debug",
        type=int,
        required=False,
        default=0,
        help="Print arguments as they are passed to each function.",
    )

    if isinstance(group, str):
        group = [group]
    if "default" not in group:
        group.append("default")
    # Add kwargs from function to parser
    for prefix in PARSE_FUNCS:
        func, patterns, without_prefix, positional, fn_group = PARSE_FUNCS[prefix]
        if not set(fn_group) & set(group):
            continue

        # Resolve string annotations produced by ``from __future__ import
        # annotations`` (PEP 563). ``eval_str=True`` (Python 3.10+) evaluates them
        # in the function's own namespace; if that's unsupported (3.9) or a name
        # can't be resolved at runtime (e.g. a ``TYPE_CHECKING``-only import), fall
        # back to the raw, possibly stringized annotations and handle the leftover
        # strings per-parameter below.
        try:
            sig = inspect.signature(func, eval_str=True)
        except Exception:
            sig = inspect.signature(func)

        docstring = docstring_parser.parse(func.__doc__)
        parameter_help = docstring.params
        parameter_help = {x.arg_name: x.description for x in parameter_help}

        f = p.add_argument_group(
            title=f"Generated arguments for function {prefix}",
        )

        def _get_arg_names(key, is_kwarg):
            arg_names = []

            prepend = "--" if is_kwarg else ""
            if without_prefix:
                arg_name = prepend + f"PATTERN/{key}"
            else:
                arg_name = prepend + f"PATTERN/{prefix}.{key}"

            arg_names.append(arg_name.replace("PATTERN/", ""))

            if patterns is not None:
                for p in patterns:
                    arg_names.append(arg_name.replace("PATTERN", p))
            return arg_names

        for key, val in sig.parameters.items():
            arg_val = val.default
            arg_type = val.annotation
            is_kwarg = arg_val is not inspect.Parameter.empty

            if arg_type is inspect.Parameter.empty and is_kwarg:
                arg_type = type(arg_val)
            elif isinstance(arg_type, str) and is_kwarg and arg_val is not None:
                # An unresolved PEP 563 annotation (the eval_str fallback above
                # kept it as a string): infer the type from the default value.
                arg_type = type(arg_val)

            if is_kwarg or positional:
                arg_names = _get_arg_names(key, is_kwarg)
                arg_help = {}
                help_text = ""
                if key in parameter_help:
                    # A documented parameter may have no description text (None).
                    help_text = textwrap.fill(
                        parameter_help[key] or "", width=HELP_WIDTH
                    )
                arg_help[arg_names[0]] = help_text
                if len(arg_names) > 1:
                    for pattern_arg_name in arg_names[1:]:
                        arg_help[pattern_arg_name] = argparse.SUPPRESS

                for arg_name in arg_names:
                    inner_types = [str, int, float, bool]

                    # Unwrap Optional[X] / X | None to X
                    unwrapped_type = _unwrap_optional(arg_type)
                    is_optional = unwrapped_type is not None
                    effective_type = unwrapped_type if is_optional else arg_type
                    # Origin of generic aliases: list for list[X]/List[X],
                    # dict for dict[K, V]/Dict[K, V], etc. None for plain types.
                    origin = get_origin(effective_type)

                    if isinstance(effective_type, str):
                        # An unresolved PEP 563 annotation with no informative
                        # default to infer from: no CLI converter can be built, so
                        # leave it YAML-configurable only rather than crashing
                        # build_parser (matches the unsupported-union behavior).
                        continue

                    if effective_type is bool:
                        # For bool with a default, support both flag and value syntax:
                        # --Example.on      -> True (uses const)
                        # --Example.on=1    -> True (uses type converter)
                        # --Example.on=0    -> False (uses type converter)
                        # (nothing)         -> default value
                        if is_optional or arg_val is not inspect.Parameter.empty:
                            f.add_argument(
                                arg_name,
                                type=str_to_bool(),
                                nargs="?",
                                const=True,
                                default=arg_val,
                                help=arg_help[arg_name],
                            )
                        else:
                            # For bool without a default, use store_true action
                            f.add_argument(
                                arg_name, action="store_true", help=arg_help[arg_name]
                            )
                    elif effective_type is list or origin is list:
                        # Covers list, List, list[X], and List[X]. Bare
                        # list defaults to str elements.
                        type_args = get_args(effective_type)
                        _type = type_args[0] if type_args else str
                        if _type in inner_types:
                            f.add_argument(
                                arg_name,
                                type=str_to_list(_type),
                                default=arg_val,
                                help=arg_help[arg_name],
                            )
                        # Lists of other element types cannot be parsed from
                        # the command line; they stay configurable via YAML.
                    elif effective_type is dict or origin is dict:
                        # Covers dict, Dict, dict[K, V], and Dict[K, V].
                        # Value types are guessed with ast.literal_eval.
                        f.add_argument(
                            arg_name,
                            type=str_to_dict(),
                            default=arg_val,
                            help=arg_help[arg_name],
                        )
                    elif _unwrap_literal(effective_type) is not None:
                        literal_values = _unwrap_literal(effective_type)
                        val_type = type(literal_values[0])
                        f.add_argument(
                            arg_name,
                            type=val_type,
                            choices=literal_values,
                            default=arg_val,
                            help=arg_help[arg_name],
                        )
                    elif origin is tuple:
                        _type_list = get_args(effective_type)
                        f.add_argument(
                            arg_name,
                            type=str_to_tuple(_type_list),
                            default=arg_val,
                            help=arg_help[arg_name],
                        )
                    elif origin in _UNION_ORIGINS:
                        # Union of several real types, e.g.
                        # str | os.PathLike | None. A command-line value is
                        # already a str, so if str is a member, pass it
                        # through unchanged. Unions without str cannot be
                        # parsed from the command line and stay configurable
                        # via YAML.
                        if str in get_args(effective_type):
                            f.add_argument(
                                arg_name,
                                type=str,
                                default=arg_val,
                                help=arg_help[arg_name],
                            )
                    elif origin is not None:
                        # Other generics (Mapping[K, V], custom generics,
                        # ...) cannot be parsed from the command line; they
                        # stay configurable via YAML.
                        pass
                    elif callable(effective_type):
                        # A plain, callable type (int, float, str, or a custom
                        # converter): argparse calls it on the raw string value.
                        f.add_argument(
                            arg_name,
                            type=effective_type,
                            default=arg_val,
                            help=arg_help[arg_name],
                        )
                    else:
                        # Not a recognized generic and not callable: the
                        # annotation is not a usable type (e.g. `x: None` or a
                        # non-type value), so no argument can be built for it.
                        raise RuntimeError(
                            f"argbind cannot bind {prefix}.{key}: its annotation "
                            f"{effective_type!r} is not a callable type or a "
                            f"supported generic."
                        )

        desc = docstring.short_description
        if desc is None:
            desc = ""

        if patterns:
            # Use the last parameter as the example; fall back to a placeholder
            # for a parameter-less function (sig.parameters is empty).
            param_keys = list(sig.parameters)
            example_key = param_keys[-1] if param_keys else "arg"
            if not without_prefix:
                scope_pattern = f"--{patterns[0]}/{prefix}.{example_key}"
            else:
                scope_pattern = f"--{patterns[0]}/{example_key}"

            desc += (
                f" Additional scope patterns: {', '.join(list(patterns))}. "
                "Use these by prefacing any of the args below with one "
                "of these patterns. For example: "
                f"{scope_pattern} VALUE."
            )

        desc = textwrap.fill(desc, width=HELP_WIDTH)
        f.description = desc

    return p


def parse_args(p=None, group: Union[list, str] = "default"):
    """
    Parses the command line and returns a dictionary.
    Builds the argument parser if p is None.
    """
    p = build_parser(group=group) if p is None else p
    used_args = [
        x.replace("--", "").split("=")[0] for x in sys.argv if x.startswith("--")
    ]
    used_args.extend(["args.save", "args.load"])

    known, unknown = p.parse_known_args()
    args = vars(known)
    args["args.unknown"] = unknown
    load_args_path = args.pop("args.load")
    save_args_path = args.pop("args.save")
    debug_args = args.pop("args.debug")

    pattern_keys = [key for key in args if "/" in key]
    top_level_args = [key for key in args if "/" not in key]

    # If the top-level arguments were altered but the scoped ones were not,
    # change the scoped ones to match the top-level (inherit from top-level).
    args |= {
        key: args[key.split("/")[1]] for key in pattern_keys if key not in used_args
    }

    if load_args_path:
        loaded_args = load_args(load_args_path)
        # Overwrite defaults with loaded arguments, except those from the command line.
        args |= {k: v for k, v in loaded_args.items() if k not in used_args}
        for key in pattern_keys:
            pattern, arg_name = key.split("/")
            if key not in loaded_args and key not in used_args:
                if arg_name in loaded_args:
                    args[key] = args[arg_name]

    for key in top_level_args:
        if key in used_args:
            for pattern_key in pattern_keys:
                pattern, arg_name = pattern_key.split("/")
                if key == arg_name and pattern_key not in used_args:
                    args[pattern_key] = args[key]

    if save_args_path:
        dump_args(args, save_args_path)

    # Put them back in case the script wants to use them
    args["args.load"] = load_args_path
    args["args.save"] = save_args_path
    args["args.debug"] = debug_args

    return args
