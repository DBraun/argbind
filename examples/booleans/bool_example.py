from dataclasses import dataclass
import argbind


@argbind.bind()
@dataclass
class Example:
    on: bool = True
    off: bool = False


if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        ex = Example()
        print(ex)
