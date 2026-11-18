"""Entry point for python -m currency_converter."""

import logging
import sys


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    from currency_converter.gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
