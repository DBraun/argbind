# Literal arguments

`Literal` annotations restrict an argument to a fixed set of values. ArgBind turns
them into argparse `choices`, so invalid values are rejected both on the command
line and when loaded from a `.yml` file. `Literal` works with `str`, `int`, and
`float` values, and composes with `Optional`.

```
❯ python examples/literal/with_argbind.py --configure.mode val --configure.level 3
mode='val' level=3 backend=None

❯ python examples/literal/with_argbind.py --configure.mode bogus
error: argument --configure.mode: invalid choice: 'bogus' (choose from 'train', 'val', 'test')
```
