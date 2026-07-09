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


@argbind.bind()
class Gadget:
    """Module-level helper class for the inheritance double-wrap tests."""

    def __init__(self, x: int = 1, **kwargs):
        self.x = x
        self.kwargs = kwargs


@argbind.bind()
class SubGadget(Gadget):
    """Bound subclass with no __init__ of its own: bind monkey-patches
    Gadget's already-wrapped __init__ onto it and wraps it a second time."""


@argbind.bind()
class StrictGadget:
    """Module-level helper class without **kwargs for the double-wrap tests."""

    def __init__(self, y: int = 1):
        self.y = y


@argbind.bind()
class StrictSubGadget(StrictGadget):
    """Bound subclass of a bound class that does not accept **kwargs."""


def test_extra_kwargs_flow_through_inherited_double_wrap():
    """Extra keyword arguments pass through both wrappers of an inherited,
    doubly-wrapped __init__ and land in the real **kwargs."""
    gadget = SubGadget(x=2, extra="hi")
    assert gadget.x == 2
    assert gadget.kwargs == {"extra": "hi"}

    # Scope-bound values and passthrough extras compose across both wrappers.
    with argbind.scope({"SubGadget.x": 9}):
        gadget = SubGadget(extra=1)
        assert gadget.x == 9
        assert gadget.kwargs == {"extra": 1}


def test_unknown_kwarg_raises_type_error_through_inherited_double_wrap():
    """An unknown keyword argument raises the natural TypeError even when the
    bound class inherits an already-wrapped __init__ from a bound parent."""
    assert StrictSubGadget(y=2).y == 2
    with pytest.raises(TypeError, match="nope"):
        StrictSubGadget(y=2, nope=3)
