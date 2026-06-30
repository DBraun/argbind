import argbind


@argbind.bind()
def func(
    maybe_count: int | None = None,
    tags: list[str] | None = None,
    weights: dict[str, float] | None = None,
    shape: tuple[int, int] = (1, 2),
):
    """Bind arguments annotated with modern (PEP 585 / PEP 604) syntax.

    ``list[str]``, ``dict[str, float]`` and ``tuple[int, int]`` are the builtin
    generics of PEP 585, and ``int | None`` is a PEP 604 union -- all are parsed
    the same way as their ``typing`` equivalents (``Optional``, ``List``, etc.).

    Parameters
    ----------
    maybe_count : int | None, optional
        An optional integer (PEP 604 union), by default None.
    tags : list[str] | None, optional
        A list of strings, space-separated on the CLI, by default None.
    weights : dict[str, float] | None, optional
        A ``key=value`` mapping, by default None.
    shape : tuple[int, int], optional
        A fixed-size tuple, by default (1, 2).
    """
    print(f"count={maybe_count!r} tags={tags!r} weights={weights!r} shape={shape!r}")


if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        func()
