import types

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
