# Using default_factory with Lists

This example demonstrates using `field(default_factory=...)` from dataclasses with ArgBind for List-type arguments.

## Example

```python
from dataclasses import dataclass, field
from typing import List
import argbind

@argbind.bind()
@dataclass
class Example:
    my_list: List[int] = field(default_factory=lambda: [1, 2, 3])
```

## Usage

### Default Value

When no arguments are provided, the default factory is used:

```bash
❯ python examples/default_factory/list_example.py
Example(my_list=[1, 2, 3])
```

### Override from Command Line

Lists are passed as space-delimited strings:

```bash
❯ python examples/default_factory/list_example.py --Example.my_list "4 5 6"
Example(my_list=[4, 5, 6])

❯ python examples/default_factory/list_example.py --Example.my_list "7 8"
Example(my_list=[7, 8])
```

## Why Use default_factory?

In dataclasses, mutable default values (like lists) should use `default_factory` to avoid sharing the same list instance across all instances of the class. This is a Python best practice:

```python
# Bad - all instances share the same list!
@dataclass
class Bad:
    my_list: List[int] = [1, 2, 3]  # Don't do this!

# Good - each instance gets its own list
@dataclass
class Good:
    my_list: List[int] = field(default_factory=lambda: [1, 2, 3])
```

ArgBind works seamlessly with both patterns, but using `default_factory` is the recommended approach for mutable defaults.

## When to Use `default_factory` vs `= None`

There are two common patterns for list arguments in ArgBind:

### Pattern 1: Optional Lists (`= None`)

Use when the list is **optional** and might not be provided:

```python
@argbind.bind()
def process_files(files: List[str] = None):
    if files is None:
        print("No files to process")
    else:
        for f in files:
            print(f"Processing {f}")
```

**Use this when:**
- The list is truly optional
- You need to distinguish between "not provided" and "empty list"
- You want to check `if files is None:`

See the [typing example](../typing) for more on this pattern.

### Pattern 2: Lists with Default Values (`default_factory`)

Use when you **always want a list** with specific default contents:

```python
from dataclasses import dataclass, field

@argbind.bind()
@dataclass
class Config:
    include_dirs: List[str] = field(default_factory=lambda: ['/usr/include', '/usr/local/include'])
```

**Use this when:**
- You always want a list (never `None`)
- You want specific default values
- You're using dataclasses (required for mutable defaults)

### Comparison

| Feature | `= None` | `default_factory` |
|---------|----------|-------------------|
| Value when not provided | `None` | Default list contents |
| Can distinguish "not provided" from "empty" | ✅ Yes | ❌ No |
| Works with dataclasses safely | ⚠️ Limited | ✅ Yes |
| Can provide default items | ❌ No | ✅ Yes |
| Always returns a list | ❌ No | ✅ Yes |

**Recommendation**: Use `= None` for optional lists in regular functions, and `default_factory` for lists with default values in dataclasses.
