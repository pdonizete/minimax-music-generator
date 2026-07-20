"""Entry point FORA do pacote — usado pelo PyInstaller.

Quando o PyInstaller constroi o .exe a partir de minimax_music/__main__.py,
o __main__.py eh executado como script solto, e os imports relativos
(`from .app import run`) quebram porque o Python nao sabe o parent package.

Este arquivo importa o pacote por caminho absoluto e delega. Use-o como
entry point do PyInstaller no `build_exe.bat`.

Tambem funciona se voce rodar diretamente:
    python run_app.py
"""

import sys

from minimax_music.app import run


if __name__ == "__main__":
    sys.exit(run() or 0)
