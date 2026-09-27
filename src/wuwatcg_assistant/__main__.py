from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .catalog import CardCatalog
from .ui import MainWindow


def parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="鳴潮：対決 カード認識アシスタント")
    parser.add_argument("--camera", type=int, default=0, help="起動時に選択するカメラ番号")
    parser.add_argument("--width", type=int, default=1280, help="カメラ要求幅")
    parser.add_argument("--height", type=int, default=720, help="カメラ要求高さ")
    return parser.parse_args(arguments)


def main() -> int:
    options = parse_arguments()
    project_root = Path(__file__).resolve().parents[2]
    catalog = CardCatalog.load(project_root / "assets" / "cards")

    application = QApplication(sys.argv)
    application.setApplicationName("鳴潮：対決 カードアシスタント")
    window = MainWindow(
        catalog,
        camera_index=options.camera,
        camera_width=options.width,
        camera_height=options.height,
    )
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
