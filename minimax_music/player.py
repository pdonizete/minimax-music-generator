"""Player de áudio usando wx.media.MediaCtrl.

No Windows, MediaCtrl usa o DirectShow / Windows Media Player, que aceita
mp3 nativamente. Para .wav também funciona. É integrado ao wx, então
combina bem com leitores de tela (botões com nomes acessíveis).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import wx
import wx.media

from . import i18n


class MusicPlayer(wx.Panel):
    """Painel de player com botões Tocar/Pausar/Parar + label do arquivo atual."""

    def __init__(self, parent: wx.Window):
        super().__init__(parent)

        # MediaCtrl nativo
        self._media = wx.media.MediaCtrl(self, style=wx.SIMPLE_BORDER)
        # No Windows, Load() precisa de um backend — best effort.
        if hasattr(wx.media, "MEDIABACKEND_WINDOWS_MEDIA"):
            self._media.SetPlaybackRate = self._media.SetPlaybackRate  # noqa: B018
        self._media.Bind(wx.media.EVT_MEDIA_LOADED, self._on_loaded)
        self._media.Bind(wx.media.EVT_MEDIA_FINISHED, self._on_finished)

        # Controles
        self.btn_play = wx.Button(self, label=i18n.BTN_PLAY)
        self.btn_pause = wx.Button(self, label=i18n.BTN_PAUSE)
        self.btn_stop = wx.Button(self, label=i18n.BTN_STOP)

        self.btn_play.Bind(wx.EVT_BUTTON, self._on_play)
        self.btn_pause.Bind(wx.EVT_BUTTON, self._on_pause)
        self.btn_stop.Bind(wx.EVT_BUTTON, self._on_stop)

        # Label do arquivo
        self.lbl_track = wx.StaticText(self, label=i18n.LBL_NO_TRACK)
        self.lbl_track.SetName(i18n.LBL_NO_TRACK)  # acessível

        # Layout
        btns = wx.BoxSizer(wx.HORIZONTAL)
        btns.Add(self.btn_play, 0, wx.RIGHT, 8)
        btns.Add(self.btn_pause, 0, wx.RIGHT, 8)
        btns.Add(self.btn_stop, 0)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.lbl_track, 0, wx.ALL, 6)
        sizer.Add(btns, 0, wx.ALL, 6)
        sizer.Add(self._media, 0, wx.ALL, 0)  # invisível por padrão
        self.SetSizer(sizer)

        # Ordem de tabulação explícita no painel do player.
        # (lbl_track é o primeiro controle, então fica como ponto de partida.)
        self.btn_play.MoveAfterInTabOrder(self.lbl_track)
        self.btn_pause.MoveAfterInTabOrder(self.btn_play)
        self.btn_stop.MoveAfterInTabOrder(self.btn_pause)

        self._current_path: Optional[Path] = None
        self._set_buttons_enabled(False)

    # ---------------- API pública ----------------

    def load(self, path: Path) -> bool:
        """Carrega um arquivo de áudio. Retorna True se OK."""
        if not path.is_file():
            return False
        ok = self._media.LoadURI(path.as_uri())
        if not ok:
            # Fallback: tentar Load com caminho
            try:
                ok = self._media.Load(str(path))
            except Exception:
                ok = False
        if ok:
            self._current_path = path
            text = i18n.LBL_TRACK_LOADED.format(filename=path.name)
            self.lbl_track.SetLabel(text)
            self.lbl_track.SetName(text)  # leitor de tela
            self._set_buttons_enabled(True)
        return ok

    def has_track(self) -> bool:
        return self._current_path is not None

    def current_path(self) -> Optional[Path]:
        return self._current_path

    # ---------------- Handlers ----------------

    def _on_play(self, _evt: wx.Event) -> None:
        if not self.has_track():
            return
        if not self._media.Play():
            wx.Bell()

    def _on_pause(self, _evt: wx.Event) -> None:
        if not self.has_track():
            return
        if not self._media.Pause():
            wx.Bell()

    def _on_stop(self, _evt: wx.Event) -> None:
        if not self.has_track():
            return
        self._media.Stop()

    def _on_loaded(self, _evt: wx.Event) -> None:
        # Toca automaticamente após carregar
        self._media.Play()

    def _on_finished(self, _evt: wx.Event) -> None:
        # Sem ação extra; usuário pode tocar novamente
        pass

    # ---------------- Utilitários ----------------

    def _set_buttons_enabled(self, enabled: bool) -> None:
        for b in (self.btn_play, self.btn_pause, self.btn_stop):
            b.Enable(enabled)
