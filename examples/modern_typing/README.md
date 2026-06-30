# Modern type annotations (PEP 585 / PEP 604)

ArgBind understands the builtin generics of
[PEP 585](https://peps.python.org/pep-0585/) (`list[str]`, `dict[str, float]`,
`tuple[int, int]`) and the union syntax of
[PEP 604](https://peps.python.org/pep-0604/) (`int | None`), parsing them exactly
like their older `typing` equivalents (`Optional`, `List`, `Dict`, `Tuple`). See
the [typing example](../typing) for the same arguments written the old way.

```
❯ python examples/modern_typing/with_argbind.py --func.tags "x y z" --func.weights "lr=0.5"
count=None tags=['x', 'y', 'z'] weights={'lr': 0.5} shape=(1, 2)
```
