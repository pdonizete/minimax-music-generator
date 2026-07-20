"""Entry point: `python -m minimax_music`.

NUNCA rode `__main__.py` diretamente — os imports relativos vão falhar.
Sempre use `python -m minimax_music` (de dentro da raiz do projeto).
"""

import sys


def main() -> int:
    # Verifica se está rodando como módulo (e não como script solto)
    if __name__ != "__main__":
        return 0
    if not __package__:
        sys.stderr.write(
            "ERRO: este arquivo NAO deve ser executado diretamente.\n"
            "Use:  python -m minimax_music\n"
            "(de dentro da raiz do projeto, com o venv ativo).\n"
        )
        return 1
    from .app import run
    return run() or 0


if __name__ == "__main__":
    raise SystemExit(main())
