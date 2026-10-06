"""Run Metawarc with ``python -m metawarc``."""

import logging

from .core import cli


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO if verbose else logging.WARNING,
    )


if __name__ == "__main__":
    import sys

    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    _configure_logging(verbose)
    cli(prog_name="metawarc")
