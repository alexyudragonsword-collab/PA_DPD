"""padpd desktop launcher — PyInstaller entry point for the PySide6 GUI."""

import multiprocessing
import sys


def main() -> None:
    multiprocessing.freeze_support()
    from gui_qt.main import main as qt_main
    qt_main()


if __name__ == "__main__":
    sys.exit(main())
