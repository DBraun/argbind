from dataclasses import dataclass, field
from typing import List
import argbind


@argbind.bind()
@dataclass
class Example:
    my_list: List[int] = field(default_factory=lambda: [1, 2, 3])


if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        ex = Example()
        print(ex)
