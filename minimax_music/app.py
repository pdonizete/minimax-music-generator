"""App wx principal: cria a janela e roda o event loop."""

from __future__ import annotations

import sys

import wx

from . import i18n
from .config import resolve_settings
from .main_window import MainWindow


def run() -> int:
    app = wx.App()
    settings = resolve_settings()
    frame = MainWindow(settings)
    frame.Show()
    app.SetTopWindow(frame)
    return app.MainLoop()


if __name__ == "__main__":
    sys.exit(run())
