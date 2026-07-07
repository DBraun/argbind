import types

import pytest

import argbind


def test_load_args():
    arg1 = argbind.load_args("examples/yaml/conf/base.yml")
    with open("examples/yaml/conf/base.yml") as f:
        arg2 = argbind.load_args(f)
    assert arg1 == arg2


def greet(name, greeting="Hello"):
    """Module-level helper used to exercise bind_module (torch-free)."""
    return f"{greeting}, {name}!"


def test_bind_module():
    """bind_module binds a module's functions so their keyword arguments are
    configurable through the argbind scope, keyed by ``<function>.<kwarg>``."""
    module = types.ModuleType("greetings")
    module.greet = greet

    bound = argbind.bind_module(module)

    # A keyword argument supplied via the scope overrides the default.
    with argbind.scope({"greet.greeting": "Hi"}):
        assert bound.greet("Ada") == "Hi, Ada!"

    # With nothing in scope, the function's own default is used.
    with argbind.scope({}):
        assert bound.greet("Ada") == "Hello, Ada!"


@argbind.bind()
def configure(a: int = 1):
    """Module-level helper for the unknown-kwarg tests."""
    return a


@argbind.bind()
class Widget:
    """Module-level helper class for the unknown-kwarg tests."""

    def __init__(self, size: int = 1):
        self.size = size


@argbind.bind()
def collect(a: int = 1, **kwargs):
    """Module-level helper for the **kwargs passthrough test."""
    return a, kwargs


def test_unknown_kwarg_raises_type_error():
    """A keyword argument that is not in the bound function's signature raises
    the function's natural TypeError instead of being silently dropped."""
    assert configure(a=2) == 2
    with pytest.raises(TypeError, match="bogus"):
        configure(a=2, bogus=3)


def test_unknown_kwarg_raises_type_error_for_bound_class():
    assert Widget(size=2).size == 2
    with pytest.raises(TypeError, match="frobnicate"):
        Widget(size=2, frobnicate=True)


def test_extra_kwargs_reach_var_keyword():
    """A bound function that declares **kwargs receives non-parameter keyword
    arguments (previously they were stripped before the call)."""
    assert collect(a=2, extra=3) == (2, {"extra": 3})

    # Scope-bound values and passthrough extras compose.
    with argbind.scope({"collect.a": 5}):
        assert collect(extra=3) == (5, {"extra": 3})
