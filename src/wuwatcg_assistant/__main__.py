from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .catalog import CardCatalog
from .ui import MainWindow


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    catalog = CardCatalog.load(project_root / "assets" / "cards")

    application = QApplication(sys.argv)
    application.setApplicationName("鳴潮：対決 カードアシスタント")
    window = MainWindow(catalog)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
