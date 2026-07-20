"""Configuração do app: carrega `.env`, expõe paths e persiste preferências.

A constante `APP_NAME` define a chave usada no diretório de preferências do
usuário (em Windows: %APPDATA%\\MavisMusicGenerator).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

# python-dotenv é opcional; se faltar, lemos .env manualmente
try:
    from dotenv import dotenv_values, set_key  # type: ignore
    _HAS_DOTENV = True
except Exception:  # pragma: no cover
    _HAS_DOTENV = False

APP_NAME = "MavisMusicGenerator"
PREF_FILENAME = "config.local.json"


# ----------------------------- .env -----------------------------

def _project_root() -> Path:
    """Resolve a raiz do projeto a partir deste arquivo.

    config.py está em minimax_music/config.py, então a raiz é o pai do pacote.
    Funciona tanto em desenvolvimento quanto no executável PyInstaller
    (que extrai arquivos em sys._MEIPASS; nesse caso, caímos no fallback
    do diretório do executável).
    """
    here = Path(__file__).resolve().parent
    candidates = [here.parent]
    # Em modo frozen (PyInstaller), os arquivos .env/.env.example podem estar
    # ao lado do .exe — também aceitamos esse local.
    if getattr(os, "frozen", False):
        candidates.insert(0, Path(os.path.dirname(os.path.abspath(__file__))))
    return candidates[0]


def _manual_load_env(path: Path) -> dict[str, str]:
    """Parser muito simples de .env (KEY=VALUE, comentários com #)."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def load_env(project_root: Path | None = None) -> dict[str, str]:
    """Carrega .env (sem poluir o process env global) e retorna dict.

    Aceita tanto MINIMAX_API_KEY quanto token_minimax (legado).
    """
    root = project_root or _project_root()
    env_path = root / ".env"
    if _HAS_DOTENV and env_path.is_file():
        values = {k: (v or "") for k, v in dotenv_values(env_path).items()}
    elif env_path.is_file():
        values = _manual_load_env(env_path)
    else:
        values = {}

    # Variáveis de ambiente do processo têm precedência
    for k in ("MINIMAX_API_KEY", "MINIMAX_BASE_URL",
              "MINIMAX_MUSIC_ENDPOINT", "MINIMAX_MUSIC_MODEL",
              "MINIMAX_OUTPUT_DIR", "token_minimax"):
        v = os.environ.get(k)
        if v:
            values[k] = v

    return values


# ----------------------------- Paths -----------------------------

def user_music_dir() -> Path:
    """Diretório padrão de músicas do usuário (multi-plataforma)."""
    if os.name == "nt":
        # Windows: %USERPROFILE%\\Music, com fallback para HOME\\Music
        home = Path(os.environ.get("USERPROFILE") or Path.home())
        candidate = home / "Music"
        if not candidate.exists():
            candidate = home / "Músicas"  # PT-BR Windows
        if not candidate.exists():
            candidate = home
    else:
        candidate = Path.home() / "Music"
    return candidate


def default_output_dir() -> Path:
    """Padrão: <pasta de músicas do usuário>/minimax-music."""
    return user_music_dir() / "minimax-music"


def user_prefs_path() -> Path:
    """%APPDATA%\\MavisMusicGenerator\\config.local.json (Windows) ou ~/.config."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / APP_NAME / PREF_FILENAME


# ----------------------------- Preferências -----------------------------

# Modelos de música conhecidos pelo app. O default é `music-3.0` (Token Plan,
# RPM 120). `music-2.6` é uma alternativa mais antiga que às vezes responde
# melhor a duetos (mas com RPM menor).
KNOWN_MUSIC_MODELS = ("music-3.0", "music-2.6")
DEFAULT_MUSIC_MODEL = "music-3.0"


@dataclass
class UserPrefs:
    """Preferências persistidas do usuário."""

    output_dir: str = ""                          # vazio = usar default_output_dir()
    music_model: str = ""                         # vazio = auto (music-2.6 pra dueto, music-3.0 pra solo)
    clean_lyrics_for_duet: bool = True            # True = letra limpa; False = com prefixos

    def resolved_output_dir(self) -> Path:
        p = Path(self.output_dir).expanduser() if self.output_dir else default_output_dir()
        return p

    def resolved_music_model(self, env_default: str = DEFAULT_MUSIC_MODEL) -> str:
        """Devolve o modelo efetivo: prefs > .env > default."""
        if self.music_model and self.music_model in KNOWN_MUSIC_MODELS:
            return self.music_model
        if env_default and env_default in KNOWN_MUSIC_MODELS:
            return env_default
        return DEFAULT_MUSIC_MODEL

    def effective_music_model(self, duet_enabled: bool,
                              env_default: str = DEFAULT_MUSIC_MODEL) -> str:
        """Modelo efetivo, considerando se é dueto ou solo.

        Lógica:
        - Se o usuário setou manualmente (music_model != ""), respeita.
        - Senão (auto): se é dueto, usa music-2.6 (sweet spot pra dueto).
        - Senão (auto, solo): usa env_default / default (music-3.0).
        """
        if self.music_model and self.music_model in KNOWN_MUSIC_MODELS:
            return self.music_model
        # Auto-seleção
        if duet_enabled and "music-2.6" in KNOWN_MUSIC_MODELS:
            return "music-2.6"
        return env_default

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "UserPrefs":
        try:
            data = json.loads(raw)
        except Exception:
            return cls()
        if not isinstance(data, dict):
            return cls()
        return cls(
            output_dir=str(data.get("output_dir", "") or ""),
            music_model=str(data.get("music_model", "") or ""),
            clean_lyrics_for_duet=bool(
                data.get("clean_lyrics_for_duet", True)
            ),
        )


def load_user_prefs() -> UserPrefs:
    path = user_prefs_path()
    if not path.is_file():
        return UserPrefs()
    try:
        return UserPrefs.from_json(path.read_text(encoding="utf-8"))
    except Exception:
        return UserPrefs()


def save_user_prefs(prefs: UserPrefs) -> Path:
    path = user_prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prefs.to_json(), encoding="utf-8")
    return path


# ----------------------------- Settings globais -----------------------------

@dataclass
class AppSettings:
    """Snapshot imutável das configurações usadas pela app."""

    api_key: str
    base_url: str
    endpoint: str
    model: str
    output_dir: Path
    project_root: Path
    text_model: str = "MiniMax-M3"

    @property
    def music_url(self) -> str:
        base = self.base_url.rstrip("/")
        ep = self.endpoint if self.endpoint.startswith("/") else f"/{self.endpoint}"
        return f"{base}{ep}"

    @property
    def chat_url(self) -> str:
        """Endpoint de chat completion (OpenAI-compatible) para gerar letras."""
        # O base_url pode ser o host puro (https://api.minimax.io) ou já com /v1.
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"


def resolve_settings() -> AppSettings:
    """Combina .env, env do processo e preferências do usuário."""
    env = load_env()
    prefs = load_user_prefs()

    # API key: MINIMAX_API_KEY > token_minimax (legado)
    api_key = env.get("MINIMAX_API_KEY") or env.get("token_minimax") or ""

    base_url = env.get("MINIMAX_BASE_URL") or "https://api.minimax.io"
    endpoint = env.get("MINIMAX_MUSIC_ENDPOINT") or "/v1/music_generation"

    # Modelo de música: prefs > .env > default
    env_model = env.get("MINIMAX_MUSIC_MODEL") or ""
    model = prefs.resolved_music_model(env_default=env_model or DEFAULT_MUSIC_MODEL)
    # Garante que o model é um dos conhecidos (fallback se o .env tiver lixo)
    if model not in KNOWN_MUSIC_MODELS:
        model = DEFAULT_MUSIC_MODEL

    text_model = env.get("MINIMAX_TEXT_MODEL") or "MiniMax-M3"

    out_raw = env.get("MINIMAX_OUTPUT_DIR") or prefs.output_dir
    if out_raw:
        out_path = Path(out_raw).expanduser()
    else:
        out_path = default_output_dir()

    return AppSettings(
        api_key=api_key,
        base_url=base_url,
        endpoint=endpoint,
        model=model,
        output_dir=out_path,
        project_root=_project_root(),
        text_model=text_model,
    )
