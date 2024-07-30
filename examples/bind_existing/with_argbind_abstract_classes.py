import abc
from typing import Any, Dict

import argbind


class Base(abc.ABC):
  
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config

    @abc.abstractmethod
    def action(self):
        """Do something"""


@argbind.bind()
class Sub1(Base):

    def action(self):
        print('hello', self.config)


@argbind.bind()
class Sub2(Base):

    def action(self):
        print('goodbye', self.config)


if __name__ == "__main__":

    argbind.parse_args() # add for help text, though it isn't used here.

    args = {
      'Sub1.config': {"a": "apple", "b": "banana"},
      'Sub2.config': {"c": "cherry", "d": "durian"},
    }

    with argbind.scope(args):
        Sub1().action() # prints "hello {'a': 'apple', 'b': 'banana'}"
        Sub2().action() # prints "goodbye {'c': 'cherry', 'd': 'durian'}"
