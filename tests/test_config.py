"""Testes de config: parse do .env e resolução de paths."""

import os
from pathlib import Path
from unittest import mock

from minimax_music.config import (
    _manual_load_env,
    default_output_dir,
    load_env,
    UserPrefs,
)


def test_manual_load_env_basic(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "# comentário\n"
        "MINIMAX_API_KEY=abc123\n"
        "token_minimax=legacy\n"
        "QUOTED=\"com aspas\"\n"
        "EMPTY=\n",
        encoding="utf-8",
    )
    values = _manual_load_env(env)
    assert values["MINIMAX_API_KEY"] == "abc123"
    assert values["token_minimax"] == "legacy"
    assert values["QUOTED"] == "com aspas"
    assert values["EMPTY"] == ""


def test_load_env_prefers_minimax_api_key(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("token_minimax=legacy\n", encoding="utf-8")
    with mock.patch.dict(os.environ, {"MINIMAX_API_KEY": "preferida"}, clear=False):
        v = load_env(tmp_path)
    assert v["MINIMAX_API_KEY"] == "preferida"
    assert v["token_minimax"] == "legacy"


def test_default_output_dir_is_under_music():
    out = default_output_dir()
    assert out.name == "minimax-music"
    # Sempre termina com /minimax-music
    assert out.parts[-1] == "minimax-music"


def test_user_prefs_roundtrip():
    p = UserPrefs(output_dir="C:/some/where")
    s = p.to_json()
    p2 = UserPrefs.from_json(s)
    assert p2.output_dir == "C:/some/where"
    # Inválido → defaults
    p3 = UserPrefs.from_json("not-json")
    assert p3.output_dir == ""


def test_user_prefs_roundtrip_com_model():
    p = UserPrefs(output_dir="C:/x", music_model="music-2.6")
    s = p.to_json()
    p2 = UserPrefs.from_json(s)
    assert p2.output_dir == "C:/x"
    assert p2.music_model == "music-2.6"


def test_resolved_music_model_prefs_vencem_env():
    p = UserPrefs(music_model="music-2.6")
    assert p.resolved_music_model(env_default="music-3.0") == "music-2.6"


def test_resolved_music_model_env_quando_prefs_vazio():
    p = UserPrefs(music_model="")
    assert p.resolved_music_model(env_default="music-2.6") == "music-2.6"
    # Se prefs vazio e env vazio, cai no DEFAULT
    assert p.resolved_music_model(env_default="") == "music-3.0"


def test_resolved_music_model_ignora_valor_desconhecido():
    """Se prefs tem um valor fora da lista conhecida, ignora e usa env."""
    p = UserPrefs(music_model="music-fake-99")
    assert p.resolved_music_model(env_default="music-2.6") == "music-2.6"


def test_resolve_settings_usa_modelo_das_prefs(tmp_path, monkeypatch):
    """resolve_settings() deve considerar as prefs do usuário."""
    from minimax_music import config as cfg
    # Persiste prefs com music-2.6
    prefs_path = tmp_path / "prefs.json"
    prefs_path.write_text('{"output_dir": "", "music_model": "music-2.6"}', encoding="utf-8")
    monkeypatch.setattr(cfg, "user_prefs_path", lambda: prefs_path)
    s = cfg.resolve_settings()
    assert s.model == "music-2.6"


def test_effective_music_model_manual_sobrepoe_auto():
    """Se o user setou manualmente, respeita — mesmo no dueto."""
    p = UserPrefs(music_model="music-3.0")
    # Mesmo com dueto, se user setou music-3.0, usa music-3.0
    assert p.effective_music_model(duet_enabled=True) == "music-3.0"
    assert p.effective_music_model(duet_enabled=False) == "music-3.0"


def test_effective_music_model_auto_seleciona_music26_para_dueto():
    """Sem config manual, auto-seleciona music-2.6 pra dueto."""
    p = UserPrefs(music_model="")
    assert p.effective_music_model(duet_enabled=True) == "music-2.6"
    # Solo usa o env_default (music-3.0)
    assert p.effective_music_model(duet_enabled=False) == "music-3.0"


def test_clean_lyrics_default_true():
    """Letra limpa é o default pra duetos."""
    p = UserPrefs()
    assert p.clean_lyrics_for_duet is True


def test_user_prefs_roundtrip_com_clean_lyrics():
    """O flag de letra limpa persiste no JSON."""
    p1 = UserPrefs(clean_lyrics_for_duet=False)
    raw = p1.to_json()
    p2 = UserPrefs.from_json(raw)
    assert p2.clean_lyrics_for_duet is False
    # Default se ausente
    p3 = UserPrefs.from_json("{}")
    assert p3.clean_lyrics_for_duet is True


def test_main_window_tab_chain_existe_e_contem_controles_principais():
    """A tab_chain deve incluir os 19 controles principais."""
    import wx
    from minimax_music.config import resolve_settings
    from minimax_music.main_window import MainWindow
    app = wx.App()
    try:
        s = resolve_settings()
        frame = MainWindow(s)
        for _ in range(3):
            app.Yield()
        chain = frame._tab_chain
        assert len(chain) == 19, f"Esperado 19 controles, achou {len(chain)}"
        # Confirma que os principais estão lá
        classes = [c.GetClassName() for c in chain]
        assert "wxChoice" in classes
        assert "wxCheckBox" in classes
        assert "wxTextCtrl" in classes
        assert classes.count("wxButton") >= 6  # gerar, settings, open, play, pause, stop, gen_yt, copy
    finally:
        del app


def test_main_window_navigate_forward_via_chain():
    """_navigate_to(1) move o foco pelo próximo controle da cadeia."""
    import wx
    from minimax_music.config import resolve_settings
    from minimax_music.main_window import MainWindow
    app = wx.App()
    try:
        s = resolve_settings()
        frame = MainWindow(s)
        for _ in range(3):
            app.Yield()
        # Habilita tudo
        frame.chk_duet.SetValue(True)
        frame._update_duet_controls()
        for _ in range(2):
            app.Yield()
        # Foca o primeiro
        chain = [c for c in frame._tab_chain if c.IsEnabled() and c.IsShown()]
        chain[0].SetFocus()
        first = wx.Window.FindFocus()
        assert first is chain[0]
        # Navega pra frente
        frame._navigate_to(1)
        for _ in range(2):
            app.Yield()
        second = wx.Window.FindFocus()
        assert second is chain[1]
        # Navega pra trás
        frame._navigate_to(-1)
        for _ in range(2):
            app.Yield()
        back = wx.Window.FindFocus()
        assert back is chain[0]
    finally:
        del app
