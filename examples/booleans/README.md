# Flexible Boolean Syntax

ArgBind supports flexible syntax for boolean arguments with defaults. You can use either flag-style or value-style syntax, making it easy to set booleans to any value from both the command line and `.yml` files.

## Example

The example uses a dataclass with boolean fields:

```python
from dataclasses import dataclass
import argbind

@argbind.bind()
@dataclass
class Example:
    on: bool = True
    off: bool = False
```

## Usage

### Flag-Style Syntax

Use the argument as a flag to set it to `True`:

```bash
# Set 'on' to True (it's already True by default, but this shows the syntax)
❯ python examples/booleans/bool_example.py --Example.on
Example(on=True, off=False)

# Set 'off' to True
❯ python examples/booleans/bool_example.py --Example.off
Example(on=True, off=True)
```

### Value-Style Syntax

Pass explicit values using `=`:

```bash
# Set 'on' to False using 0
❯ python examples/booleans/bool_example.py --Example.on=0
Example(on=False, off=False)

# Set 'on' to True using 1
❯ python examples/booleans/bool_example.py --Example.on=1
Example(on=True, off=False)

# Use true/false (lowercase)
❯ python examples/booleans/bool_example.py --Example.on=false --Example.off=true
Example(on=False, off=True)

# Use True/False (capitalized)
❯ python examples/booleans/bool_example.py --Example.on=False --Example.off=True
Example(on=False, off=True)
```

### Mixed Syntax

You can mix flag-style and value-style in the same command:

```bash
❯ python examples/booleans/bool_example.py --Example.on --Example.off=0
Example(on=True, off=False)
```

### Default Values

When no arguments are provided, the defaults from the dataclass are used:

```bash
❯ python examples/booleans/bool_example.py
Example(on=True, off=False)
```

## Help Text

The help text shows that boolean arguments accept optional values:

```bash
❯ python examples/booleans/bool_example.py --help
usage: bool_example.py [-h] [--args.save ARGS.SAVE]
                       [--args.load ARGS.LOAD]
                       [--args.debug ARGS.DEBUG]
                       [--Example.on [EXAMPLE.ON]]
                       [--Example.off [EXAMPLE.OFF]]

Generated arguments for function Example:

  --Example.on [EXAMPLE.ON]
  --Example.off [EXAMPLE.OFF]
```

The square brackets `[EXAMPLE.ON]` indicate that the value is optional - you can use it as a flag or provide a value.

## Accepted Boolean Values

ArgBind accepts the following values for booleans:

**True values**: `1`, `true`, `True`

**False values**: `0`, `false`, `False`

## Important Notes

- This flexible syntax applies to **booleans with defaults** (e.g., `my_flag: bool = True`)
- **Always provide defaults for boolean arguments** - this is the recommended pattern in ArgBind
- Both flag-style and value-style work in `.yml` files as well
- You can now easily flip boolean values from the command line without workarounds

**Note on booleans without defaults**: Booleans without defaults (e.g., `my_flag: bool`) are only exposed to the CLI when using `@argbind.bind(positional=True)`, which makes them positional arguments. As noted in the main README, positional arguments should generally be avoided in `.yml` files, so it's best to always provide a default value for boolean arguments.

## Why This Matters

Previously, ArgBind treated booleans as flags that could only be set to `True`. If you wanted to set a boolean to `False` from the command line, you had to use workarounds like using integers instead of booleans. Now you have the flexibility to use whichever syntax is most convenient for your use case!
