"""Entry point for python -m currency_converter."""


def main() -> None:
    from currency_converter.gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
