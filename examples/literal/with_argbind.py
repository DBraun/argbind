from typing import Literal, Optional

import argbind


@argbind.bind()
def configure(
    mode: Literal["train", "val", "test"] = "train",
    level: Literal[1, 2, 3] = 1,
    backend: Optional[Literal["cpu", "gpu"]] = None,
):
    """Configure a run using Literal-restricted arguments.

    ``Literal`` arguments become argparse ``choices``: invalid values are
    rejected both on the command line and when loaded from a ``.yml`` file.

    Parameters
    ----------
    mode : Literal['train', 'val', 'test'], optional
        Which split to run, by default 'train'.
    level : Literal[1, 2, 3], optional
        An integer level, by default 1.
    backend : Optional[Literal['cpu', 'gpu']], optional
        Optional compute backend; None lets the program decide, by default None.
    """
    print(f"mode={mode!r} level={level!r} backend={backend!r}")


if __name__ == "__main__":
    args = argbind.parse_args()
    with argbind.scope(args):
        configure()
